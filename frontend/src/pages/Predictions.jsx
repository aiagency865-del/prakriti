import { useCallback, useEffect, useState } from "react";
import { CloudRain, Mountain, Info, Table2, Map as MapIcon } from "lucide-react";
import api from "@/lib/api";
import NavRail from "@/components/NavRail";
import PageHeader from "@/components/PageHeader";
import NerMap from "@/components/NerMap";

const RISK_COLORS = { LOW: "#1E8E3E", MODERATE: "#C77C00", HIGH: "#D9622B", CRITICAL: "#C4281C" };
const FEATURE_LABELS = {
  rainfall_24h: "Rainfall (24h)", rainfall_7d: "Rainfall (7d)", soil_moisture: "Soil moisture",
  low_elevation: "Low elevation", low_slope: "Flat terrain", slope: "Steep slope",
  proximity_to_river: "River proximity", historical_flood_frequency: "Flood history",
  historical_landslide_frequency: "Landslide history", poor_drainage: "Poor drainage",
  fragile_geology: "Fragile geology", low_vegetation: "Low vegetation", road_cut: "Road cut exposure",
};

export default function Predictions() {
  const [hazard, setHazard] = useState("flood");
  const [view, setView] = useState("table");
  const [data, setData] = useState(null);
  const [roads, setRoads] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async (h) => {
    setLoading(true);
    try {
      const { data: d } = await api.get(`/predictions/${h}`);
      setData(d);
    } catch (e) { /* keep last */ } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(hazard); }, [hazard, fetchAll]);

  useEffect(() => {
    api.get("/dashboard/summary").then((r) => setRoads(r.data.roads)).catch(() => {});
  }, []);

  const probKey = hazard === "flood" ? "flood_probability" : "landslide_probability";

  const bucketFor = (p) => (p >= 0.75 ? "BLOCKED" : p >= 0.55 ? "RESTRICTED" : p >= 0.3 ? "AT_RISK" : "OPEN");

  const hazardRoads = data && roads
    ? {
        type: "FeatureCollection",
        features: roads.features.map((f) => {
          const pred = data.predictions.find((p) => p.road_id === f.properties.id);
          return {
            ...f,
            properties: { ...f.properties, status: pred ? bucketFor(pred[probKey]) : "UNKNOWN" },
          };
        }),
      }
    : null;

  return (
    <div className="h-screen flex bg-[var(--surface-base)] overflow-hidden" data-testid="predictions-page">
      <NavRail />
      <div className="flex-1 flex flex-col min-w-0">
        <PageHeader title="HAZARD PREDICTIONS" chip={data ? `${data.provenance} · ${data.model_version}` : "…"} />

        <div className="flex-1 overflow-y-auto p-5">
          <div className="flex gap-1 p-1 bg-[var(--surface-sunken)] rounded-md w-fit mb-5" data-testid="predictions-tabs">
            {[
              { key: "flood", label: "Flood Risk", icon: CloudRain },
              { key: "landslide", label: "Landslide Risk", icon: Mountain },
            ].map((t) => (
              <button
                key={t.key}
                onClick={() => setHazard(t.key)}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-[5px] text-[12.5px] font-medium transition-colors ${
                  hazard === t.key ? "bg-white shadow-sm text-[var(--text-primary)]" : "text-neutral-500"
                }`}
                data-testid={`predictions-tab-${t.key}`}
              >
                <t.icon size={14} /> {t.label}
              </button>
            ))}
            <div className="w-px bg-[var(--border-default)] mx-1" />
            {[
              { key: "table", label: "Table", icon: Table2 },
              { key: "map", label: "Map", icon: MapIcon },
            ].map((t) => (
              <button
                key={t.key}
                onClick={() => setView(t.key)}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-[5px] text-[12.5px] font-medium transition-colors ${
                  view === t.key ? "bg-white shadow-sm text-[var(--text-primary)]" : "text-neutral-500"
                }`}
                data-testid={`predictions-view-${t.key}`}
              >
                <t.icon size={14} /> {t.label}
              </button>
            ))}
          </div>

          {view === "map" && (
            <div className="border hairline rounded-md overflow-hidden relative h-[520px]" data-testid="predictions-map">
              {hazardRoads ? (
                <NerMap
                  roads={hazardRoads}
                  vehicles={[]}
                  incidents={[]}
                  layers={{ roads: true, vehicles: false, incidents: false }}
                />
              ) : (
                <div className="absolute inset-0 bg-[var(--surface-sunken)] animate-pulse" />
              )}
              <div className="absolute bottom-3 left-3 bg-white/95 border hairline rounded-md shadow-sm px-3 py-2 z-10">
                <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                  {[
                    ["#1E8E3E", "Low (<30%)"], ["#C77C00", "Moderate (30–55%)"],
                    ["#D9622B", "High (55–75%)"], ["#C4281C", "Critical (≥75%)"],
                  ].map(([c, label]) => (
                    <div key={label} className="flex items-center gap-1.5 text-[10.5px] text-neutral-600">
                      <span className="w-4 h-[3px] rounded-full" style={{ background: c }} />
                      {label}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {view === "table" && (
          <div className="bg-white border hairline rounded-md overflow-hidden">
            <table className="w-full text-[13px]" data-testid="predictions-table">
              <thead>
                <tr className="border-b hairline text-left text-[10px] uppercase tracking-widest text-neutral-500">
                  <th className="px-4 py-3 font-semibold">Corridor</th>
                  <th className="px-4 py-3 font-semibold">District</th>
                  <th className="px-4 py-3 font-semibold w-56">Probability (24h)</th>
                  <th className="px-4 py-3 font-semibold">Risk</th>
                  <th className="px-4 py-3 font-semibold text-right">Conf.</th>
                  <th className="px-4 py-3 font-semibold">Top contributor</th>
                </tr>
              </thead>
              <tbody>
                {(!data || loading) && [1, 2, 3, 4].map((n) => (
                  <tr key={n} className="border-b hairline">
                    {[...Array(6)].map((_, i) => <td key={i} className="px-4 py-3"><div className="h-3.5 bg-[var(--surface-sunken)] rounded animate-pulse" /></td>)}
                  </tr>
                ))}
                {data && !loading && data.predictions.map((p) => {
                  const prob = p[probKey];
                  const color = RISK_COLORS[p.risk_level];
                  const top = p.top_features[0];
                  return (
                    <tr key={p.road_id} className="border-b hairline hover:bg-[var(--surface-base)]" data-testid={`prediction-row-${p.road_id}`}>
                      <td className="px-4 py-3 font-medium">{p.name}</td>
                      <td className="px-4 py-3 text-neutral-600">{p.district}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 bg-[var(--surface-sunken)] rounded-full overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${prob * 100}%`, background: color }} />
                          </div>
                          <span className="text-[12px] font-semibold tabular-nums w-10 text-right">{Math.round(prob * 100)}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded" style={{ background: `${color}14`, color }}>
                          {p.risk_level}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums text-neutral-600">{Math.round(p.confidence * 100)}%</td>
                      <td className="px-4 py-3 text-neutral-600">{top ? FEATURE_LABELS[top.name] || top.name : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          )}

          {data && (
            <div className="mt-5 p-4 border hairline rounded-md bg-white flex items-start gap-3" data-testid="predictions-model-card">
              <Info size={15} className="mt-0.5 flex-shrink-0 text-[var(--accent-primary)]" />
              <div className="text-[12px] text-neutral-600 leading-relaxed">
                <span className="font-medium text-[var(--text-primary)]">
                  Model: {hazard === "flood" ? "ner-flood-rule" : "ner-landslide-rule"} · {data.model_version}
                </span>
                {" "}— Prototype rule-based scoring calibrated to NER monsoon terrain (rainfall, slope, soil moisture, geology, river proximity, history).
                Not a statistically trained model; no accuracy metric is claimed. Contributions are model outputs, not causal effects.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
