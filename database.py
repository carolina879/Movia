import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "waze.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS historico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                origem TEXT,
                destino TEXT,
                distancia_km REAL,
                tempo_min REAL,
                modo TEXT DEFAULT 'drive',
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS favoritos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def salvar_historico(origem: str, destino: str, distancia_km: float, tempo_min: float, modo: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO historico (origem, destino, distancia_km, tempo_min, modo) VALUES (?,?,?,?,?)",
            (origem, destino, distancia_km, tempo_min, modo)
        )
        # Mantém só os últimos 50
        await db.execute("DELETE FROM historico WHERE id NOT IN (SELECT id FROM historico ORDER BY id DESC LIMIT 50)")
        await db.commit()


async def listar_historico():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM historico ORDER BY criado_em DESC LIMIT 20") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def salvar_favorito(nome: str, lat: float, lon: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO favoritos (nome, lat, lon) VALUES (?,?,?)", (nome, lat, lon))
        await db.commit()


async def listar_favoritos():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM favoritos ORDER BY nome") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def deletar_favorito(id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM favoritos WHERE id=?", (id,))
        await db.commit()