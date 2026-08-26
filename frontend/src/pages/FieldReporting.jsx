import { useCallback, useEffect, useState } from "react";
import { Send, Loader2, CloudOff, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "@/lib/api";
import NavRail from "@/components/NavRail";
import PageHeader from "@/components/PageHeader";
import EmergencyBanner from "@/components/EmergencyBanner";
import EscalationsPanel from "@/components/EscalationsPanel";

const REPORT_TYPES = ["LANDSLIDE", "FLOOD", "ROAD_DAMAGE", "BRIDGE_DAMAGE", "ACCIDENT", "BLOCKAGE", "OTHER"];
const SEVERITIES = ["INFO", "WARNING", "HIGH", "CRITICAL"];
const SEV_COLORS = { INFO: "#4C7EA8", WARNING: "#C77C00", HIGH: "#D9622B", CRITICAL: "#C4281C" };
const QUEUE_KEY = "neris_field_queue";

const getQueue = () => JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]");
const setQueue = (q) => localStorage.setItem(QUEUE_KEY, JSON.stringify(q));

function timeAgo(iso) {
  if (!iso) return "—";
  const diff = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  if (diff < 1) return "just now";
  if (diff < 60) return `${diff}m ago`;
  return `${Math.floor(diff / 60)}h ago`;
}

