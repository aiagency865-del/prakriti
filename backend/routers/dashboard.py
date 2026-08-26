from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from core.database import db
from core.security import get_current_user
from seed import _iso_mins_ago

router = APIRouter()


@router.get("/dashboard/summary")
async def dashboard_summary(user: dict = Depends(get_current_user)):
    roads = await db.roads.find({}, {"_id": 0}).to_list(1000)
    incidents = await db.incidents.find({}, {"_id": 0}).sort("created_minutes_ago", 1).to_list(100)
    vehicles = await db.vehicles.find({}, {"_id": 0}).to_list(500)
    villages = await db.villages.find({}, {"_id": 0}).to_list(500)
    supply = await db.supply_risks.find({}, {"_id": 0}).to_list(100)

    now = datetime.now(timezone.utc)
    for i in incidents:
        i["created_at"] = _iso_mins_ago(i.get("created_minutes_ago", 0))
        i.pop("created_minutes_ago", None)

    kpis = {
        "active_vehicles": sum(1 for v in vehicles if v.get("status") in ("IN_TRANSIT", "DELAYED")),
        "at_risk_corridors": sum(1 for r in roads if r.get("status") in ("AT_RISK", "RESTRICTED")),
        "blocked_roads": sum(1 for r in roads if r.get("status") in ("BLOCKED", "GOVERNMENT_CLOSED")),
        "critical_alerts": sum(1 for i in incidents if i.get("severity") in ("CRITICAL", "HIGH")),
        "villages_isolation_risk": sum(1 for v in villages if v.get("isolation_risk") in ("HIGH", "CRITICAL")),
        "critical_supply_locations": sum(s.get("at_risk_count", 0) for s in supply if s.get("severity") == "CRITICAL"),
    }

    return {
        "provenance": "DEMO",
        "generated_at": now.isoformat(),
        "kpis": kpis,
        "roads": {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": r["geometry"], "properties": {k: v for k, v in r.items() if k != "geometry"}}
                for r in roads
            ],
        },
        "incidents": incidents,
        "vehicles": vehicles,
        "supply": supply,
        "villages": villages,
    }
