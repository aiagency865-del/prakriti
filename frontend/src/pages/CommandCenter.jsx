import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { toast } from "sonner";
import { formatApiErrorDetail } from "@/lib/api";
import NavRail from "@/components/NavRail";
import NerMap, { STATUS_COLORS } from "@/components/NerMap";
import RoadControlDrawer from "@/components/RoadControlDrawer";
import EmergencyBanner from "@/components/EmergencyBanner";
import EmergencyZoneModal from "@/components/EmergencyZoneModal";
import { useAuth } from "@/context/AuthContext";
import {
  Mountain, CloudRain, Wrench, Car, CloudLightning, HelpCircle,
  Pill, Wheat, Droplets, Fuel, Truck, ShieldAlert, CircleAlert, Layers, AlertOctagon,
} from "lucide-react";

const SEVERITY_COLORS = { INFO: "#4C7EA8", WARNING: "#C77C00", HIGH: "#D9622B", CRITICAL: "#C4281C" };
const TYPE_ICONS = {
  LANDSLIDE: Mountain, FLOOD: CloudRain, ROAD_DAMAGE: Wrench, BRIDGE_DAMAGE: Wrench,
  ACCIDENT: Car, TRAFFIC: Car, WEATHER: CloudLightning, UNKNOWN: HelpCircle,
};
const COMMODITY_ICONS = { MEDICINE: Pill, FOOD: Wheat, WATER: Droplets, FUEL: Fuel };

const KPIS = [
  { key: "active_vehicles", label: "Active Vehicles", testId: "kpi-active-vehicles" },
  { key: "at_risk_corridors", label: "At-Risk Corridors", testId: "kpi-at-risk-corridors" },
  { key: "blocked_roads", label: "Blocked Roads", testId: "kpi-blocked-roads" },
  { key: "critical_alerts", label: "Critical Alerts", testId: "kpi-critical-alerts" },
  { key: "villages_isolation_risk", label: "Villages at Isolation Risk", testId: "kpi-villages-isolation" },
  { key: "critical_supply_locations", label: "Critical Supply Locations", testId: "kpi-critical-supply" },
];

function timeAgo(iso, now) {
  if (!iso) return "—";
  const diff = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 1000));
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

const GOV_ROLES = ["SUPER_ADMIN", "GOVERNMENT_ADMIN", "GOVERNMENT_OFFICER", "DISTRICT_OFFICER"];

