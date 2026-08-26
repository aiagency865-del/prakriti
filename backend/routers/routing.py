import math

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from core.database import db
from core.security import get_current_user

router = APIRouter()

NER_PLACES = {
    "guwahati": (91.74, 26.15), "shillong": (91.60, 25.57), "tezpur": (92.80, 26.63),
    "nagaon": (92.32, 26.30), "jorhat": (94.20, 26.75), "silchar": (92.78, 24.83),
    "aizawl": (92.90, 23.73), "kohima": (94.05, 25.70), "dimapur": (93.73, 25.91),
    "imphal": (93.94, 24.82), "ukhrul": (94.35, 24.98), "itanagar": (93.61, 27.10),
    "pasighat": (95.33, 28.06), "agartala": (91.28, 23.83), "udaipur": (91.49, 23.53),
    "goalpara": (90.97, 26.07), "mangaldai": (92.03, 26.44),
}

VEHICLE_SPEEDS = {"TWO_WHEELER": 45, "LIGHT": 55, "SUV": 60, "TRUCK": 40, "EMERGENCY": 75}
STATUS_MULTIPLIER = {"OPEN": 1.0, "AT_RISK": 3.0, "RESTRICTED": 5.0, "UNKNOWN": 1.5}


def _haversine_km(a, b):
    lng1, lat1 = a
    lng2, lat2 = b
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _line_length_km(coords):
    return sum(_haversine_km(coords[i], coords[i + 1]) for i in range(len(coords) - 1))


def _snap_places(point, max_km=25.0):
    return [name for name, coord in NER_PLACES.items() if _haversine_km(point, coord) <= max_km]


def _build_graph(roads, exclude_blocked=True):
    adj = {}
    for r in roads:
        if exclude_blocked and r["status"] in ("BLOCKED", "GOVERNMENT_CLOSED"):
            continue
        coords = r["geometry"]["coordinates"]
        starts = _snap_places(coords[0])
        ends = _snap_places(coords[-1])
        length = _line_length_km(coords)
        for a in starts:
            for b in ends:
                if a == b:
                    continue
                cost = length * STATUS_MULTIPLIER.get(r["status"], 1.5)
                adj.setdefault(a, []).append((b, r, cost))
                adj.setdefault(b, []).append((a, r, cost))
    # Local-road connectors: link each town to its 3 nearest towns so any OD pair routes (demo network)
    names = list(NER_PLACES.keys())
    for a in names:
        dists = sorted((_haversine_km(NER_PLACES[a], NER_PLACES[b]), b) for b in names if b != a)
        for d, b in dists[:3]:
            pseudo = {
                "id": f"local-{a}-{b}", "name": f"Local roads {a.title()}–{b.title()}",
                "status": "LOCAL", "risk": 25, "district": "—",
                "geometry": {"type": "LineString", "coordinates": [list(NER_PLACES[a]), list(NER_PLACES[b])]},
            }
            cost = d * 1.3 * 2.0
            adj.setdefault(a, []).append((b, pseudo, cost))
            adj.setdefault(b, []).append((a, pseudo, cost))
    return adj


def _dijkstra(adj, start, end):
    dist = {start: 0.0}
    prev = {}
    visited = set()
    while True:
        cur = None
        best = float("inf")
        for n, d in dist.items():
            if n not in visited and d < best:
                cur, best = n, d
        if cur is None:
            return None
        if cur == end:
            break
        visited.add(cur)
        for nb, road, cost in adj.get(cur, []):
            nd = best + cost
            if nd < dist.get(nb, float("inf")):
                dist[nb] = nd
                prev[nb] = (cur, road)
    if end not in prev and end != start:
        return None
    edges = []
    cur = end
    while cur != start:
        p, road = prev[cur]
        edges.append((p, cur, road))
        cur = p
    edges.reverse()
    return edges


def _assemble_route(edges, start):
    segments = []
    polyline = []
    cur_node = start
    for a, b, road in edges:
        coords = road["geometry"]["coordinates"]
        if _haversine_km(coords[-1], NER_PLACES[cur_node]) < _haversine_km(coords[0], NER_PLACES[cur_node]):
            coords = list(reversed(coords))
        if polyline and coords:
            polyline.extend(coords[1:])
        else:
            polyline.extend(coords)
        segments.append({
            "road_id": road["id"],
            "name": road.get("name"),
            "status": road.get("status"),
            "risk": road.get("risk"),
            "district": road.get("district"),
            "distance_km": round(_line_length_km(road["geometry"]["coordinates"]), 1),
            "geometry": road["geometry"],
        })
        cur_node = b
    return segments, polyline


class RouteRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    origin: str
    destination: str
    vehicle_type: str = "TRUCK"


@router.get("/routes/places")
async def route_places(user: dict = Depends(get_current_user)):
    return sorted(NER_PLACES.keys())


async def _osrm_route(o, d):
    """Real road-network routing via the public OSRM demo server (OpenStreetMap data)."""
    try:
        async with httpx.AsyncClient(timeout=6.0) as http_client:
            resp = await http_client.get(
                f"https://router.project-osrm.org/route/v1/driving/{o[0]},{o[1]};{d[0]},{d[1]}",
                params={"overview": "full", "geometries": "geojson"},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("routes"):
                    rt = data["routes"][0]
                    return rt["geometry"]["coordinates"], rt["distance"] / 1000.0, rt["duration"] / 60.0
    except Exception:
        pass
    return None


def _corridors_near(coords, roads, max_km=12.0):
    sample = coords[:: max(1, len(coords) // 200)]
    near = []
    for r in roads:
        rcoords = r["geometry"]["coordinates"]
        if any(_haversine_km(p, q) <= max_km for p in rcoords for q in sample):
            near.append(r)
    return near


async def compute_route(origin: str, destination: str, vehicle: str) -> dict:
    roads = await db.roads.find({}, {"_id": 0}).to_list(1000)
    speed = VEHICLE_SPEEDS[vehicle]
    osrm = await _osrm_route(NER_PLACES[origin], NER_PLACES[destination])

    if osrm:
        coords, dist_km, dur_min = osrm
        near = _corridors_near(coords, roads)
        segments = [
            {"road_id": r["id"], "name": r.get("name"), "status": r.get("status"), "risk": r.get("risk"),
             "district": r.get("district"), "distance_km": round(_line_length_km(r["geometry"]["coordinates"]), 1),
             "geometry": r["geometry"]}
            for r in near
        ]
        blocked_roads = [s["name"] for s in segments if s["status"] in ("BLOCKED", "GOVERNMENT_CLOSED")]
        at_risk_names = [s["name"] for s in segments if s["status"] in ("AT_RISK", "RESTRICTED")]
        risky_len = sum(s["distance_km"] for s in segments if s["status"] in ("AT_RISK", "RESTRICTED", "BLOCKED", "GOVERNMENT_CLOSED"))
        eta_minutes = round(dur_min * (1 + 0.5 * (risky_len / max(dist_km, 1))))
        risk_score = max([s["risk"] or 0 for s in segments], default=15)
        reason = ["Real road-network routing (OpenStreetMap via OSRM)"]
        reason.append(f"Corridor includes government-blocked road(s): {', '.join(blocked_roads)}" if blocked_roads else "No government closures near this route")
        if at_risk_names:
            reason.append(f"Elevated hazard on: {', '.join(at_risk_names)}")
        reason.append(f"Suitable for {vehicle.replace('_', ' ').title()}")
        return {
            "provenance": "OSM_ROAD_NETWORK + LIVE_CORRIDOR_STATUS",
            "origin": {"name": origin, "lng": NER_PLACES[origin][0], "lat": NER_PLACES[origin][1]},
            "destination": {"name": destination, "lng": NER_PLACES[destination][0], "lat": NER_PLACES[destination][1]},
            "vehicle_type": vehicle,
            "recommended_route": {
                "segments": segments,
                "polyline": coords,
                "distance_km": round(dist_km, 1),
                "eta_minutes": eta_minutes,
                "risk_score": risk_score,
                "contains_blocked": len(blocked_roads) > 0,
                "blocked_roads": blocked_roads,
                "road_ids": [r["id"] for r in near],
            },
            "reason": reason,
            "alternative_route": None,
        }

    # Fallback: demo corridor graph (offline / OSRM unreachable)
    adj = _build_graph(roads, exclude_blocked=True)
    edges = _dijkstra(adj, origin, destination)
    if edges is None:
        adj_all = _build_graph(roads, exclude_blocked=False)
        edges = _dijkstra(adj_all, origin, destination)
    if edges is None:
        pseudo = {
            "id": f"direct-{origin}-{destination}", "name": f"Direct route {origin.title()}–{destination.title()} (off-network)",
            "status": "LOCAL", "risk": 35, "district": "—",
            "geometry": {"type": "LineString", "coordinates": [list(NER_PLACES[origin]), list(NER_PLACES[destination])]},
        }
        edges = [(origin, destination, pseudo)]

    segments, polyline = _assemble_route(edges, origin)
    distance_km = round(_line_length_km(polyline), 1)
    risky_len = sum(s["distance_km"] for s in segments if s["status"] in ("AT_RISK", "RESTRICTED", "BLOCKED", "GOVERNMENT_CLOSED"))
    delay_factor = 1 + 0.5 * (risky_len / max(distance_km, 1))
    eta_minutes = round(distance_km / speed * 60 * delay_factor)
    risk_score = max((s["risk"] or 0) for s in segments)
    blocked_roads = [s["name"] for s in segments if s["status"] in ("BLOCKED", "GOVERNMENT_CLOSED")]

    reason = ["Demo corridor-graph routing (offline mode)"]
    reason.append(f"Corridor includes government-blocked road(s): {', '.join(blocked_roads)}" if blocked_roads else "No government closures on this route")
    at_risk_names = [s["name"] for s in segments if s["status"] in ("AT_RISK", "RESTRICTED")]
    if at_risk_names:
        reason.append(f"Elevated hazard on: {', '.join(at_risk_names)}")
    reason.append(f"Suitable for {vehicle.replace('_', ' ').title()}")

    alternative = None
    if not blocked_roads:
        adj_naive = _build_graph(roads, exclude_blocked=False)
        naive_edges = _dijkstra(adj_naive, origin, destination)
        if naive_edges and [e[2]["id"] for e in naive_edges] != [e[2]["id"] for e in edges]:
            nseg, npoly = _assemble_route(naive_edges, origin)
            n_blocked = [s["name"] for s in nseg if s["status"] in ("BLOCKED", "GOVERNMENT_CLOSED")]
            if n_blocked:
                nd = round(_line_length_km(npoly), 1)
                alternative = {
                    "segments": nseg,
                    "polyline": npoly,
                    "distance_km": nd,
                    "eta_minutes": round(nd / speed * 60),
                    "risk_score": max((s["risk"] or 0) for s in nseg),
                    "rejected_because": [f"Government closure: {', '.join(n_blocked)}"] + ([f"Risk score {max((s['risk'] or 0) for s in nseg)}"] if max((s["risk"] or 0) for s in nseg) >= 60 else []),
                }

    return {
        "provenance": "DEMO",
        "origin": {"name": origin, "lng": NER_PLACES[origin][0], "lat": NER_PLACES[origin][1]},
        "destination": {"name": destination, "lng": NER_PLACES[destination][0], "lat": NER_PLACES[destination][1]},
        "vehicle_type": vehicle,
        "recommended_route": {
            "segments": segments,
            "polyline": polyline,
            "distance_km": distance_km,
            "eta_minutes": eta_minutes,
            "risk_score": risk_score,
            "contains_blocked": len(blocked_roads) > 0,
            "blocked_roads": blocked_roads,
            "road_ids": [s["road_id"] for s in segments if not s["road_id"].startswith(("local-", "direct-"))],
        },
        "reason": reason,
        "alternative_route": alternative,
    }


@router.post("/routes/calculate")
async def calculate_route(body: RouteRequest, user: dict = Depends(get_current_user)):
    origin = body.origin.strip().lower()
    destination = body.destination.strip().lower()
    if origin not in NER_PLACES or destination not in NER_PLACES:
        raise HTTPException(status_code=400, detail=f"Unknown place. Valid: {sorted(NER_PLACES.keys())}")
    if origin == destination:
        raise HTTPException(status_code=400, detail="Origin and destination must be different")
    vehicle = body.vehicle_type.upper()
    if vehicle not in VEHICLE_SPEEDS:
        raise HTTPException(status_code=400, detail=f"Invalid vehicle type. Valid: {sorted(VEHICLE_SPEEDS.keys())}")
    return await compute_route(origin, destination, vehicle)
