from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from core.database import db
from core.security import get_current_user
from ml.hazard_models import CORRIDOR_FEATURES, MODEL_VERSION, predict_flood, predict_landslide

router = APIRouter()


class HazardFeatures(BaseModel):
    model_config = ConfigDict(extra="allow")
    prediction_window_hours: int = 24


@router.post("/ml/flood/predict")
async def ml_flood_predict(body: HazardFeatures, user: dict = Depends(get_current_user)):
    feats = body.model_dump(exclude={"prediction_window_hours"})
    return predict_flood(feats, body.prediction_window_hours)


@router.post("/ml/landslide/predict")
async def ml_landslide_predict(body: HazardFeatures, user: dict = Depends(get_current_user)):
    feats = body.model_dump(exclude={"prediction_window_hours"})
    return predict_landslide(feats, body.prediction_window_hours)


@router.get("/predictions/{hazard}")
async def corridor_predictions(hazard: str, user: dict = Depends(get_current_user)):
    if hazard not in ("flood", "landslide"):
        raise HTTPException(status_code=404, detail="Unknown hazard. Use flood or landslide.")
    fn = predict_flood if hazard == "flood" else predict_landslide
    roads = await db.roads.find({}, {"_id": 0}).to_list(1000)
    out = []
    for r in roads:
        feats = CORRIDOR_FEATURES.get(r["id"], {}).get(hazard, {})
        pred = fn(feats)
        out.append({
            "road_id": r["id"],
            "name": r.get("name"),
            "district": r.get("district"),
            "status": r.get("status"),
            **pred,
        })
    out.sort(key=lambda x: x.get("flood_probability", x.get("landslide_probability", 0)), reverse=True)
    return {
        "hazard": hazard,
        "model_version": MODEL_VERSION,
        "provenance": "PROTOTYPE_DEMO",
        "predictions": out,
    }
