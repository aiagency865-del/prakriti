from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from core.database import db
from core.security import GOVERNMENT_ROLES, get_current_user
from seed import _current_environment, _iso_mins_ago

router = APIRouter()


@router.get("/environment")
async def get_environment(user: dict = Depends(get_current_user)):
    events = await db.environment_events.find({}, {"_id": 0}).to_list(100)
    env = _current_environment(events)
    return {"provenance": "DEMO", **env}


@router.get("/deliveries")
async def list_deliveries(user: dict = Depends(get_current_user)):
    return await db.deliveries.find({}, {"_id": 0}).to_list(500)


@router.get("/alerts")
async def list_alerts(user: dict = Depends(get_current_user)):
    # Verification pipeline: unverified reports/incidents are visible only to
    # government & field roles; logistics and public see only VERIFIED items,
    # plus government notifications and emergency zones.
    privileged = user["role"] in (GOVERNMENT_ROLES | {"FIELD_OFFICER", "DRIVER"})
    inc_q = {"status": {"$ne": "RESOLVED"}} if privileged else {"status": "VERIFIED"}
    rep_q = {} if privileged else {"status": "VERIFIED"}
    incidents = await db.incidents.find(inc_q, {"_id": 0}).to_list(200)
    reports = await db.field_reports.find(rep_q, {"_id": 0}).to_list(200)
    public_reports = await db.public_reports.find(rep_q, {"_id": 0}).to_list(200)
    notifications = await db.notifications.find({}, {"_id": 0}).sort("created_at", -1).to_list(20)
    zones = await db.emergency_zones.find({"active": True}, {"_id": 0}).to_list(20)
    actions = await db.government_actions.find({}, {"_id": 0}).sort("timestamp", -1).to_list(20)

    feed = []
    for i in incidents:
        feed.append({
            "kind": "INCIDENT", "id": i["id"], "title": i.get("title"), "severity": i.get("severity"),
            "location": i.get("location"), "source": i.get("source"), "status": i.get("status"),
            "created_at": i.get("created_at") or _iso_mins_ago(i.get("created_minutes_ago", 0)),
        })
    for r in reports:
        feed.append({
            "kind": "FIELD_REPORT", "id": r["id"], "title": r.get("description", "")[:80], "severity": r.get("severity"),
            "location": r.get("location"), "source": f"FIELD · {r.get('officer_name', 'Officer')}", "status": r.get("status"),
            "created_at": r.get("created_at") or _iso_mins_ago(r.get("created_minutes_ago", 0)),
        })
    for r in public_reports:
        feed.append({
            "kind": "PUBLIC_REPORT", "id": r["id"], "title": r.get("description", "")[:80], "severity": r.get("severity", "INFO"),
            "location": r.get("location"), "source": f"PUBLIC · {r.get('reporter_name', 'Citizen')}", "status": r.get("status"),
            "created_at": r.get("created_at") or _iso_mins_ago(r.get("created_minutes_ago", 0)),
        })
    for n in notifications:
        feed.append({
            "kind": "NOTIFICATION", "id": n["id"], "title": n.get("title"), "severity": n.get("severity", "INFO"),
            "location": "Broadcast to all users", "source": "GOVERNMENT", "status": "VERIFIED",
            "message": n.get("message"),
            "created_at": n.get("created_at"),
        })
    for z in zones:
        feed.append({
            "kind": "EMERGENCY", "id": z["id"],
            "title": f"Emergency declared: {z.get('name')} ({z.get('radius_km')} km radius)",
            "severity": "CRITICAL", "location": z.get("name"), "source": "GOVERNMENT", "status": "VERIFIED",
            "message": z.get("message"),
            "created_at": z.get("created_at"),
        })
    env_events = await db.environment_events.find({}, {"_id": 0}).to_list(100)
    env = _current_environment(env_events)
    now_iso_env = datetime.now(timezone.utc).isoformat()
    for r in env["rain"]:
        if r["level"] == "HEAVY":
            feed.append({
                "kind": "WEATHER", "id": r["id"],
                "title": f"Heavy rainfall: {r['name']} ({r['intensity_mm_h']} mm/h)",
                "severity": "HIGH", "location": r["name"], "source": "AI/WEATHER", "status": "VERIFIED",
                "message": f"Active rain cell, ~{r['radius_km']} km radius. Roads in the area may degrade.",
                "created_at": now_iso_env,
            })
    for l in env["landslides"]:
        if l["probability"] >= 0.6:
            feed.append({
                "kind": "HAZARD", "id": l["id"],
                "title": f"Landslide watch: {l['name']} ({l['slide_type'].replace('_', ' ').title()}, {int(l['probability'] * 100)}%)",
                "severity": "HIGH", "location": l["name"], "source": "AI", "status": "VERIFIED",
                "created_at": now_iso_env,
            })
    for a in actions:
        feed.append({
            "kind": "GOVERNMENT_ACTION", "id": a["id"],
            "title": f"{a.get('official_name', 'Official')} set {a.get('target_name', a.get('target_id'))}: {a.get('old_state')} → {a.get('new_state')}",
            "severity": "GOV", "location": a.get("target_name"), "source": "GOVERNMENT", "status": "VERIFIED",
            "created_at": a.get("timestamp"),
        })
    feed.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return feed


@router.get("/public/advisories")
async def public_advisories(user: dict = Depends(get_current_user)):
    roads = await db.roads.find({"status": {"$nin": ["OPEN", "UNKNOWN"]}}, {"_id": 0}).to_list(200)
    incidents = await db.incidents.find({"status": "VERIFIED"}, {"_id": 0}).to_list(100)
    verified_reports = await db.field_reports.find({"status": "VERIFIED"}, {"_id": 0}).to_list(100)
    for i in incidents:
        if "created_at" not in i:
            i["created_at"] = _iso_mins_ago(i.get("created_minutes_ago", 0))
        i.pop("created_minutes_ago", None)
    for r in verified_reports:
        if "created_at" not in r:
            r["created_at"] = _iso_mins_ago(r.get("created_minutes_ago", 0))
        r.pop("created_minutes_ago", None)
    return {
        "provenance": "DEMO",
        "road_advisories": [
            {"id": r["id"], "name": r["name"], "district": r.get("district"), "status": r["status"],
             "reason": r.get("status_reason"), "expected_duration": r.get("expected_duration"),
             "updated_at": r.get("updated_at")}
            for r in roads
        ],
        "verified_incidents": incidents,
        "verified_field_reports": verified_reports,
    }
