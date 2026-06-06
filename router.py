import heapq
import math
import time
from networkx import MultiDiGraph
from datetime import datetime

# ── Constantes ────────────────────────────────────────────────────────────────
MAX_SPEED_MS = 130 / 3.6

# Distância máxima em linha reta permitida entre origem e destino (300 km)
MAX_STRAIGHT_LINE_KM = 300.0

# Timeout máximo para o A* (segundos)
ASTAR_TIMEOUT_S = 15.0

# Tipos de via a evitar por modo
AVOID_HIGHWAY_TYPES = {
    "toll":     {"motorway", "motorway_link", "trunk", "trunk_link"},
    "highway":  {"motorway", "motorway_link", "trunk", "trunk_link"},
    "walk":     {"motorway", "motorway_link", "trunk", "trunk_link"},
    "bike":     {"motorway", "motorway_link", "trunk", "trunk_link"},
}

# Velocidades médias por modo (m/s)
MODE_SPEEDS = {
    "drive": None,      # usa travel_time do OSM
    "walk":  1.4,       # 5 km/h
    "bike":  4.2,       # 15 km/h
}

# Multiplicadores de trânsito simulado por hora do dia
TRAFFIC_FACTORS = {
    range(0, 6):   0.8,
    range(6, 7):   1.2,
    range(7, 10):  1.8,
    range(10, 12): 1.1,
    range(12, 14): 1.3,
    range(14, 17): 1.1,
    range(17, 20): 1.9,
    range(20, 22): 1.3,
    range(22, 24): 0.9,
}


def get_traffic_factor(hour: int = None) -> float:
    if hour is None:
        hour = datetime.now().hour
    for r, factor in TRAFFIC_FACTORS.items():
        if hour in r:
            return factor
    return 1.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def check_distance(G: MultiDiGraph, orig: int, dest: int):
    """
    Valida se a distância em linha reta entre origem e destino é razoável.
    Lança ValueError se ultrapassar MAX_STRAIGHT_LINE_KM.
    """
    lat1 = G.nodes[orig]["y"]; lon1 = G.nodes[orig]["x"]
    lat2 = G.nodes[dest]["y"]; lon2 = G.nodes[dest]["x"]
    dist_km = haversine(lat1, lon1, lat2, lon2) / 1000
    if dist_km > MAX_STRAIGHT_LINE_KM:
        raise ValueError(
            f"Distância em linha reta muito grande: {dist_km:.0f} km. "
            f"Máximo permitido: {MAX_STRAIGHT_LINE_KM:.0f} km."
        )
    return dist_km


def get_edge_cost(
    G: MultiDiGraph,
    u: int, v: int,
    mode: str = "drive",
    penalties: dict = None,
    traffic_factor: float = 1.0,
    avoid_tolls: bool = False,
    avoid_highways: bool = False,
) -> float:
    edges = G[u][v]
    best = min(edges.values(), key=lambda e: e.get("travel_time", float("inf")))

    hw = best.get("highway", "")
    if isinstance(hw, list):
        hw = hw[0] if hw else ""

    if avoid_tolls and best.get("toll") == "yes":
        return float("inf")

    avoid_set = set()
    if avoid_highways:
        avoid_set |= AVOID_HIGHWAY_TYPES.get("highway", set())
    if mode in AVOID_HIGHWAY_TYPES:
        avoid_set |= AVOID_HIGHWAY_TYPES[mode]
    if hw in avoid_set:
        return float("inf")

    if mode == "drive":
        cost = best.get("travel_time", float("inf")) * traffic_factor
    else:
        speed = MODE_SPEEDS[mode]
        length = best.get("length", float("inf"))
        cost = length / speed

    if penalties and (u, v) in penalties:
        cost *= penalties[(u, v)]

    return cost


def get_edge_length(G: MultiDiGraph, u: int, v: int) -> float:
    edges = G[u][v]
    best = min(edges.values(), key=lambda e: e.get("length", float("inf")))
    return best.get("length", 0.0)


def astar(
    G: MultiDiGraph,
    orig: int,
    dest: int,
    mode: str = "drive",
    penalties: dict = None,
    traffic_factor: float = 1.0,
    avoid_tolls: bool = False,
    avoid_highways: bool = False,
    timeout: float = ASTAR_TIMEOUT_S,
) -> list[int]:
    """
    A* com timeout. Retorna lista vazia se não encontrar rota ou se estourar o tempo.
    """
    if orig == dest:
        return [orig]

    dest_lat = G.nodes[dest]["y"]
    dest_lon = G.nodes[dest]["x"]
    deadline = time.monotonic() + timeout

    def heuristic(node: int) -> float:
        lat = G.nodes[node]["y"]
        lon = G.nodes[node]["x"]
        return haversine(lat, lon, dest_lat, dest_lon) / MAX_SPEED_MS

    heap = [(heuristic(orig), 0.0, orig)]
    g_score: dict[int, float] = {orig: 0.0}
    came_from: dict[int, int] = {}
    visited: set[int] = set()

    while heap:
        # Verifica timeout a cada iteração
        if time.monotonic() > deadline:
            return []

        f, g, current = heapq.heappop(heap)
        if current in visited:
            continue
        visited.add(current)
        if current == dest:
            return _reconstruct_path(came_from, orig, dest)

        for neighbor in G.neighbors(current):
            if neighbor in visited:
                continue
            cost = get_edge_cost(G, current, neighbor, mode, penalties, traffic_factor, avoid_tolls, avoid_highways)
            if cost == float("inf"):
                continue
            tentative_g = g + cost
            if tentative_g < g_score.get(neighbor, float("inf")):
                g_score[neighbor] = tentative_g
                came_from[neighbor] = current
                heapq.heappush(heap, (tentative_g + heuristic(neighbor), tentative_g, neighbor))

    return []


