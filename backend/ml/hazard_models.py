"""NER flood & landslide hazard models — NERIS prototype.

Deterministic, rule-based scoring calibrated to North Eastern Region (NER)
terrain characteristics (monsoon rainfall, steep Himalayan foothill slopes,
fragile geology, riverine floodplains). These are NOT statistically trained ML
models — no accuracy metric is claimed. Every output carries
provenance="PROTOTYPE_DEMO" so it is traceable end-to-end.
"""

MODEL_VERSION = "v0.1"

# Feature weights (sum = 1.0). Each feature is normalized to 0..1 before weighting.
FLOOD_WEIGHTS = {
    "rainfall_24h": 0.24,              # mm, normalized /150
    "rainfall_7d": 0.10,               # mm, normalized /400
    "soil_moisture": 0.14,             # 0..1 direct
    "low_elevation": 0.10,             # 1 - min(elev_m, 1500)/1500 (Brahmaputra plain ~50m, hills >1500m)
    "low_slope": 0.10,                 # 1 - min(slope_deg, 30)/30 (flat = water ponds)
    "proximity_to_river": 0.16,        # 1 - min(dist_m, 3000)/3000
    "historical_flood_frequency": 0.10,  # count /10
    "poor_drainage": 0.06,             # 0..1 direct
}

LANDSLIDE_WEIGHTS = {
    "slope": 0.24,                     # min(slope_deg, 45)/45
    "rainfall_24h": 0.18,              # mm /150
    "rainfall_7d": 0.08,               # mm /400
    "soil_moisture": 0.08,             # 0..1
    "fragile_geology": 0.14,           # 0..1 (young Himalayan strata = high)
    "low_vegetation": 0.06,            # 1 - vegetation_index
    "historical_landslide_frequency": 0.14,  # count /10
    "road_cut": 0.08,                  # 0..1 (cut-slope exposure along the road)
}


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _normalize(name, raw):
    v = raw.get(name)
    if name == "rainfall_24h":
        return _clamp((v or 0) / 150.0)
    if name == "rainfall_7d":
        return _clamp((v or 0) / 400.0)
    if name == "low_elevation":
        return 1.0 - _clamp((raw.get("elevation_m", 800)) / 1500.0)
    if name == "low_slope":
        return 1.0 - _clamp((raw.get("slope_deg", 10)) / 30.0)
    if name == "proximity_to_river":
        return 1.0 - _clamp((raw.get("distance_to_river_m", 3000)) / 3000.0)
    if name == "historical_flood_frequency":
        return _clamp((v or 0) / 10.0)
    if name == "historical_landslide_frequency":
        return _clamp((v or 0) / 10.0)
    if name == "slope":
        return _clamp((raw.get("slope_deg", 10)) / 45.0)
    if name == "low_vegetation":
        return 1.0 - _clamp(raw.get("vegetation_index", 0.5))
    # direct 0..1 features: soil_moisture, poor_drainage, fragile_geology, road_cut
    return _clamp(v if v is not None else 0.0)


def _risk_level(p):
    if p >= 0.75:
        return "CRITICAL"
    if p >= 0.55:
        return "HIGH"
    if p >= 0.30:
        return "MODERATE"
    return "LOW"