export default function CommandCenter() {
  const { user } = useAuth();
  const isGov = user && GOV_ROLES.includes(user.role);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [lastFetch, setLastFetch] = useState(null);
  const [now, setNow] = useState(Date.now());
  const [layers, setLayers] = useState({ roads: true, vehicles: true, incidents: true });
  const [selectedRoad, setSelectedRoad] = useState(null);
  const [zones, setZones] = useState([]);
  const [environment, setEnvironment] = useState(null);
  const [emergencyOpen, setEmergencyOpen] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [{ data: d }, { data: z }, { data: env }] = await Promise.all([
        api.get("/dashboard/summary"),
        api.get("/emergency-zones"),
        api.get("/environment"),
      ]);
      setData(d);
      setZones(z);
      setEnvironment(env);
      setError("");
      setLastFetch(Date.now());
    } catch (e) {
      setError("Live updates paused. Data shown may be outdated.");
    }
  }, []);

  const incidentAction = useCallback(async (id, action) => {
    try {
      await api.patch(`/incidents/${id}/${action}`);
      toast.success(action === "verify" ? "Incident verified — broadcast to all roles" : "Incident rejected");
      fetchAll();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Action failed");
    }
  }, [fetchAll]);

  useEffect(() => {
    fetchAll();
    const poll = setInterval(fetchAll, 10000);
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => { clearInterval(poll); clearInterval(tick); };
  }, [fetchAll]);

  const connected = !error;

  return (
    <div className="h-screen flex bg-[var(--surface-base)] overflow-hidden" data-testid="command-center">
      <NavRail />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Page top bar */}
        <header className="h-14 flex-shrink-0 bg-white border-b hairline px-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-[15px] font-semibold tracking-tight" data-testid="cc-title">
              NER LOGISTICS INTELLIGENCE CENTER
            </h1>
            <span className="hidden md:inline-flex items-center px-2 py-0.5 rounded-full border hairline text-[10px] font-mono text-neutral-500">
              DEMO DATA
            </span>
          </div>
          <div className="flex items-center gap-3">
            {isGov && (
              <button
                onClick={() => setEmergencyOpen(true)}
                className="h-8 px-3 rounded-md border border-[#8A1512] text-[#8A1512] hover:bg-red-50 text-[12px] font-medium flex items-center gap-1.5 transition-colors"
                data-testid="declare-emergency-button"
              >
                <AlertOctagon size={13} /> Declare Emergency
              </button>
            )}
          </div>
          <div className="flex items-center gap-2 text-[12px]" data-testid="cc-live-indicator">
            {connected ? (
              <>
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-60" style={{ background: "#1E8E3E" }} />
                  <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: "#1E8E3E" }} />
                </span>
                <span className="text-neutral-600">
                  Live · Last updated {lastFetch ? `${Math.max(0, Math.floor((now - lastFetch) / 1000))}s ago` : "—"}
                </span>
              </>
            ) : (
              <>
                <span className="status-dot" style={{ background: "#8A9099" }} />
                <span className="text-neutral-500">Reconnecting…</span>
              </>
            )}
          </div>
        </header>

        <EmergencyBanner zones={zones} onChanged={fetchAll} />

        {error && (
          <div className="flex-shrink-0 bg-amber-50 border-b border-amber-200 px-5 py-2 text-[12px] text-amber-800 flex items-center justify-between" data-testid="cc-offline-banner">
            <span>{error}</span>
            <button onClick={fetchAll} className="underline underline-offset-2" data-testid="cc-retry-button">Retry</button>
          </div>
        )}

        {/* KPI strip */}
        <div className="flex-shrink-0 grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 border-b hairline bg-white" data-testid="cc-kpi-strip">
          {KPIS.map((k, idx) => (
            <div
              key={k.key}
              data-testid={k.testId}
              className={`px-4 py-3 ${idx > 0 ? "border-l hairline" : ""} hover:bg-[var(--surface-base)] transition-colors`}
            >
              <div className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold truncate">{k.label}</div>
              <div className="mt-1 text-2xl font-semibold tabular-nums text-[var(--text-primary)]">
                {data ? data.kpis[k.key] : <span className="inline-block w-8 h-6 bg-[var(--surface-sunken)] rounded animate-pulse" />}
              </div>
            </div>
          ))}
        </div>

        {/* Main: map + incidents */}
        <div className="flex-1 flex min-h-0">
          {/* Map zone */}
          <div className="flex-1 relative min-w-0">
            {data ? (
              <NerMap
                roads={data.roads}
                vehicles={data.vehicles}
                incidents={data.incidents.filter((i) => i.status !== "RESOLVED")}
                layers={layers}
                onRoadClick={(props) => setSelectedRoad(props)}
                zones={zones}
                environment={environment}
              />
            ) : (
              <div className="absolute inset-0 bg-[var(--surface-sunken)] animate-pulse" data-testid="cc-map-skeleton" />
            )}

            {/* Layer toggles */}
            <div className="absolute top-3 right-3 bg-white border hairline rounded-md shadow-sm p-2.5 w-44 z-10" data-testid="cc-layer-control">
              <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-neutral-500 font-semibold mb-2">
                <Layers size={12} /> Layers
              </div>
              {[
                { key: "roads", label: "Road Status" },
                { key: "vehicles", label: "Vehicles" },
                { key: "incidents", label: "Incidents" },
              ].map((l) => (
                <label key={l.key} className="flex items-center gap-2 py-1 text-[12px] text-neutral-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={layers[l.key]}
                    onChange={(e) => setLayers((s) => ({ ...s, [l.key]: e.target.checked }))}
                    className="w-3.5 h-3.5 accent-[var(--accent-primary)]"
                    data-testid={`layer-toggle-${l.key}`}
                  />
                  {l.label}
                </label>
              ))}
            </div>

            {/* Legend */}
            <div className="absolute bottom-3 left-3 bg-white/95 border hairline rounded-md shadow-sm px-3 py-2 z-10" data-testid="cc-map-legend">
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
                <div className="flex items-center gap-1.5 text-[10.5px] text-neutral-600">
                  <span className="w-4 h-[3px] rounded-full" style={{ background: "#2563EB" }} />
                  Rain cell
                </div>
                <div className="flex items-center gap-1.5 text-[10.5px] text-neutral-600">
                  <span style={{ width: 0, height: 0, borderLeft: "5px solid transparent", borderRight: "5px solid transparent", borderBottom: "9px solid #D9622B" }} />
                  Landslide watch
                </div>
              </div>
            </div>
          </div>

          {/* Live incidents panel */}
          <aside className="w-80 flex-shrink-0 bg-white border-l hairline flex flex-col min-h-0" data-testid="cc-incidents-panel">
            <div className="px-4 py-3 border-b hairline flex items-center justify-between">
              <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold">Live Incidents</div>
              {data && (
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--surface-sunken)] text-neutral-600" data-testid="cc-incidents-count">
                  {data.incidents.filter((i) => i.status !== "RESOLVED").length} ACTIVE
                </span>
              )}
            </div>
            <div className="flex-1 overflow-y-auto">
              {!data && [1, 2, 3, 4, 5].map((n) => (
                <div key={n} className="px-4 py-3 border-b hairline">
                  <div className="h-3 w-2/3 bg-[var(--surface-sunken)] rounded animate-pulse mb-2" />
                  <div className="h-2.5 w-1/2 bg-[var(--surface-sunken)] rounded animate-pulse" />
                </div>
              ))}
              {data && data.incidents.filter((i) => i.status !== "RESOLVED").length === 0 && (
                <div className="px-4 py-10 text-center text-[13px] text-neutral-500" data-testid="cc-incidents-empty">
                  No active incidents — all monitored corridors are currently operating normally.
                </div>
              )}
              {data && data.incidents.filter((i) => i.status !== "RESOLVED").map((inc) => {
                const Icon = TYPE_ICONS[inc.type] || HelpCircle;
                return (
                  <div
                    key={inc.id}
                    data-testid={`incident-row-${inc.id}`}
                    className="w-full text-left px-4 py-3 border-b hairline hover:bg-[var(--surface-base)] transition-colors"
                    style={{ borderLeft: `3px solid ${SEVERITY_COLORS[inc.severity] || "#8A9099"}` }}
                  >
                    <div className="flex items-start gap-2.5">
                      <span
                        className="mt-0.5 w-6 h-6 rounded-sm flex items-center justify-center flex-shrink-0"
                        style={{ background: `${SEVERITY_COLORS[inc.severity]}14`, color: SEVERITY_COLORS[inc.severity] }}
                      >
                        <Icon size={14} strokeWidth={1.75} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <div className="text-[13px] font-medium text-[var(--text-primary)] truncate">{inc.title}</div>
                          <div className="text-[10px] font-mono text-neutral-400 flex-shrink-0">{timeAgo(inc.created_at, now)}</div>
                        </div>
                        <div className="text-[11.5px] text-neutral-500 truncate mt-0.5">{inc.location}</div>
                        <div className="flex items-center gap-2 mt-1.5">
                          <span
                            className="text-[9.5px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded"
                            style={{ background: `${SEVERITY_COLORS[inc.severity]}14`, color: SEVERITY_COLORS[inc.severity] }}
                          >
                            {inc.severity}
                          </span>
                          <span className="text-[10px] text-neutral-500 font-mono">{inc.source}</span>
                          <span className="text-[10px] text-neutral-500 tabular-nums ml-auto">{inc.confidence}% conf.</span>
                        </div>
                        {isGov && inc.status === "UNVERIFIED" && (
                          <div className="flex gap-2 mt-2" data-testid={`cc-review-${inc.id}`}>
                            <button
                              onClick={() => incidentAction(inc.id, "verify")}
                              className="h-7 px-2.5 rounded-md text-[11px] font-medium bg-green-700 hover:bg-green-800 text-white transition-colors"
                              data-testid={`cc-verify-${inc.id}`}
                            >
                              Verify & broadcast
                            </button>
                            <button
                              onClick={() => incidentAction(inc.id, "reject")}
                              className="h-7 px-2.5 rounded-md border hairline text-[11px] font-medium text-neutral-600 hover:bg-red-50 hover:text-red-700 transition-colors"
                              data-testid={`cc-reject-${inc.id}`}
                            >
                              Reject
                            </button>
                          </div>
                        )}
                        {inc.status === "VERIFIED" && (
                          <div className="mt-1.5 text-[10px] font-semibold text-green-700 uppercase tracking-wider">Verified · broadcast to all</div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </aside>
        </div>

        {/* Supply risk strip */}
        <div className="flex-shrink-0 bg-white border-t hairline" data-testid="cc-supply-strip">
          <div className="px-5 pt-2.5 pb-1 flex items-center justify-between">
            <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold flex items-center gap-1.5">
              <ShieldAlert size={13} /> Supply Risk
            </div>
            <Link to="/supply" className="text-[11px] text-[var(--accent-primary)] hover:underline" data-testid="cc-supply-view-all">
              View supply intelligence →
            </Link>
          </div>
          <div className="px-5 pb-3 flex gap-3 overflow-x-auto">
            {!data && [1, 2, 3, 4].map((n) => (
              <div key={n} className="w-52 h-16 flex-shrink-0 bg-[var(--surface-sunken)] rounded-md animate-pulse" />
            ))}
            {data && data.supply.length === 0 && (
              <div className="text-[12px] text-neutral-500 py-3" data-testid="cc-supply-empty">No supply risks detected</div>
            )}
            {data && data.supply.map((s) => {
              const Icon = COMMODITY_ICONS[s.commodity] || Truck;
              return (
                <Link
                  key={s.commodity}
                  to="/supply"
                  data-testid={`supply-card-${s.commodity.toLowerCase()}`}
                  className="flex-shrink-0 w-56 border hairline rounded-md px-3 py-2.5 hover:bg-[var(--surface-base)] transition-colors flex items-center gap-3"
                  style={{ borderLeft: `3px solid ${SEVERITY_COLORS[s.severity]}` }}
                >
                  <span
                    className="w-8 h-8 rounded-sm flex items-center justify-center flex-shrink-0"
                    style={{ background: `${SEVERITY_COLORS[s.severity]}14`, color: SEVERITY_COLORS[s.severity] }}
                  >
                    <Icon size={16} strokeWidth={1.75} />
                  </span>
                  <div className="min-w-0">
                    <div className="text-[12px] font-semibold text-[var(--text-primary)] capitalize">{s.commodity.toLowerCase()}</div>
                    <div className="text-[11px] text-neutral-500">
                      <span className="tabular-nums font-medium text-[var(--text-primary)]">{s.at_risk_count}</span> at-risk locations
                    </div>
                  </div>
                  <CircleAlert size={14} className="ml-auto flex-shrink-0" style={{ color: SEVERITY_COLORS[s.severity] }} />
                </Link>
              );
            })}
          </div>
        </div>
      </div>

      {emergencyOpen && (
        <EmergencyZoneModal
          onClose={() => setEmergencyOpen(false)}
          onCreated={() => fetchAll()}
        />
      )}

      {selectedRoad && (
        <RoadControlDrawer
          road={
            data?.roads?.features?.find((f) => f.properties.id === selectedRoad.id)?.properties || selectedRoad
          }
          onClose={() => setSelectedRoad(null)}
          onChanged={(updated) => {
            setSelectedRoad(updated);
            fetchAll();
          }}
        />
      )}
    </div>
  );
}
