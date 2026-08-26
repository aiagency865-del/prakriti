import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, TriangleAlert, Radio, ShieldCheck, CarFront } from "lucide-react";
import api from "@/lib/api";
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

  const fetchAll = useCallback(async () => {
    try {
      const [s, d, a, acc] = await Promise.all([
        api.get("/dashboard/summary"),
        api.get("/deliveries"),
        api.get("/alerts"),
        api.get("/accidents"),
      ]);
      setSummary(s.data);
      setDeliveries(d.data);
      setAlerts(a.data);
      setAccidents(acc.data);
    } catch (e) { /* keep last */ }
  }, []);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 10000);
    return () => clearInterval(t);
  }, [fetchAll]);

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
