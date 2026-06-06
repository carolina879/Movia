import osmnx as ox
import networkx as nx
import pickle
import os
import logging

logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join(os.path.dirname(__file__), "bh_graph.pkl")
DEFAULT_PLACE = "Belo Horizonte, Minas Gerais, Brazil"


def load_graph(place: str = DEFAULT_PLACE) -> nx.MultiDiGraph:

    if os.path.exists(CACHE_FILE):
        logger.info("Carregando grafo do cache...")
        with open(CACHE_FILE, "rb") as f:
            G = pickle.load(f)
        logger.info(f"Grafo carregado: {len(G.nodes)} nós, {len(G.edges)} arestas")
        return G

    logger.info(f"Baixando mapa de '{place}' do OpenStreetMap...")
    logger.info("Isso pode levar 2-5 minutos na primeira vez.")

    ox.settings.log_console = True
    ox.settings.use_cache = True

    G = ox.graph_from_place(place, network_type="drive", simplify=True)

    
    G = ox.add_edge_speeds(G)

    
    G = ox.add_edge_travel_times(G)

    logger.info(f"Grafo criado: {len(G.nodes)} nós, {len(G.edges)} arestas")
    logger.info("Salvando cache...")

    with open(CACHE_FILE, "wb") as f:
        pickle.dump(G, f)

    logger.info("Cache salvo em bh_graph.pkl")
    return G
