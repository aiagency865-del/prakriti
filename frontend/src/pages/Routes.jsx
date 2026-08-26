import { useCallback, useEffect, useRef, useState } from "react";
import { Search, Loader2, Check, X, AlertOctagon, Bike, Car, Truck, Ambulance } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import api, { formatApiErrorDetail } from "@/lib/api";
import { ensureWS, subscribeWS } from "@/lib/ws";
import NavRail from "@/components/NavRail";
import NerMap, { STATUS_COLORS } from "@/components/NerMap";
import EmergencyBanner from "@/components/EmergencyBanner";

const VEHICLE_TYPES = [
  { key: "TWO_WHEELER", label: "2W", icon: Bike },
  { key: "LIGHT", label: "Light", icon: Car },
  { key: "SUV", label: "SUV", icon: Car },
  { key: "TRUCK", label: "Truck", icon: Truck },
  { key: "EMERGENCY", label: "Emergency", icon: Ambulance },
];

function fmtEta(mins) {
  if (mins == null) return "—";
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return h > 0 ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
}

function riskBand(score) {
  if (score >= 60) return { label: "HIGH", color: "#C4281C" };
  if (score >= 30) return { label: "MODERATE", color: "#C77C00" };
  return { label: "LOW", color: "#1E8E3E" };
}

