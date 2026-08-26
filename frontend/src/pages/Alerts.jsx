import { useCallback, useEffect, useState } from "react";
import { TriangleAlert, Radio, ShieldCheck, Megaphone, Bell, AlertOctagon, CloudRain, Mountain } from "lucide-react";
import api from "@/lib/api";
import NavRail from "@/components/NavRail";
import PageHeader from "@/components/PageHeader";

const SEV_COLORS = { INFO: "#4C7EA8", WARNING: "#C77C00", HIGH: "#D9622B", CRITICAL: "#C4281C", GOV: "#1B4B66" };
const KIND_META = {
  INCIDENT: { label: "Incident", icon: TriangleAlert },
  FIELD_REPORT: { label: "Field Report", icon: Radio },
  PUBLIC_REPORT: { label: "Public Report", icon: Megaphone },
  NOTIFICATION: { label: "Gov Notification", icon: Bell },
  EMERGENCY: { label: "Emergency Zone", icon: AlertOctagon },
  WEATHER: { label: "Weather", icon: CloudRain },
  HAZARD: { label: "Hazard Watch", icon: Mountain },
  GOVERNMENT_ACTION: { label: "Government Action", icon: ShieldCheck },
};

function timeAgo(iso) {
  if (!iso) return "—";
  const d = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  return d < 1 ? "just now" : d < 60 ? `${d}m ago` : `${Math.floor(d / 60)}h ago`;
}

export default function Alerts() {
  const [alerts, setAlerts] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const { data } = await api.get("/alerts");
      setAlerts(data);
    } catch (e) { /* keep last */ }
  }, []);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 10000);
    return () => clearInterval(t);
  }, [fetchAll]);

  return (
    <div className="h-screen flex bg-[var(--surface-base)] overflow-hidden" data-testid="alerts-page">
      <NavRail />
      <div className="flex-1 flex flex-col min-w-0">
        <PageHeader title="ALERTS" chip="UNIFIED FEED · 10S REFRESH" />
        <div className="flex-1 overflow-y-auto p-5 max-w-4xl">
          <div className="space-y-2" data-testid="alerts-feed">
            {!alerts && [1, 2, 3, 4, 5].map((n) => <div key={n} className="h-16 bg-white border hairline rounded-md animate-pulse" />)}
            {alerts && alerts.length === 0 && (
              <div className="bg-white border hairline rounded-md p-10 text-center text-[13px] text-neutral-500" data-testid="alerts-empty">
                No active alerts.
              </div>
            )}
            {alerts && alerts.map((a) => {
              const meta = KIND_META[a.kind] || KIND_META.INCIDENT;
              const color = SEV_COLORS[a.severity] || "#8A9099";
              return (
                <div key={`${a.kind}-${a.id}`} className="bg-white border hairline rounded-md p-4" style={{ borderLeft: `3px solid ${color}` }} data-testid={`alert-row-${a.id}`}>
                  <div className="flex items-center gap-2">
                    <meta.icon size={14} style={{ color }} />
                    <span className="text-[10px] uppercase tracking-widest font-semibold" style={{ color }}>{meta.label}</span>
                    {a.status && (
                      <span className="text-[9.5px] font-mono px-1.5 py-0.5 rounded bg-[var(--surface-sunken)] text-neutral-500">{(a.status || "").replace(/_/g, " ")}</span>
                    )}
                    <span className="ml-auto text-[10px] font-mono text-neutral-400">{timeAgo(a.created_at)}</span>
                  </div>
                  <div className="mt-1.5 text-[13px] font-medium">{a.title}</div>
                  <div className="mt-0.5 text-[11.5px] text-neutral-500">{a.location} · <span className="font-mono">{a.source}</span></div>
                  {a.message && (
                    <div className="mt-1.5 text-[12px] text-neutral-600 bg-[var(--surface-base)] border hairline rounded px-2.5 py-1.5">{a.message}</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
