from datetime import datetime, timezone

from core.database import db
from core.ws import manager
from routers.routing import compute_route


async def _reroute_trips_on_road(road_id: str, road_name: str, new_status: str):
    """Push REROUTE_REQUIRED to every driver with an active trip through this road."""
    now_iso = datetime.now(timezone.utc).isoformat()
    trips = await db.trips.find({"status": "ACTIVE", "road_ids": road_id}).to_list(50)
    for t in trips:
        new_route = await compute_route(t["origin"], t["destination"], t.get("vehicle_type", "TRUCK"))
        await db.trips.update_one(
            {"id": t["id"]},
            {"$set": {"route": new_route, "rerouted_at": now_iso, "reroute_reason": f"{road_name} is now {new_status.replace('_', ' ')}"}},
        )
        await manager.send_to_user(t["driver_email"], {
            "type": "REROUTE_REQUIRED",
            "trip_id": t["id"],
            "road_id": road_id,
            "road_name": road_name,
            "new_status": new_status,
            "route": new_route,
        })
