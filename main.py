import logging
import sys
import os
from contextlib import asynccontextmanager

import uvicorn
import osmnx as ox
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from graph import load_graph
from router import alternative_routes, path_stats, turn_by_turn, get_traffic_factor, check_distance, ASTAR_TIMEOUT_S
from geocoder import geocode
from database import init_db, salvar_historico, listar_historico, salvar_favorito, listar_favoritos, deletar_favorito

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

G = None

# Diretório deste arquivo = onde está o index.html
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(THIS_DIR, "index.html")

logger.info(f"THIS_DIR={THIS_DIR}")
logger.info(f"INDEX_PATH={INDEX_PATH}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global G
    logger.info("Iniciando servidor...")
    await init_db()
    G = load_graph()
    logger.info("Servidor pronto!")
    yield
    logger.info("Servidor encerrado.")


app = FastAPI(title="Waze Clone BH", version="2.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class FavoritoIn(BaseModel):
    nome: str
    lat: float
    lon: float


def _nearest(lon, lat):
    try:
        # Busca manual com KDTree para não depender do scikit-learn
        import numpy as np
        nodes = list(G.nodes(data=True))
        xs = np.array([d["x"] for _, d in nodes])
        ys = np.array([d["y"] for _, d in nodes])
        dists = (xs - lon)**2 + (ys - lat)**2
        idx = int(np.argmin(dists))
        return nodes[idx][0]
    except Exception as e:
        raise HTTPException(400, f"Ponto fora da área do mapa: {e}")

def _path_to_geojson(G, path, props):
    coords = [[G.nodes[n]["x"], G.nodes[n]["y"]] for n in path]
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": props,
    }


@app.get("/api/debug")
async def debug():
    try:
        dir_contents = os.listdir(THIS_DIR)
    except Exception as e:
        dir_contents = str(e)
    return {
        "__file__": os.path.abspath(__file__),
        "THIS_DIR": THIS_DIR,
        "INDEX_PATH": INDEX_PATH,
        "index_exists": os.path.exists(INDEX_PATH),
        "dir_contents": dir_contents,
        "cwd": os.getcwd(),
    }


@app.get("/api/status")
async def status():
    if G is None:
        return {"status": "loading"}
    return {"status": "ready", "nos": len(G.nodes), "arestas": len(G.edges)}


@app.get("/api/rotas")
async def get_routes(
    olat: float = Query(...), olon: float = Query(...),
    dlat: float = Query(...), dlon: float = Query(...),
    k: int = Query(3, ge=1, le=5),
    modo: str = Query("drive", pattern="^(drive|walk|bike)$"),
    evitar_pedagio: bool = Query(False),
    evitar_rodovias: bool = Query(False),
    transito: bool = Query(True),
):
    if G is None:
        raise HTTPException(503, "Grafo ainda carregando. Aguarde.")

    orig = _nearest(olon, olat)
    dest = _nearest(dlon, dlat)
    if orig == dest:
        raise HTTPException(400, "Origem e destino são o mesmo ponto.")

    try:
        dist_km = check_distance(G, orig, dest)
    except ValueError as e:
        raise HTTPException(400, str(e))

    logger.info(f"Rota solicitada: {dist_km:.1f} km em linha reta, modo={modo}")

    traffic_factor = get_traffic_factor() if transito else 1.0
    paths = alternative_routes(
        G, orig, dest, k=k, mode=modo,
        traffic_factor=traffic_factor,
        avoid_tolls=evitar_pedagio,
        avoid_highways=evitar_rodovias,
    )

    if not paths:
        raise HTTPException(
            404,
            f"Nenhuma rota encontrada entre os pontos selecionados. "
            f"Verifique se origem e destino são acessíveis por '{modo}', "
            f"ou se os filtros (pedágio/rodovia) estão muito restritivos. "
            f"(Timeout do A*: {ASTAR_TIMEOUT_S}s)"
        )

    features = []
    for i, path in enumerate(paths):
        stats = path_stats(G, path, mode=modo, traffic_factor=traffic_factor)
        instrs = turn_by_turn(G, path) if i == 0 else []
        features.append(_path_to_geojson(G, path, {
            "indice": i,
            "nos": len(path),
            "distancia_km": stats["distancia_km"],
            "tempo_min": stats["tempo_min"],
            "modo": modo,
            "fator_transito": round(traffic_factor, 2),
            "instrucoes": instrs,
        }))

    s = features[0]["properties"]
    await salvar_historico(
        f"{olat:.4f},{olon:.4f}", f"{dlat:.4f},{dlon:.4f}",
        s["distancia_km"], s["tempo_min"], modo
    )

    return {"type": "FeatureCollection", "features": features}


@app.get("/api/geocode")
async def geocode_address(q: str = Query(...)):
    result = await geocode(q)
    if result is None:
        raise HTTPException(404, f"Endereço não encontrado: {q}")
    return {"lat": result[0], "lon": result[1], "endereco": q}


@app.get("/api/geocode-reverso")
async def reverse_geocode(lat: float = Query(...), lon: float = Query(...)):
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "json"},
                headers={"User-Agent": "waze-clone-study/2.0"},
            )
            data = r.json()
            addr = data.get("address", {})
            name = (addr.get("road") or addr.get("neighbourhood") or
                    addr.get("suburb") or data.get("display_name", f"{lat:.4f},{lon:.4f}"))
            return {"nome": name}
    except Exception:
        return {"nome": f"{lat:.4f},{lon:.4f}"}


@app.get("/api/historico")
async def get_historico():
    return await listar_historico()


@app.get("/api/favoritos")
async def get_favoritos():
    return await listar_favoritos()


@app.post("/api/favoritos")
async def post_favorito(fav: FavoritoIn):
    await salvar_favorito(fav.nome, fav.lat, fav.lon)
    return {"ok": True}


@app.delete("/api/favoritos/{id}")
async def del_favorito(id: int):
    await deletar_favorito(id)
    return {"ok": True}


@app.get("/api/transito")
async def get_transito():
    from datetime import datetime
    hora = datetime.now().hour
    fator = get_traffic_factor(hora)
    return {
        "hora": hora,
        "fator": round(fator, 2),
        "descricao": _descricao_transito(fator),
        "tabela": {h: round(get_traffic_factor(h), 2) for h in range(24)},
    }

def _descricao_transito(f):
    if f >= 1.7: return "Trânsito intenso"
    if f >= 1.3: return "Trânsito moderado"
    if f >= 1.1: return "Trânsito leve"
    return "Via livre"


@app.get("/")
async def home():
    if not os.path.exists(INDEX_PATH):
        logger.error(f"index.html nao encontrado em: {INDEX_PATH}")
        return HTMLResponse(
            f"<h2>index.html nao encontrado em: {INDEX_PATH}</h2>"
            f"<p>Conteudo de THIS_DIR: {os.listdir(THIS_DIR)}</p>",
            status_code=500,
        )
    return FileResponse(INDEX_PATH)


if __name__ == "__main__":
    os.chdir(THIS_DIR)
    logger.info("Iniciando Uvicorn...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)