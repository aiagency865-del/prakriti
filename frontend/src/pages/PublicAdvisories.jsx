import { useCallback, useEffect, useState } from "react";
import { ShieldCheck, MapPin, CheckCircle2, Megaphone, Loader2, X, CarFront, Coins, Ban } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "@/lib/api";
import NavRail from "@/components/NavRail";
import PageHeader from "@/components/PageHeader";
import EmergencyBanner from "@/components/EmergencyBanner";
import { STATUS_COLORS } from "@/components/NerMap";

const STATUS_LABELS = {
  OPEN: "Open", AT_RISK: "At Risk", RESTRICTED: "Restricted",
  BLOCKED: "Blocked", GOVERNMENT_CLOSED: "Gov Closed", UNKNOWN: "Unknown",
};
const SEV_COLORS = { INFO: "#4C7EA8", WARNING: "#C77C00", HIGH: "#D9622B", CRITICAL: "#C4281C" };

function timeAgo(iso) {
  if (!iso) return "—";
  const d = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  return d < 1 ? "just now" : d < 60 ? `${d}m ago` : `${Math.floor(d / 60)}h ago`;
}

export default function PublicAdvisories() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [zones, setZones] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [roads, setRoads] = useState([]);
  const [myReports, setMyReports] = useState([]);
  const [accidents, setAccidents] = useState([]);
  const [me, setMe] = useState(null);

  const isBanned = me?.report_ban_until && new Date(me.report_ban_until) > new Date();
  const [report, setReport] = useState({ type: "ROAD_DAMAGE", road_id: "", description: "", lat: "", lng: "" });
  const [sending, setSending] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [{ data: d }, { data: z }, { data: acc }] = await Promise.all([
        api.get("/public/advisories"),
        api.get("/emergency-zones"),
        api.get("/accidents"),
      ]);
      setData(d);
      setZones(z);
      setAccidents(acc);
      setError("");
    } catch (e) {
      setError("Unable to load advisories. Please retry.");
    }
  }, []);

  const fetchMyReports = useCallback(async () => {
    try {
      const [{ data: reports }, { data: meData }] = await Promise.all([
        api.get("/public/reports"),
        api.get("/auth/me"),
      ]);
      setMyReports(reports);
      setMe(meData);
    } catch (e) { /* keep last */ }
  }, []);

  useEffect(() => {
    fetchAll();
    fetchMyReports();
    api.get("/dashboard/summary").then((r) => {
      setRoads(r.data.roads.features.map((f) => ({ id: f.properties.id, name: f.properties.name })));
    }).catch(() => {});
    const t = setInterval(fetchAll, 15000);
    return () => clearInterval(t);
  }, [fetchAll, fetchMyReports]);

  const onRoadChange = (roadId) => {
    setReport((r) => ({ ...r, road_id: roadId }));
    api.get("/dashboard/summary").then((r) => {
      const feat = r.data.roads.features.find((x) => x.properties.id === roadId);
      if (feat) {
        const coords = feat.geometry.coordinates;
        const mid = coords[Math.floor(coords.length / 2)];
        setReport((rr) => ({ ...rr, lat: mid[1].toFixed(4), lng: mid[0].toFixed(4) }));
      }
    }).catch(() => {});
  };

  const submitReport = async (e) => {
    e.preventDefault();
    setSending(true);
    try {
      await api.post("/public/reports", {
        type: report.type,
        description: report.description.trim(),
        road_id: report.road_id || null,
        lat: parseFloat(report.lat) || 26.15,
        lng: parseFloat(report.lng) || 91.74,
      });
      toast.success("Report sent — a government or field officer will verify it before it is broadcast");
      setReport({ type: "ROAD_DAMAGE", road_id: "", description: "", lat: "", lng: "" });
      setShowForm(false);
      fetchMyReports();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Unable to submit report");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-[var(--surface-base)]" data-testid="public-page">
      <NavRail />
      <div className="flex-1 flex flex-col min-w-0">
        <PageHeader title="PUBLIC ADVISORIES" chip="GOVERNMENT-VERIFIED ONLY">
          {me && (
            <span className="h-8 px-3 rounded-full border hairline bg-white text-[12px] font-medium flex items-center gap-1.5 text-neutral-700" data-testid="public-token-balance">
              <Coins size={13} className="text-amber-600" /> {me.tokens ?? 0} tokens
            </span>
          )}
          {!isBanned && (
            <button
              onClick={() => setShowForm((s) => !s)}
              className="h-8 px-3 rounded-md bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] text-white text-[12px] font-medium flex items-center gap-1.5 transition-colors"
              data-testid="public-report-toggle"
            >
              <Megaphone size={13} /> Report an issue
            </button>
          )}
        </PageHeader>

        <EmergencyBanner zones={zones} onChanged={fetchAll} />

        {isBanned && (
          <div className="flex-shrink-0 bg-red-50 border-b border-red-200 px-6 py-2.5 text-[12px] text-red-800 flex items-center gap-2" data-testid="public-ban-banner">
            <Ban size={14} />
            Reporting suspended for 24 hours because a previous report was rejected as inaccurate. You can report again after {new Date(me.report_ban_until).toLocaleString()}.
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-6 max-w-5xl">
          <div className="p-4 border hairline rounded-md bg-white mb-6 text-[13px] text-neutral-600">
            This page shows only <span className="font-medium text-[var(--text-primary)]">government-verified</span> road status
            and verified field reports. Data refreshes automatically. Demo dataset.
          </div>

          {showForm && (
            <form onSubmit={submitReport} className="mb-6 p-4 border hairline rounded-md bg-white space-y-3" data-testid="public-report-form">
              <div className="flex items-center justify-between">
                <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold">Send a report to government</div>
                <button type="button" onClick={() => setShowForm(false)} className="text-neutral-400 hover:text-neutral-700"><X size={14} /></button>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <select
                  value={report.type}
                  onChange={(e) => setReport((r) => ({ ...r, type: e.target.value }))}
                  className="h-10 px-3 border hairline rounded-md text-[13px] bg-white"
                  data-testid="public-report-type"
                >
                  {["ROAD_DAMAGE", "LANDSLIDE", "FLOOD", "BRIDGE_DAMAGE", "ACCIDENT", "BLOCKAGE", "OTHER"].map((t) => (
                    <option key={t} value={t}>{t.replace("_", " ")}</option>
                  ))}
                </select>
                <select
                  value={report.road_id}
                  onChange={(e) => onRoadChange(e.target.value)}
                  className="h-10 px-3 border hairline rounded-md text-[13px] bg-white"
                  data-testid="public-report-road"
                >
                  <option value="">— Road (optional) —</option>
                  {roads.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
              </div>
              <textarea
                value={report.description}
                onChange={(e) => setReport((r) => ({ ...r, description: e.target.value }))}
                rows={3}
                required
                minLength={5}
                placeholder="Describe what you observe…"
                className="w-full px-3 py-2 border hairline rounded-md text-[13px] resize-none"
                data-testid="public-report-description"
              />
              <div className="flex items-center justify-between">
                <div className="text-[11px] text-neutral-500">Reviewed by a government or field officer before broadcast to all users.</div>
                <button
                  type="submit"
                  disabled={sending}
                  className="h-9 px-4 rounded-md bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] disabled:opacity-60 text-white text-[12.5px] font-medium flex items-center gap-2"
                  data-testid="public-report-submit"
                >
                  {sending && <Loader2 size={13} className="animate-spin" />}
                  {sending ? "Sending…" : "Send report"}
                </button>
              </div>
            </form>
          )}

          {myReports.length > 0 && (
            <div className="mb-6" data-testid="public-my-reports">
              <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold mb-2">My submissions</div>
              <div className="space-y-1.5">
                {myReports.slice(0, 5).map((r) => (
                  <div key={r.id} className="bg-white border hairline rounded-md px-3.5 py-2.5 flex items-center gap-3 text-[12.5px]" data-testid={`public-report-row-${r.id}`}>
                    <span className="font-medium truncate">{r.description}</span>
                    <span className="text-neutral-500 text-[11px] flex-shrink-0">{r.location}</span>
                    <span
                      className={`ml-auto text-[9.5px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded flex-shrink-0 ${
                        r.status === "VERIFIED" ? "bg-green-50 text-green-700" : r.status === "REJECTED" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"
                      }`}
                    >
                      {r.status === "VERIFIED" ? "Verified · +10 tokens" : r.status === "REJECTED" ? "Rejected" : "Pending review"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {error && <div className="p-3 mb-4 border rounded-md bg-red-50 border-red-200 text-red-800 text-[12px]" data-testid="public-error">{error}</div>}

          <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold mb-3">Current road advisories</div>
          <div className="space-y-2" data-testid="public-road-advisories">
            {!data && [1, 2, 3].map((n) => <div key={n} className="h-16 bg-white border hairline rounded-md animate-pulse" />)}
            {data && data.road_advisories.length === 0 && (
              <div className="bg-white border hairline rounded-md p-8 text-center text-[13px] text-neutral-500" data-testid="public-advisories-empty">
                No active advisories — all monitored roads are operating normally.
              </div>
            )}
            {data && data.road_advisories.map((r) => (
              <div key={r.id} className="bg-white border hairline rounded-md p-4" style={{ borderLeft: `3px solid ${STATUS_COLORS[r.status]}` }} data-testid={`advisory-card-${r.id}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="status-dot" style={{ background: STATUS_COLORS[r.status] }} />
                    <span className="text-[13.5px] font-semibold">{r.name}</span>
                    <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded" style={{ background: `${STATUS_COLORS[r.status]}14`, color: STATUS_COLORS[r.status] }}>
                      {STATUS_LABELS[r.status]}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--surface-sunken)] text-neutral-500">GOVERNMENT-VERIFIED</span>
                </div>
                <div className="mt-1.5 text-[12.5px] text-neutral-600 flex items-center gap-1.5">
                  <MapPin size={12} className="text-neutral-400" /> {r.district}
                  {r.reason && <> · {r.reason}</>}
                </div>
                <div className="mt-1 text-[11px] text-neutral-500">
                  {r.expected_duration && <>Expected duration: {r.expected_duration} · </>}
                  Updated {timeAgo(r.updated_at)}
                </div>
              </div>
            ))}
          </div>

          <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold mt-8 mb-3">Verified accidents</div>
          <div className="space-y-2" data-testid="public-accidents">
            {data && accidents.length === 0 && (
              <div className="bg-white border hairline rounded-md p-8 text-center text-[13px] text-neutral-500" data-testid="public-accidents-empty">
                No verified accidents reported. Accident reports from the public appear here only after field or government verification.
              </div>
            )}
            {accidents.map((a) => (
              <div key={a.id} className="bg-white border hairline rounded-md p-4 flex items-center gap-3" data-testid={`accident-row-${a.id}`}>
                <span className="w-8 h-8 rounded-sm bg-red-50 text-red-700 flex items-center justify-center flex-shrink-0">
                  <CarFront size={15} />
                </span>
                <div className="min-w-0">
                  <div className="text-[13px] font-medium">{a.title}</div>
                  <div className="text-[11px] text-neutral-500">{a.location} · Verified by {a.verified_by || "authorities"} · {timeAgo(a.created_at)}</div>
                </div>
                <CheckCircle2 size={14} className="ml-auto flex-shrink-0 text-green-700" />
              </div>
            ))}
          </div>

          <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold mt-8 mb-3">Verified incidents</div>
          <div className="space-y-2" data-testid="public-verified-incidents">
            {data && data.verified_incidents.length === 0 && data.verified_field_reports.length === 0 && (
              <div className="bg-white border hairline rounded-md p-8 text-center text-[13px] text-neutral-500" data-testid="public-incidents-empty">
                No verified incidents at this time.
              </div>
            )}
            {data && data.verified_incidents.map((i) => (
              <div key={i.id} className="bg-white border hairline rounded-md p-4 flex items-center gap-3" data-testid={`verified-incident-${i.id}`}>
                <span
                  className="text-[9.5px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded flex-shrink-0"
                  style={{ background: `${SEV_COLORS[i.severity]}14`, color: SEV_COLORS[i.severity] }}
                >
                  {i.severity}
                </span>
                <div className="min-w-0">
                  <div className="text-[13px] font-medium">{i.title}</div>
                  <div className="text-[11px] text-neutral-500">{i.location} · {timeAgo(i.created_at)}</div>
                </div>
                <CheckCircle2 size={14} className="ml-auto flex-shrink-0 text-green-700" />
              </div>
            ))}
            {data && data.verified_field_reports.map((r) => (
              <div key={r.id} className="bg-white border hairline rounded-md p-4 flex items-center gap-3" data-testid={`verified-report-${r.id}`}>
                <span
                  className="text-[9.5px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded flex-shrink-0"
                  style={{ background: `${SEV_COLORS[r.severity]}14`, color: SEV_COLORS[r.severity] }}
                >
                  {r.severity}
                </span>
                <div className="min-w-0">
                  <div className="text-[13px] font-medium">{r.description}</div>
                  <div className="text-[11px] text-neutral-500">{r.location} · Field report · {timeAgo(r.created_at)}</div>
                </div>
                <ShieldCheck size={14} className="ml-auto flex-shrink-0 text-[var(--accent-primary)]" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
