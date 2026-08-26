import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, TriangleAlert, Radio, ShieldCheck, CarFront, Play, Navigation, Loader2, AlertOctagon } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "@/lib/api";
import { ensureWS, subscribeWS } from "@/lib/ws";
import NavRail from "@/components/NavRail";
import PageHeader from "@/components/PageHeader";
import EmergencyBanner from "@/components/EmergencyBanner";

const SEV_COLORS = { INFO: "#4C7EA8", WARNING: "#C77C00", HIGH: "#D9622B", CRITICAL: "#C4281C", GOV: "#1B4B66" };
const DELIVERY_STATUS = {
  ON_TRACK: { label: "On Track", color: "#1E8E3E" },
  DELAYED: { label: "Delayed", color: "#C77C00" },
  AT_RISK: { label: "At Risk", color: "#C4281C" },
};

function riskMeta(r) {
  if (r >= 60) return { label: "HIGH", color: "#C4281C" };
  if (r >= 30) return { label: "MED", color: "#C77C00" };
  return { label: "LOW", color: "#1E8E3E" };
}
function fmtEta(m) {
  if (m == null) return "—";
  const h = Math.floor(m / 60);
  return h > 0 ? `${h}h ${String(m % 60).padStart(2, "0")}m` : `${m}m`;
}
function timeAgo(iso) {
  if (!iso) return "—";
  const d = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  return d < 1 ? "just now" : d < 60 ? `${d}m ago` : `${Math.floor(d / 60)}h ago`;
}