def _penalty_factor_for_distance(dist_km: float) -> float:
    """
    Retorna um PENALTY_FACTOR adaptativo baseado na distância da rota.
    Rotas mais curtas precisam de penalização maior para forçar desvios significativos.
    Rotas longas toleram penalização menor pois já há muitos caminhos alternativos.
    """
    if dist_km < 5:
        return 12.0
    if dist_km < 15:
        return 8.0
    if dist_km < 40:
        return 5.0
    return 3.5


def alternative_routes(
    G: MultiDiGraph,
    orig: int,
    dest: int,
    k: int = 3,
    mode: str = "drive",
    traffic_factor: float = 1.0,
    avoid_tolls: bool = False,
    avoid_highways: bool = False,
) -> list[list[int]]:
    dist_km = haversine(
        G.nodes[orig]["y"], G.nodes[orig]["x"],
        G.nodes[dest]["y"], G.nodes[dest]["x"],
    ) / 1000
    penalty_factor = _penalty_factor_for_distance(dist_km)

    MAX_SIMILARITY = 0.85
    routes = []
    penalties: dict[tuple, float] = {}

    for _ in range(k * 2):
        path = astar(G, orig, dest, mode, penalties, traffic_factor, avoid_tolls, avoid_highways)
        if not path:
            break
        if not _too_similar(path, routes, MAX_SIMILARITY):
            routes.append(path)
        if len(routes) >= k:
            break
        for u, v in zip(path, path[1:]):
            penalties[(u, v)] = penalties.get((u, v), 1.0) * penalty_factor

    return routes


def _too_similar(path, existing, threshold):
    path_set = set(path)
    for other in existing:
        overlap = len(path_set & set(other)) / max(len(path_set), len(other))
        if overlap > threshold:
            return True
    return False


def _reconstruct_path(came_from, orig, dest):
    path, current = [], dest
    while current != orig:
        path.append(current)
        current = came_from[current]
    path.append(orig)
    path.reverse()
    return path


def path_stats(G: MultiDiGraph, path: list[int], mode: str = "drive", traffic_factor: float = 1.0) -> dict:
    if len(path) < 2:
        return {"distancia_km": 0.0, "tempo_min": 0.0}
    total_length = 0.0
    total_time = 0.0
    for u, v in zip(path, path[1:]):
        total_length += get_edge_length(G, u, v)
        cost = get_edge_cost(G, u, v, mode=mode, traffic_factor=traffic_factor)
        if cost < float("inf"):
            total_time += cost
    return {
        "distancia_km": round(total_length / 1000, 2),
        "tempo_min": round(total_time / 60, 1),
    }


def turn_by_turn(G: MultiDiGraph, path: list[int]) -> list[dict]:
    """Gera instruções turn-by-turn detectando ângulo entre segmentos."""
    if len(path) < 2:
        return []

    def bearing(lat1, lon1, lat2, lon2):
        d_lon = math.radians(lon2 - lon1)
        lat1, lat2 = math.radians(lat1), math.radians(lat2)
        x = math.sin(d_lon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(d_lon)
        return (math.degrees(math.atan2(x, y)) + 360) % 360

    def turn_direction(angle_diff):
        d = (angle_diff + 180) % 360 - 180
        if d < -45:  return "Vire à esquerda"
        if d > 45:   return "Vire à direita"
        if d < -15:  return "Mantenha-se à esquerda"
        if d > 15:   return "Mantenha-se à direita"
        return "Siga em frente"

    def get_street_name(u, v):
        edges = G[u][v]
        best = min(edges.values(), key=lambda e: e.get("travel_time", float("inf")))
        name = best.get("name", "")
        if isinstance(name, list):
            name = name[0] if name else ""
        return name or "rua sem nome"

    instructions = []
    accumulated_dist = 0.0
    current_street = get_street_name(path[0], path[1])

    for i in range(1, len(path) - 1):
        u, v, w = path[i - 1], path[i], path[i + 1]
        accumulated_dist += get_edge_length(G, u, v)
        next_street = get_street_name(v, w)

        n1 = G.nodes[u]; n2 = G.nodes[v]; n3 = G.nodes[w]
        b1 = bearing(n1["y"], n1["x"], n2["y"], n2["x"])
        b2 = bearing(n2["y"], n2["x"], n3["y"], n3["x"])
        angle_diff = b2 - b1

        direction = turn_direction(angle_diff)

        if next_street != current_street or direction != "Siga em frente":
            dist_str = f"{accumulated_dist:.0f} m" if accumulated_dist < 1000 else f"{accumulated_dist/1000:.1f} km"
            instructions.append({
                "instrucao": f"{direction} na {next_street}",
                "distancia": dist_str,
                "lat": n2["y"],
                "lon": n2["x"],
            })
            accumulated_dist = 0.0
            current_street = next_street

    last = path[-1]
    instructions.append({
        "instrucao": "Você chegou ao destino",
        "distancia": "",
        "lat": G.nodes[last]["y"],
        "lon": G.nodes[last]["x"],
    })

    return instructions