def _predict(model_name, weights, features, window_hours):
    contributions = {}
    for name, w in weights.items():
        contributions[name] = w * _normalize(name, features)
    total = sum(contributions.values())
    probability = _clamp(total, 0.02, 0.97)

    provided = sum(1 for n in weights if n in features or
                   (n in ("low_elevation",) and "elevation_m" in features) or
                   (n in ("low_slope", "slope") and "slope_deg" in features) or
                   (n == "proximity_to_river" and "distance_to_river_m" in features) or
                   (n == "low_vegetation" and "vegetation_index" in features))
    confidence = round(0.55 + 0.35 * (provided / len(weights)), 2)

    top = sorted(contributions.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_features = [
        {"name": n, "contribution": round(c / total, 2) if total > 0 else 0.0}
        for n, c in top
    ]

    return {
        "probability": round(probability, 2),
        "risk_level": _risk_level(probability),
        "confidence": confidence,
        "prediction_window_hours": window_hours,
        "top_features": top_features,
        "model_name": model_name,
        "model_version": MODEL_VERSION,
        "provenance": "PROTOTYPE_DEMO",
        "disclaimer": "Values are feature contributions to the model's output, not causal effects. Prototype scoring model — not a statistically trained model.",
    }


def predict_flood(features: dict, window_hours: int = 24) -> dict:
    out = _predict("ner-flood-rule", FLOOD_WEIGHTS, features, window_hours)
    out["flood_probability"] = out.pop("probability")
    return out


def predict_landslide(features: dict, window_hours: int = 24) -> dict:
    out = _predict("ner-landslide-rule", LANDSLIDE_WEIGHTS, features, window_hours)
    out["landslide_probability"] = out.pop("probability")
    return out


# Demo feature presets per seeded NER corridor (monsoon-season values, SIMULATED).
CORRIDOR_FEATURES = {
    "rd-nh27": {"flood": {"rainfall_24h": 88, "rainfall_7d": 210, "soil_moisture": 0.72, "elevation_m": 62, "slope_deg": 2, "distance_to_river_m": 900, "historical_flood_frequency": 6, "poor_drainage": 0.6},
                "landslide": {"slope_deg": 8, "rainfall_24h": 88, "rainfall_7d": 210, "soil_moisture": 0.72, "fragile_geology": 0.3, "vegetation_index": 0.55, "historical_landslide_frequency": 2, "road_cut": 0.35}},
    "rd-nh6": {"flood": {"rainfall_24h": 122, "rainfall_7d": 340, "soil_moisture": 0.85, "elevation_m": 140, "slope_deg": 6, "distance_to_river_m": 1400, "historical_flood_frequency": 4, "poor_drainage": 0.5},
               "landslide": {"slope_deg": 32, "rainfall_24h": 122, "rainfall_7d": 340, "soil_moisture": 0.85, "fragile_geology": 0.85, "vegetation_index": 0.35, "historical_landslide_frequency": 8, "road_cut": 0.9}},
    "rd-nh15": {"flood": {"rainfall_24h": 74, "rainfall_7d": 190, "soil_moisture": 0.68, "elevation_m": 78, "slope_deg": 3, "distance_to_river_m": 500, "historical_flood_frequency": 7, "poor_drainage": 0.55},
                "landslide": {"slope_deg": 10, "rainfall_24h": 74, "rainfall_7d": 190, "soil_moisture": 0.68, "fragile_geology": 0.35, "vegetation_index": 0.5, "historical_landslide_frequency": 3, "road_cut": 0.4}},
    "rd-nh17": {"flood": {"rainfall_24h": 40, "rainfall_7d": 120, "soil_moisture": 0.5, "elevation_m": 55, "slope_deg": 2, "distance_to_river_m": 1600, "historical_flood_frequency": 3, "poor_drainage": 0.4},
                "landslide": {"slope_deg": 5, "rainfall_24h": 40, "rainfall_7d": 120, "soil_moisture": 0.5, "fragile_geology": 0.25, "vegetation_index": 0.6, "historical_landslide_frequency": 1, "road_cut": 0.2}},
    "rd-nh715": {"flood": {"rainfall_24h": 45, "rainfall_7d": 130, "soil_moisture": 0.52, "elevation_m": 90, "slope_deg": 2, "distance_to_river_m": 2000, "historical_flood_frequency": 3, "poor_drainage": 0.35},
                 "landslide": {"slope_deg": 6, "rainfall_24h": 45, "rainfall_7d": 130, "soil_moisture": 0.52, "fragile_geology": 0.3, "vegetation_index": 0.6, "historical_landslide_frequency": 2, "road_cut": 0.25}},
    "rd-sh9": {"flood": {"rainfall_24h": 96, "rainfall_7d": 260, "soil_moisture": 0.78, "elevation_m": 25, "slope_deg": 1, "distance_to_river_m": 400, "historical_flood_frequency": 8, "poor_drainage": 0.7},
               "landslide": {"slope_deg": 18, "rainfall_24h": 96, "rainfall_7d": 260, "soil_moisture": 0.78, "fragile_geology": 0.6, "vegetation_index": 0.45, "historical_landslide_frequency": 5, "road_cut": 0.6}},
    "rd-nh29": {"flood": {"rainfall_24h": 68, "rainfall_7d": 180, "soil_moisture": 0.66, "elevation_m": 1450, "slope_deg": 14, "distance_to_river_m": 2600, "historical_flood_frequency": 2, "poor_drainage": 0.3},
                "landslide": {"slope_deg": 34, "rainfall_24h": 68, "rainfall_7d": 180, "soil_moisture": 0.66, "fragile_geology": 0.8, "vegetation_index": 0.4, "historical_landslide_frequency": 7, "road_cut": 0.85}},
    "rd-nh13": {"flood": {"rainfall_24h": 35, "rainfall_7d": 100, "soil_moisture": 0.45, "elevation_m": 400, "slope_deg": 8, "distance_to_river_m": 1800, "historical_flood_frequency": 2, "poor_drainage": 0.3},
                "landslide": {"slope_deg": 20, "rainfall_24h": 35, "rainfall_7d": 100, "soil_moisture": 0.45, "fragile_geology": 0.5, "vegetation_index": 0.55, "historical_landslide_frequency": 3, "road_cut": 0.45}},
    "rd-nh502": {"flood": {"rainfall_24h": 55, "rainfall_7d": 150, "soil_moisture": 0.6, "elevation_m": 1600, "slope_deg": 12, "distance_to_river_m": 2200, "historical_flood_frequency": 2, "poor_drainage": 0.35},
                 "landslide": {"slope_deg": 28, "rainfall_24h": 55, "rainfall_7d": 150, "soil_moisture": 0.6, "fragile_geology": 0.7, "vegetation_index": 0.4, "historical_landslide_frequency": 5, "road_cut": 0.7}},
    "rd-nh108": {"flood": {"rainfall_24h": 30, "rainfall_7d": 90, "soil_moisture": 0.42, "elevation_m": 40, "slope_deg": 2, "distance_to_river_m": 2500, "historical_flood_frequency": 2, "poor_drainage": 0.3},
                 "landslide": {"slope_deg": 4, "rainfall_24h": 30, "rainfall_7d": 90, "soil_moisture": 0.42, "fragile_geology": 0.2, "vegetation_index": 0.65, "historical_landslide_frequency": 1, "road_cut": 0.15}},
    "rd-nh15w": {"flood": {"rainfall_24h": 58, "rainfall_7d": 150, "soil_moisture": 0.6, "elevation_m": 58, "slope_deg": 2, "distance_to_river_m": 1100, "historical_flood_frequency": 5, "poor_drainage": 0.5},
                 "landslide": {"slope_deg": 5, "rainfall_24h": 58, "rainfall_7d": 150, "soil_moisture": 0.6, "fragile_geology": 0.25, "vegetation_index": 0.55, "historical_landslide_frequency": 1, "road_cut": 0.2}},
    "rd-nh27e": {"flood": {"rainfall_24h": 62, "rainfall_7d": 170, "soil_moisture": 0.62, "elevation_m": 130, "slope_deg": 5, "distance_to_river_m": 1300, "historical_flood_frequency": 4, "poor_drainage": 0.45},
                 "landslide": {"slope_deg": 15, "rainfall_24h": 62, "rainfall_7d": 170, "soil_moisture": 0.62, "fragile_geology": 0.45, "vegetation_index": 0.5, "historical_landslide_frequency": 3, "road_cut": 0.5}},
}