export default function LogisticsWorkspace() {
  const [summary, setSummary] = useState(null);
  const [deliveries, setDeliveries] = useState(null);
  const [alerts, setAlerts] = useState(null);
  const [accidents, setAccidents] = useState(null);
  const [trips, setTrips] = useState(null);
  const [tripForm, setTripForm] = useState({ origin: "", destination: "", vehicle_type: "TRUCK" });
  const [places, setPlaces] = useState([]);
  const [starting, setStarting] = useState(false);
  const [reroute, setReroute] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const [s, d, a, acc, t] = await Promise.all([
        api.get("/dashboard/summary"),
        api.get("/deliveries"),
        api.get("/alerts"),
        api.get("/accidents"),
        api.get("/trips"),
      ]);
      setSummary(s.data);
      setDeliveries(d.data);
      setAlerts(a.data);
      setAccidents(acc.data);
      setTrips(t.data);
    } catch (e) { /* keep last */ }
  }, []);

  useEffect(() => {
    api.get("/routes/places").then((r) => setPlaces(r.data)).catch(() => {});
    fetchAll();
    const t = setInterval(fetchAll, 10000);
    return () => clearInterval(t);
  }, [fetchAll]);

  useEffect(() => {
    ensureWS();
    const unsub = subscribeWS((msg) => {
      if (msg.type === "REROUTE_REQUIRED") {
        setReroute(msg);
        toast.error(`Reroute required: ${msg.road_name} is now ${msg.new_status.replace(/_/g, " ")}`, { duration: 8000 });
        fetchAll();
      } else if (["ROAD_STATUS_CHANGED", "INCIDENT_CREATED", "INCIDENT_VERIFIED", "EMERGENCY_DECLARED", "EMERGENCY_ENDED", "VEHICLE_ADDED"].includes(msg.type)) {
        fetchAll();
      }
    });
    return unsub;
  }, [fetchAll]);

  const startTrip = async (e) => {
    e.preventDefault();
    setStarting(true);
    try {
      const { data } = await api.post("/trips", {
        origin: tripForm.origin.trim().toLowerCase(),
        destination: tripForm.destination.trim().toLowerCase(),
        vehicle_type: tripForm.vehicle_type,
      });
      toast.success(`Trip ${data.id} started — live rerouting active`);
      setTripForm({ origin: "", destination: "", vehicle_type: "TRUCK" });
      fetchAll();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Unable to start trip");
    } finally {
      setStarting(false);
    }
  };

  const endTrip = async (id) => {
    try {
      await api.patch(`/trips/${id}/end`);
      toast.success("Trip ended");
      fetchAll();
    } catch (e) {
      toast.error("Unable to end trip");
    }
  };

  const kpis = deliveries && summary ? [
    { label: "Active Vehicles", value: summary.kpis.active_vehicles },
    { label: "Deliveries On Track", value: deliveries.filter((d) => d.status === "ON_TRACK").length },
    { label: "Delayed / At Risk", value: deliveries.filter((d) => d.status !== "ON_TRACK").length },
    { label: "Avg Route Risk", value: Math.round(deliveries.reduce((a, d) => a + d.risk, 0) / Math.max(deliveries.length, 1)) },
  ] : [];

  return (
    <div className="h-screen flex bg-[var(--surface-base)] overflow-hidden" data-testid="logistics-page">
      <NavRail />
      <div className="flex-1 flex flex-col min-w-0">
        <PageHeader title="LOGISTICS WORKSPACE" chip="LIVE NETWORK STATE">
          <Link to="/routes" className="text-[12px] text-[var(--accent-primary)] hover:underline flex items-center gap-1" data-testid="logistics-route-link">
            Calculate route <ArrowRight size={13} />
          </Link>
        </PageHeader>

        <EmergencyBanner />

        {reroute && (
          <div className="flex-shrink-0 bg-red-600 text-white px-5 py-2.5 flex items-center gap-2.5 text-[13px]" data-testid="logistics-reroute-banner">
            <AlertOctagon size={15} className="flex-shrink-0" />
            <span className="font-semibold">REROUTE REQUIRED</span>
            <span>{reroute.road_name} is now {reroute.new_status.replace(/_/g, " ")} — trip route recalculated.</span>
            <button onClick={() => setReroute(null)} className="ml-auto text-[11px] underline underline-offset-2" data-testid="logistics-reroute-dismiss">Dismiss</button>
          </div>
        )}

        <div className="flex-shrink-0 grid grid-cols-2 md:grid-cols-4 border-b hairline bg-white" data-testid="logistics-kpis">
          {(kpis.length ? kpis : [1, 2, 3, 4]).map((k, i) => (
            <div key={i} className={`px-5 py-3 ${i > 0 ? "border-l hairline" : ""}`}>
              {kpis.length ? (
                <>
                  <div className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">{k.label}</div>
                  <div className="mt-1 text-xl font-semibold tabular-nums">{k.value}</div>
                </>
              ) : <div className="h-10 bg-[var(--surface-sunken)] rounded animate-pulse" />}
            </div>
          ))}
        </div>

        <div className="flex-1 flex min-h-0">
          <div className="flex-1 overflow-y-auto p-5 min-w-0">
            {/* Trips (driver mode merged into logistics) */}
            <div className="mb-5 bg-white border hairline rounded-md p-4" data-testid="logistics-trips">
              <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold mb-3">Trips — start & live status</div>
              <form onSubmit={startTrip} className="flex flex-wrap gap-2 items-end" data-testid="logistics-trip-form">
                <input
                  list="logistics-places"
                  value={tripForm.origin}
                  onChange={(e) => setTripForm((f) => ({ ...f, origin: e.target.value }))}
                  placeholder="From"
                  required
                  className="h-9 px-3 border hairline rounded-md text-[12.5px] capitalize w-36"
                  data-testid="logistics-trip-origin"
                />
                <input
                  list="logistics-places"
                  value={tripForm.destination}
                  onChange={(e) => setTripForm((f) => ({ ...f, destination: e.target.value }))}
                  placeholder="To"
                  required
                  className="h-9 px-3 border hairline rounded-md text-[12.5px] capitalize w-36"
                  data-testid="logistics-trip-destination"
                />
                <datalist id="logistics-places">
                  {places.map((p) => <option key={p} value={p} />)}
                </datalist>
                <select
                  value={tripForm.vehicle_type}
                  onChange={(e) => setTripForm((f) => ({ ...f, vehicle_type: e.target.value }))}
                  className="h-9 px-2 border hairline rounded-md text-[12.5px] bg-white"
                  data-testid="logistics-trip-vehicle"
                >
                  {["TRUCK", "LIGHT", "SUV", "TWO_WHEELER", "EMERGENCY"].map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
                </select>
                <button
                  type="submit"
                  disabled={starting}
                  className="h-9 px-3.5 rounded-md bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] disabled:opacity-60 text-white text-[12.5px] font-medium flex items-center gap-1.5"
                  data-testid="logistics-trip-start"
                >
                  {starting ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
                  Start Trip
                </button>
              </form>

              <div className="mt-3 space-y-1.5" data-testid="logistics-trips-list">
                {trips && trips.length === 0 && (
                  <div className="text-[12px] text-neutral-500 py-2" data-testid="logistics-trips-empty">No trips yet.</div>
                )}
                {trips && trips.slice(0, 6).map((t) => (
                  <div key={t.id} className="flex items-center gap-2.5 px-3 py-2 border hairline rounded-md text-[12.5px]" data-testid={`logistics-trip-${t.id}`}>
                    <Navigation size={13} className="text-[var(--accent-primary)] flex-shrink-0" />
                    <span className="font-medium capitalize">{t.origin} → {t.destination}</span>
                    <span className="text-neutral-500 text-[11px] font-mono">{t.id}</span>
                    {t.reroute_reason && (
                      <span className="text-[10px] font-semibold text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded" data-testid={`logistics-trip-rerouted-${t.id}`}>
                        Rerouted: {t.reroute_reason}
                      </span>
                    )}
                    <span className="ml-auto flex items-center gap-2 flex-shrink-0">
                      <Link
                        to={`/routes?origin=${t.origin}&destination=${t.destination}`}
                        className="text-[11px] text-[var(--accent-primary)] hover:underline"
                        data-testid={`logistics-trip-map-${t.id}`}
                      >
                        View on map
                      </Link>
                      <span className={`text-[9.5px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded ${t.status === "ACTIVE" ? "bg-green-50 text-green-700" : "bg-neutral-100 text-neutral-500"}`}>{t.status}</span>
                      {t.status === "ACTIVE" && (
                        <button onClick={() => endTrip(t.id)} className="text-[11px] text-neutral-400 hover:text-red-700" data-testid={`logistics-trip-end-${t.id}`}>End</button>
                      )}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {accidents && accidents.length > 0 && (
              <div className="mb-5" data-testid="logistics-accidents">
                <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold mb-2">Verified accidents on network</div>
                <div className="space-y-1.5">
                  {accidents.slice(0, 4).map((a) => (
                    <div key={a.id} className="bg-white border hairline rounded-md px-3.5 py-2.5 flex items-center gap-3 text-[12.5px]" style={{ borderLeft: "3px solid #C4281C" }} data-testid={`logistics-accident-${a.id}`}>
                      <CarFront size={14} className="text-red-700 flex-shrink-0" />
                      <span className="font-medium truncate">{a.title}</span>
                      <span className="text-neutral-500 text-[11px] flex-shrink-0">{a.location}</span>
                      <span className="ml-auto text-[9.5px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-green-50 text-green-700 flex-shrink-0">Verified</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold mb-3">Deliveries</div>
            <div className="bg-white border hairline rounded-md overflow-hidden">
              <table className="w-full text-[13px]" data-testid="deliveries-table">
                <thead>
                  <tr className="border-b hairline text-left text-[10px] uppercase tracking-widest text-neutral-500">
                    <th className="px-4 py-3 font-semibold">Delivery</th>
                    <th className="px-4 py-3 font-semibold">Vehicle</th>
                    <th className="px-4 py-3 font-semibold">Route</th>
                    <th className="px-4 py-3 font-semibold">Commodity</th>
                    <th className="px-4 py-3 font-semibold text-right">ETA</th>
                    <th className="px-4 py-3 font-semibold">Risk</th>
                    <th className="px-4 py-3 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {!deliveries && [1, 2, 3, 4].map((n) => (
                    <tr key={n} className="border-b hairline">
                      {[...Array(7)].map((_, i) => <td key={i} className="px-4 py-3"><div className="h-3.5 bg-[var(--surface-sunken)] rounded animate-pulse" /></td>)}
                    </tr>
                  ))}
                  {deliveries && deliveries.map((d) => {
                    const R = riskMeta(d.risk);
                    const S = DELIVERY_STATUS[d.status];
                    return (
                      <tr key={d.id} className="border-b hairline hover:bg-[var(--surface-base)]" data-testid={`delivery-row-${d.id}`}>
                        <td className="px-4 py-3 font-mono text-[12px]">{d.id}</td>
                        <td className="px-4 py-3 font-medium tabular-nums">{d.vehicle}</td>
                        <td className="px-4 py-3 text-neutral-600">{d.origin} → {d.destination} <span className="text-neutral-400">({d.road})</span></td>
                        <td className="px-4 py-3 text-neutral-600 capitalize">{d.commodity.toLowerCase()}</td>
                        <td className="px-4 py-3 text-right tabular-nums">{fmtEta(d.eta_minutes)}</td>
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold px-1.5 py-0.5 rounded" style={{ background: `${R.color}14`, color: R.color }} data-testid={`delivery-risk-${d.id}`}>
                            <span className="status-dot" style={{ background: R.color }} />{R.label} · {d.risk}
                          </span>
                        </td>
                        <td className="px-4 py-3"><span className="text-[11px] font-medium" style={{ color: S.color }}>{S.label}</span></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <aside className="w-80 flex-shrink-0 bg-white border-l hairline flex flex-col min-h-0" data-testid="logistics-alerts-feed">
            <div className="px-4 py-3 border-b hairline text-[11px] uppercase tracking-widest text-neutral-500 font-semibold">
              Network Alerts
            </div>
            <div className="flex-1 overflow-y-auto">
              {!alerts && [1, 2, 3, 4].map((n) => (
                <div key={n} className="px-4 py-3 border-b hairline"><div className="h-3 w-2/3 bg-[var(--surface-sunken)] rounded animate-pulse" /></div>
              ))}
              {alerts && alerts.length === 0 && (
                <div className="px-4 py-10 text-center text-[13px] text-neutral-500" data-testid="logistics-alerts-empty">No active alerts on the network.</div>
              )}
              {alerts && alerts.map((a) => {
                const Icon = a.kind === "FIELD_REPORT" ? Radio : a.kind === "GOVERNMENT_ACTION" ? ShieldCheck : TriangleAlert;
                const color = SEV_COLORS[a.severity] || "#8A9099";
                return (
                  <div key={`${a.kind}-${a.id}`} className="px-4 py-3 border-b hairline" style={{ borderLeft: `3px solid ${color}` }} data-testid={`logistics-alert-${a.id}`}>
                    <div className="flex items-start gap-2">
                      <Icon size={14} className="mt-0.5 flex-shrink-0" style={{ color }} />
                      <div className="min-w-0">
                        <div className="text-[12.5px] font-medium leading-snug">{a.title}</div>
                        <div className="text-[11px] text-neutral-500 mt-0.5">{a.location}</div>
                        <div className="flex items-center gap-2 mt-1 text-[10px] text-neutral-500">
                          <span className="font-mono">{a.source}</span>
                          <span className="ml-auto">{timeAgo(a.created_at)}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