export default function Routes() {
  const [params] = useSearchParams();
  const [places, setPlaces] = useState([]);
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [vehicleType, setVehicleType] = useState("TRUCK");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [roads, setRoads] = useState(null);
  const [zones, setZones] = useState([]);
  const [environment, setEnvironment] = useState(null);
  const lastQuery = useRef(null);

  useEffect(() => {
    api.get("/routes/places").then((r) => setPlaces(r.data)).catch(() => {});
  }, []);

  // Prefill + auto-calculate from query params (e.g. from a trip's "View on map")
  useEffect(() => {
    const o = params.get("origin");
    const d = params.get("destination");
    if (o && d) {
      setOrigin(o);
      setDestination(d);
      const q = { origin: o.toLowerCase(), destination: d.toLowerCase(), vehicle_type: vehicleType };
      lastQuery.current = q;
      calculate(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Live road state — government changes propagate here every 10s
  useEffect(() => {
    const fetchRoads = async () => {
      try {
        const [{ data: d }, { data: z }, { data: env }] = await Promise.all([
          api.get("/dashboard/summary"),
          api.get("/emergency-zones"),
          api.get("/environment"),
        ]);
        setRoads(d.roads);
        setZones(z);
        setEnvironment(env);
      } catch (e) { /* keep last known state */ }
    };
    fetchRoads();
    const t = setInterval(fetchRoads, 10000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    ensureWS();
    const unsub = subscribeWS((msg) => {
      if (["ROAD_STATUS_CHANGED", "EMERGENCY_DECLARED", "EMERGENCY_ENDED"].includes(msg.type)) {
        api.get("/dashboard/summary").then((r) => setRoads(r.data.roads)).catch(() => {});
        api.get("/emergency-zones").then((r) => setZones(r.data)).catch(() => {});
      }
    });
    return unsub;
  }, []);

  const calculate = useCallback(async (q) => {
    const query = q || { origin, destination, vehicle_type: vehicleType };
    if (!query.origin || !query.destination) return;
    setLoading(true);
    setError("");
    try {
      const { data } = await api.post("/routes/calculate", query);
      setResult(data);
    } catch (e) {
      setError(formatApiErrorDetail(e.response?.data?.detail) || "Unable to calculate route. Please retry.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [origin, destination, vehicleType]);

  // Re-calculate whenever live road state changes (gov status change → route colors update)
  useEffect(() => {
    if (roads && lastQuery.current) calculate(lastQuery.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roads]);

  const onSubmit = (e) => {
    e.preventDefault();
    const q = { origin: origin.trim().toLowerCase(), destination: destination.trim().toLowerCase(), vehicle_type: vehicleType };
    lastQuery.current = q;
    calculate(q);
  };

  const routeGeoJSON = result
    ? {
        type: "FeatureCollection",
        features: [
          { type: "Feature", geometry: { type: "LineString", coordinates: result.recommended_route.polyline }, properties: { status: "MAIN", name: "Route" } },
          ...result.recommended_route.segments
            .filter((s) => !["OPEN", "LOCAL"].includes(s.status))
            .map((s) => ({ type: "Feature", geometry: s.geometry, properties: { status: s.status, name: s.name } })),
        ],
      }
    : null;

  const altGeoJSON = result?.alternative_route
    ? {
        type: "FeatureCollection",
        features: result.alternative_route.segments.map((s) => ({
          type: "Feature", geometry: s.geometry, properties: { status: s.status, name: s.name },
        })),
      }
    : null;

  const rr = result?.recommended_route;
  const band = rr ? riskBand(rr.risk_score) : null;

  return (
    <div className="h-screen flex bg-[var(--surface-base)] overflow-hidden" data-testid="routes-page">
      <NavRail />
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 flex-shrink-0 bg-white border-b hairline px-5 flex items-center justify-between">
          <h1 className="text-[15px] font-semibold tracking-tight">ROUTE CALCULATION</h1>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full border hairline text-neutral-500">LIVE ROAD STATE · DEMO ROUTING</span>
        </header>

        <EmergencyBanner zones={zones} />

        <div className="flex-1 flex min-h-0">
          {/* Left: form + results */}
          <div className="w-[380px] flex-shrink-0 bg-white border-r hairline overflow-y-auto p-5">
            <form onSubmit={onSubmit} className="space-y-4" data-testid="route-form">
              <div>
                <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">From</label>
                <input
                  list="ner-places"
                  value={origin}
                  onChange={(e) => setOrigin(e.target.value)}
                  placeholder="e.g. Guwahati"
                  required
                  className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] focus:border-[var(--accent-primary)] outline-none capitalize"
                  data-testid="route-origin-input"
                />
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">To</label>
                <input
                  list="ner-places"
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  placeholder="e.g. Tezpur"
                  required
                  className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] focus:border-[var(--accent-primary)] outline-none capitalize"
                  data-testid="route-destination-input"
                />
                <datalist id="ner-places">
                  {places.map((p) => <option key={p} value={p} className="capitalize" />)}
                </datalist>
              </div>

              <div>
                <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Vehicle type</label>
                <div className="mt-1.5 grid grid-cols-5 gap-1 p-1 bg-[var(--surface-sunken)] rounded-md" data-testid="route-vehicle-types">
                  {VEHICLE_TYPES.map((t) => (
                    <button
                      key={t.key}
                      type="button"
                      onClick={() => setVehicleType(t.key)}
                      className={`flex flex-col items-center gap-0.5 py-1.5 rounded-[5px] text-[10px] font-medium transition-colors ${
                        vehicleType === t.key ? "bg-white shadow-sm text-[var(--accent-primary)]" : "text-neutral-500"
                      }`}
                      data-testid={`route-vehicle-${t.key.toLowerCase()}`}
                    >
                      <t.icon size={14} /> {t.label}
                    </button>
                  ))}
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full h-10 rounded-md bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] disabled:opacity-60 text-white text-[13px] font-medium flex items-center justify-center gap-2 transition-colors"
                data-testid="route-calculate-button"
              >
                {loading ? <Loader2 size={15} className="animate-spin" /> : <Search size={15} />}
                {loading ? "Calculating…" : "Calculate Route"}
              </button>
            </form>

            {error && (
              <div className="mt-4 p-3 border rounded-md bg-red-50 border-red-200 text-red-800 text-[12px]" data-testid="route-error">{error}</div>
            )}

            {!result && !error && !loading && (
              <div className="mt-8 text-center text-[13px] text-neutral-500" data-testid="route-empty-state">
                Enter an origin and destination to calculate a route.
              </div>
            )}

            {result && rr && (
              <div className="mt-5 space-y-4" data-testid="route-result">
                {rr.contains_blocked && (
                  <div className="p-3 border rounded-md bg-red-50 border-red-300 text-red-900 text-[12px] flex items-start gap-2" data-testid="route-blocked-banner">
                    <AlertOctagon size={15} className="mt-0.5 flex-shrink-0" />
                    <div>
                      <div className="font-semibold">Government-blocked road on this corridor</div>
                      <div className="mt-0.5">{rr.blocked_roads.join(", ")} — segment shown in red. No safe alternative exists on the monitored network.</div>
                    </div>
                  </div>
                )}

                <div className="border hairline rounded-md p-4 bg-[var(--surface-base)]">
                  <div className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Recommended route</div>
                  <div className="mt-2 flex items-end justify-between">
                    <div>
                      <div className="text-2xl font-semibold tabular-nums" data-testid="route-eta">{fmtEta(rr.eta_minutes)}</div>
                      <div className="text-[11px] text-neutral-500 tabular-nums">{rr.distance_km} km</div>
                    </div>
                    <span
                      className="text-[10px] font-semibold uppercase tracking-wider px-2 py-1 rounded"
                      style={{ background: `${band.color}14`, color: band.color }}
                      data-testid="route-risk-chip"
                    >
                      Risk {band.label} · {rr.risk_score}
                    </span>
                  </div>
                </div>

                <div>
                  <div className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold mb-2">Why selected</div>
                  <div className="space-y-1.5">
                    {result.reason.map((r, i) => (
                      <div key={i} className="flex items-start gap-2 text-[12px] text-neutral-700">
                        <Check size={13} className="mt-0.5 flex-shrink-0" style={{ color: "#1E8E3E" }} />
                        {r}
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold mb-2">Monitored corridors on route</div>
                  <div className="space-y-1.5" data-testid="route-segments">
                    {rr.segments.length === 0 && (
                      <div className="text-[12px] text-neutral-500 py-2" data-testid="route-segments-empty">No monitored corridors crossed — clear route.</div>
                    )}
                    {rr.segments.map((s) => (
                      <div key={s.road_id} className="flex items-center gap-2.5 p-2.5 border hairline rounded-md text-[12px]" data-testid={`route-segment-${s.road_id}`}>
                        <span className="w-6 h-[4px] rounded-full flex-shrink-0" style={{ background: s.status === "LOCAL" ? "#64748B" : (s.status === "OPEN" ? "#1A73E8" : STATUS_COLORS[s.status] || STATUS_COLORS.UNKNOWN) }} />
                        <span className="font-medium truncate">{s.name}</span>
                        {s.status === "LOCAL" && <span className="text-[9px] uppercase tracking-wider text-neutral-400 flex-shrink-0">unverified</span>}
                        <span className="ml-auto text-neutral-500 tabular-nums flex-shrink-0">{s.distance_km} km</span>
                      </div>
                    ))}
                  </div>
                </div>

                {result.alternative_route && (
                  <div className="border hairline rounded-md p-4" data-testid="route-alternative">
                    <div className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Alternative (rejected)</div>
                    <div className="mt-2 flex items-end justify-between">
                      <div>
                        <div className="text-lg font-semibold tabular-nums">{fmtEta(result.alternative_route.eta_minutes)}</div>
                        <div className="text-[11px] text-neutral-500 tabular-nums">{result.alternative_route.distance_km} km</div>
                      </div>
                      <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-1 rounded bg-red-50 text-red-800">
                        Risk {result.alternative_route.risk_score}
                      </span>
                    </div>
                    <div className="mt-2 space-y-1">
                      {result.alternative_route.rejected_because.map((r, i) => (
                        <div key={i} className="flex items-start gap-2 text-[12px] text-neutral-600">
                          <X size={13} className="mt-0.5 flex-shrink-0 text-red-700" />
                          {r}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right: map */}
          <div className="flex-1 relative min-w-0">
            <NerMap
              roads={roads}
              vehicles={[]}
              incidents={[]}
              layers={{ roads: true, vehicles: false, incidents: false }}
              route={routeGeoJSON}
              zones={zones}
              environment={environment}
              endpoints={result ? [
                { lng: result.origin.lng, lat: result.origin.lat, label: "A" },
                { lng: result.destination.lng, lat: result.destination.lat, label: "B" },
              ] : []}
            />
            <div className="absolute bottom-3 left-3 bg-white/95 border hairline rounded-md shadow-sm px-3 py-2 z-10" data-testid="routes-map-legend">
              <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                {[
                  ["OPEN", "Open"], ["AT_RISK", "At Risk"], ["RESTRICTED", "Restricted"],
                  ["BLOCKED", "Blocked"], ["GOVERNMENT_CLOSED", "Gov Closed"], ["UNKNOWN", "Unknown"],
                ].map(([k, label]) => (
                  <div key={k} className="flex items-center gap-1.5 text-[10.5px] text-neutral-600">
                    <span className="w-4 h-[3px] rounded-full" style={{ background: STATUS_COLORS[k] }} />
                    {label}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
