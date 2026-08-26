import { useEffect, useState } from "react";
import { X, TriangleAlert, Loader2 } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "@/lib/api";

const TYPES = ["ACCIDENT", "LANDSLIDE", "FLOOD", "ROAD_DAMAGE", "BRIDGE_DAMAGE", "BLOCKAGE", "TRAFFIC", "WEATHER", "OTHER"];
const SEVERITIES = ["INFO", "WARNING", "HIGH", "CRITICAL"];

export default function AddIncidentModal({ onClose, onCreated }) {
  const [roads, setRoads] = useState([]);
  const [form, setForm] = useState({ type: "ACCIDENT", title: "", road_id: "", location: "", severity: "WARNING", lat: "", lng: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/dashboard/summary").then((r) => {
      setRoads(r.data.roads.features.map((f) => ({ id: f.properties.id, name: f.properties.name })));
    }).catch(() => {});
  }, []);

  const onRoadChange = (roadId) => {
    setForm((f) => ({ ...f, road_id: roadId }));
    api.get("/dashboard/summary").then((r) => {
      const feat = r.data.roads.features.find((x) => x.properties.id === roadId);
      if (feat) {
        const coords = feat.geometry.coordinates;
        const mid = coords[Math.floor(coords.length / 2)];
        setForm((f) => ({ ...f, lat: mid[1].toFixed(4), lng: mid[0].toFixed(4), location: "" }));
      }
    }).catch(() => {});
  };

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const { data } = await api.post("/incidents", {
        type: form.type,
        title: form.title.trim(),
        road_id: form.road_id || null,
        location: form.location.trim() || null,
        lat: parseFloat(form.lat),
        lng: parseFloat(form.lng),
        severity: form.severity,
      });
      toast.success(`Incident ${data.id} created — broadcast to all roles`);
      onCreated?.(data);
      onClose();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Unable to create incident");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/30" data-testid="add-incident-modal">
      <div className="bg-white rounded-md border hairline shadow-xl w-[440px] max-h-[90vh] overflow-y-auto">
        <div className="px-5 py-4 border-b hairline flex items-center justify-between">
          <div className="flex items-center gap-2 text-[var(--accent-primary)]">
            <TriangleAlert size={16} />
            <span className="text-[14px] font-semibold">Add Incident</span>
          </div>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-700" data-testid="add-incident-close">
            <X size={16} />
          </button>
        </div>

        <form onSubmit={submit} className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Type</label>
              <select value={form.type} onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}
                className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] bg-white" data-testid="incident-type-select">
                {TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Severity</label>
              <select value={form.severity} onChange={(e) => setForm((f) => ({ ...f, severity: e.target.value }))}
                className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] bg-white" data-testid="incident-severity-select">
                {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Title</label>
            <input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              placeholder="e.g. Multi-vehicle collision near toll gate" required minLength={5}
              className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px]" data-testid="incident-title-input" />
          </div>
          <div>
            <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Road / corridor</label>
            <select value={form.road_id} onChange={(e) => onRoadChange(e.target.value)}
              className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] bg-white" data-testid="incident-road-select">
              <option value="">— Custom location —</option>
              {roads.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          </div>
          {!form.road_id && (
            <div>
              <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Location label</label>
              <input value={form.location} onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))}
                placeholder="e.g. Near Baihata Chariali"
                className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px]" data-testid="incident-location-input" />
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Latitude</label>
              <input value={form.lat} onChange={(e) => setForm((f) => ({ ...f, lat: e.target.value }))} required placeholder="26.07"
                className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] font-mono" data-testid="incident-lat-input" />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Longitude</label>
              <input value={form.lng} onChange={(e) => setForm((f) => ({ ...f, lng: e.target.value }))} required placeholder="91.63"
                className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] font-mono" data-testid="incident-lng-input" />
            </div>
          </div>
          <div className="p-3 bg-[var(--accent-soft)] border hairline rounded-md text-[11.5px] text-[var(--accent-primary)]">
            Incidents created by government and field roles are broadcast to all users immediately. Public reports still require verification first.
          </div>
          <button type="submit" disabled={saving}
            className="w-full h-11 rounded-md bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] disabled:opacity-60 text-white text-[13px] font-medium flex items-center justify-center gap-2 transition-colors"
            data-testid="incident-submit-button">
            {saving ? <Loader2 size={15} className="animate-spin" /> : <TriangleAlert size={15} />}
            {saving ? "Creating…" : "Create & Broadcast"}
          </button>
        </form>
      </div>
    </div>
  );
}
