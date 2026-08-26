import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from core.database import db
from core.security import TRIPS_MONITOR_ROLES, get_current_user
from core.ws import manager
from ml.hazard_models import CORRIDOR_FEATURES, predict_flood, predict_landslide
from services import _reroute_trips_on_road

router = APIRouter()

AI_ESCALATION_THRESHOLD = 0.75
AI_ESCALATION_WINDOW_MIN = 5


async def _evaluate_escalations():
    """Create pending escalations for corridors crossing the hazard threshold and
    auto-block roads whose escalation went unanswered for AI_ESCALATION_WINDOW_MIN minutes."""
    now = datetime.now(timezone.utc)
    roads = await db.roads.find({}, {"_id": 0}).to_list(1000)
    for r in roads:
        if r["status"] in ("BLOCKED", "GOVERNMENT_CLOSED"):
            continue
        feats = CORRIDOR_FEATURES.get(r["id"], {})
        if not feats:
            continue
        flood = predict_flood(feats.get("flood", {}))["flood_probability"]
        land = predict_landslide(feats.get("landslide", {}))["landslide_probability"]
        hazard, prob = ("FLOOD", flood) if flood >= land else ("LANDSLIDE", land)
        if prob >= AI_ESCALATION_THRESHOLD:
            recent = await db.ai_escalations.find_one({"road_id": r["id"], "status": {"$in": ["PENDING", "ACKED"]}})
            if not recent:
                esc = {
                    "id": f"ESC-{uuid.uuid4().hex[:6].upper()}",
                    "road_id": r["id"], "road_name": r["name"], "hazard": hazard,
                    "probability": prob, "status": "PENDING",
                    "created_at": now.isoformat(),
                    "deadline_at": (now + timedelta(minutes=AI_ESCALATION_WINDOW_MIN)).isoformat(),
                }
                await db.ai_escalations.insert_one({**esc})
                esc.pop("_id", None)
                await manager.broadcast({
                    "type": "AI_ESCALATION", "id": esc["id"], "road_name": esc["road_name"],
                    "hazard": hazard, "probability": prob, "deadline_at": esc["deadline_at"],
                })
    # sweep: auto-block expired pending escalations
    expired = await db.ai_escalations.find({"status": "PENDING"}).to_list(50)
    for e in expired:
        try:
            deadline = datetime.fromisoformat(e["deadline_at"])
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if deadline <= now:
            now_iso = now.isoformat()
            road = await db.roads.find_one({"id": e["road_id"]}, {"_id": 0})
            if road and road["status"] not in ("BLOCKED", "GOVERNMENT_CLOSED"):
                reason = f"Auto-blocked: AI {e['hazard'].lower()} risk {int(e['probability'] * 100)}% unanswered for {AI_ESCALATION_WINDOW_MIN} min"
                await db.roads.update_one({"id": e["road_id"]}, {"$set": {
                    "status": "BLOCKED", "status_reason": reason,
                    "updated_at": now_iso, "updated_by": "neris-ai",
                }})
                await db.government_actions.insert_one({
                    "id": str(uuid.uuid4()), "official_id": "neris-ai", "official_email": "ai@neris.system",
                    "official_name": "NERIS AI", "action_type": "ROAD_AUTO_BLOCKED", "target_type": "road",
                    "target_id": e["road_id"], "target_name": e["road_name"],
                    "old_state": road["status"], "new_state": "BLOCKED", "reason": reason, "timestamp": now_iso,
                })
                await manager.broadcast({"type": "ROAD_STATUS_CHANGED", "road_id": e["road_id"], "status": "BLOCKED", "road_name": e["road_name"]})
                await _reroute_trips_on_road(e["road_id"], e["road_name"], "BLOCKED")
            await db.ai_escalations.update_one({"id": e["id"]}, {"$set": {"status": "AUTO_BLOCKED"}})


@router.get("/ai/escalations")
async def list_escalations(user: dict = Depends(get_current_user)):
    if user["role"] not in TRIPS_MONITOR_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    await _evaluate_escalations()
    rows = await db.ai_escalations.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"threshold": AI_ESCALATION_THRESHOLD, "window_minutes": AI_ESCALATION_WINDOW_MIN, "escalations": rows}


class EscalationAck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: str


@router.post("/ai/escalations/{esc_id}/ack")
async def ack_escalation(esc_id: str, body: EscalationAck, user: dict = Depends(get_current_user)):
    if user["role"] not in TRIPS_MONITOR_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    esc = await db.ai_escalations.find_one({"id": esc_id})
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if esc["status"] != "PENDING":
        raise HTTPException(status_code=400, detail=f"Escalation already handled ({esc['status']})")
    now_iso = datetime.now(timezone.utc).isoformat()
    if body.action == "BLOCK_NOW":
        reason = f"Blocked by {user.get('name')}: AI {esc['hazard'].lower()} risk {int(esc['probability'] * 100)}%"
        road = await db.roads.find_one({"id": esc["road_id"]}, {"_id": 0})
        if road:
            await db.roads.update_one({"id": esc["road_id"]}, {"$set": {
                "status": "BLOCKED", "status_reason": reason, "updated_at": now_iso, "updated_by": user["email"],
            }})
            await db.government_actions.insert_one({
                "id": str(uuid.uuid4()), "official_id": user["id"], "official_email": user["email"],
                "official_name": user.get("name"), "action_type": "ROAD_STATUS_CHANGE", "target_type": "road",
                "target_id": esc["road_id"], "target_name": esc["road_name"],
                "old_state": road["status"], "new_state": "BLOCKED", "reason": reason, "timestamp": now_iso,
            })
            await manager.broadcast({"type": "ROAD_STATUS_CHANGED", "road_id": esc["road_id"], "status": "BLOCKED", "road_name": esc["road_name"]})
            await _reroute_trips_on_road(esc["road_id"], esc["road_name"], "BLOCKED")
        await db.ai_escalations.update_one({"id": esc_id}, {"$set": {"status": "BLOCKED_MANUAL", "acked_by": user["email"], "acked_at": now_iso}})
        return {"id": esc_id, "status": "BLOCKED_MANUAL"}
    if body.action == "MONITOR":
        await db.ai_escalations.update_one({"id": esc_id}, {"$set": {"status": "ACKED", "acked_by": user["email"], "acked_at": now_iso}})
        return {"id": esc_id, "status": "ACKED"}
    raise HTTPException(status_code=400, detail="action must be MONITOR or BLOCK_NOW")