export default function FieldReporting() {
  const [roads, setRoads] = useState([]);
  const [reports, setReports] = useState(null);
  const [queued, setQueued] = useState(getQueue().length);
  const [form, setForm] = useState({ type: "ROAD_DAMAGE", road_id: "", severity: "WARNING", description: "", lat: "", lng: "" });
  const [saving, setSaving] = useState(false);

  const loadReports = useCallback(async () => {
    try {
      const { data } = await api.get("/field/reports");
      setReports(data);
    } catch (e) { /* keep last */ }
  }, []);

  const flushQueue = useCallback(async () => {
    const q = getQueue();
    if (!q.length) return;
    const remaining = [];
    let flushed = 0;
    for (const item of q) {
      try {
        await api.post("/field/reports", item);
        flushed++;
      } catch (e) {
        remaining.push(item);
      }
    }
    setQueue(remaining);
    setQueued(remaining.length);
    if (flushed > 0) {
      toast.success(`${flushed} queued report(s) synced`);
      loadReports();
    }
  }, [loadReports]);

  useEffect(() => {
    api.get("/dashboard/summary").then((r) => {
      setRoads(r.data.roads.features.map((f) => ({ id: f.properties.id, name: f.properties.name })));
    }).catch(() => {});
    loadReports();
    flushQueue();
    const t = setInterval(loadReports, 15000);
    const online = () => flushQueue();
    window.addEventListener("online", online);
    return () => { clearInterval(t); window.removeEventListener("online", online); };
  }, [loadReports, flushQueue]);

  const onRoadChange = (roadId) => {
    setForm((f) => {
      const road = roads.find((r) => r.id === roadId);
      return { ...f, road_id: roadId };
    });
    // auto-fill coordinates from road midpoint
    api.get("/dashboard/summary").then((r) => {
      const feat = r.data.roads.features.find((x) => x.properties.id === roadId);
      if (feat) {
        const coords = feat.geometry.coordinates;
        const mid = coords[Math.floor(coords.length / 2)];
        setForm((f) => ({ ...f, lat: mid[1].toFixed(4), lng: mid[0].toFixed(4) }));
      }
    }).catch(() => {});
  };

  const submit = async (e) => {
    e.preventDefault();
    const payload = {
      type: form.type,
      description: form.description.trim(),
      road_id: form.road_id || null,
      lat: parseFloat(form.lat),
      lng: parseFloat(form.lng),
      severity: form.severity,
    };
    if (!payload.description || isNaN(payload.lat) || isNaN(payload.lng)) return;
    setSaving(true);
    try {
      await api.post("/field/reports", payload);
      toast.success("Report submitted — visible to Command Center and logistics immediately");
      setForm({ type: "ROAD_DAMAGE", road_id: "", severity: "WARNING", description: "", lat: "", lng: "" });
      loadReports();
    } catch (err) {
      if (!err.response) {
        const q = getQueue();
        q.push(payload);
        setQueue(q);
        setQueued(q.length);
        toast.info("Offline — report queued and will sync when connection returns");
        setForm({ type: "ROAD_DAMAGE", road_id: "", severity: "WARNING", description: "", lat: "", lng: "" });
      } else {
        toast.error(formatApiErrorDetail(err.response?.data?.detail));
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="h-screen flex bg-[var(--surface-base)] overflow-hidden" data-testid="field-page">
      <NavRail />
      <div className="flex-1 flex flex-col min-w-0">
        <PageHeader title="FIELD REPORTING" chip="DEMO FEED">
          {queued > 0 && (
            <span className="text-[11px] text-amber-700 flex items-center gap-1.5" data-testid="field-queue-count">
              <CloudOff size={13} /> {queued} queued
            </span>
          )}
        </PageHeader>

        <EmergencyBanner />

        <div className="flex-1 flex min-h-0">
          <div className="w-[420px] flex-shrink-0 bg-white border-r hairline overflow-y-auto p-5">
            <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold mb-3">New report</div>
            <form onSubmit={submit} className="space-y-4" data-testid="field-report-form">
              <div>
                <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Type</label>
                <select
                  value={form.type}
                  onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}
                  className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] bg-white"
                  data-testid="field-type-select"
                >
                  {REPORT_TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Road / corridor</label>
                <select
                  value={form.road_id}
                  onChange={(e) => onRoadChange(e.target.value)}
                  className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] bg-white"
                  data-testid="field-road-select"
                >
                  <option value="">— Select road —</option>
                  {roads.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Severity</label>
                <select
                  value={form.severity}
                  onChange={(e) => setForm((f) => ({ ...f, severity: e.target.value }))}
                  className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] bg-white"
                  data-testid="field-severity-select"
                >
                  {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Latitude</label>
                  <input
                    value={form.lat}
                    onChange={(e) => setForm((f) => ({ ...f, lat: e.target.value }))}
                    placeholder="26.0700"
                    required
                    className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] font-mono"
                    data-testid="field-lat-input"
                  />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Longitude</label>
                  <input
                    value={form.lng}
                    onChange={(e) => setForm((f) => ({ ...f, lng: e.target.value }))}
                    placeholder="91.6300"
                    required
                    className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] font-mono"
                    data-testid="field-lng-input"
                  />
                </div>
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Description</label>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  rows={4}
                  required
                  minLength={5}
                  placeholder="What do you observe on the ground?"
                  className="mt-1.5 w-full px-3 py-2 border hairline rounded-md text-[13px] resize-none"
                  data-testid="field-description-input"
                />
              </div>
              <button
                type="submit"
                disabled={saving}
                className="w-full h-11 rounded-md bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] disabled:opacity-60 text-white text-[13px] font-medium flex items-center justify-center gap-2 transition-colors"
                data-testid="field-submit-button"
              >
                {saving ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
                {saving ? "Submitting…" : "Submit Report"}
              </button>
              <div className="text-[11px] text-neutral-500 text-center">
                Photo evidence upload coming in the next iteration. Reports propagate to government & logistics instantly.
              </div>
            </form>
          </div>

          <div className="flex-1 overflow-y-auto p-5">
            <div className="bg-white border hairline rounded-md mb-4 overflow-hidden">
              <EscalationsPanel />
            </div>
            <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold mb-3">My reports</div>
            <div className="space-y-2" data-testid="field-reports-list">
              {!reports && [1, 2, 3].map((n) => (
                <div key={n} className="h-20 bg-white border hairline rounded-md animate-pulse" />
              ))}
              {reports && reports.length === 0 && (
                <div className="bg-white border hairline rounded-md p-10 text-center text-[13px] text-neutral-500" data-testid="field-reports-empty">
                  No reports yet. Submit your first field report.
                </div>
              )}
              {reports && reports.map((r) => (
                <div key={r.id} className="bg-white border hairline rounded-md p-4" data-testid={`field-report-row-${r.id}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span
                        className="text-[9.5px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded"
                        style={{ background: `${SEV_COLORS[r.severity]}14`, color: SEV_COLORS[r.severity] }}
                      >
                        {r.severity}
                      </span>
                      <span className="text-[12px] font-medium">{r.type.replace("_", " ")}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {r.status === "VERIFIED" ? (
                        <span className="text-[10px] font-semibold text-green-700 flex items-center gap-1">
                          <CheckCircle2 size={12} /> VERIFIED
                        </span>
                      ) : (
                        <span className="text-[10px] font-semibold text-neutral-500">SUBMITTED</span>
                      )}
                      <span className="text-[10px] font-mono text-neutral-400">{timeAgo(r.created_at)}</span>
                    </div>
                  </div>
                  <div className="mt-1.5 text-[13px] text-neutral-700">{r.description}</div>
                  <div className="mt-1 text-[11px] text-neutral-500">{r.location} · <span className="font-mono">{r.id}</span></div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
