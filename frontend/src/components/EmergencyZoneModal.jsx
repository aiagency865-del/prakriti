import { useEffect, useState } from "react";
import { X, AlertOctagon, Loader2 } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "@/lib/api";

const PLACE_COORDS = {
  guwahati: [91.74, 26.15], shillong: [91.60, 25.57], tezpur: [92.80, 26.63],
  nagaon: [92.32, 26.30], jorhat: [94.20, 26.75], silchar: [92.78, 24.83],
  aizawl: [92.90, 23.73], kohima: [94.05, 25.70], dimapur: [93.73, 25.91],
  imphal: [93.94, 24.82], ukhrul: [94.35, 24.98], itanagar: [93.61, 27.10],
  pasighat: [95.33, 28.06], agartala: [91.28, 23.83], udaipur: [91.49, 23.53],
  goalpara: [90.97, 26.07], mangaldai: [92.03, 26.44],
};

export default function EmergencyZoneModal({ onClose, onCreated }) {
  const [places, setPlaces] = useState(Object.keys(PLACE_COORDS));
  const [form, setForm] = useState({ name: "", place: "guwahati", radius_km: 10, message: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/routes/places").then((r) => setPlaces(r.data)).catch(() => {});
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    const coords = PLACE_COORDS[form.place] || PLACE_COORDS.guwahati;
    setSaving(true);
    try {
      const { data } = await api.post("/emergency-zones", {
        name: form.name.trim(),
        lat: coords[1],
        lng: coords[0],
        radius_km: Number(form.radius_km),
        message: form.message.trim(),
      });
      toast.success(`Emergency declared for ${data.name} — visible to all users`);
      onCreated?.(data);
      onClose();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Unable to declare emergency");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/30" data-testid="emergency-modal">
      <div className="bg-white rounded-md border hairline shadow-xl w-[440px] max-h-[90vh] overflow-y-auto">
        <div className="px-5 py-4 border-b hairline flex items-center justify-between">
          <div className="flex items-center gap-2 text-[#8A1512]">
            <AlertOctagon size={16} />
            <span className="text-[14px] font-semibold">Declare Emergency Zone</span>
          </div>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-700" data-testid="emergency-modal-close">
            <X size={16} />
          </button>
        </div>

        <form onSubmit={submit} className="p-5 space-y-4">
          <div>
            <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Zone name</label>
            <input
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="e.g. Sonapur Landslide Zone"
              required
              minLength={3}
              className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px]"
              data-testid="emergency-name-input"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Center (town)</label>
              <select
                value={form.place}
                onChange={(e) => setForm((f) => ({ ...f, place: e.target.value }))}
                className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] bg-white capitalize"
                data-testid="emergency-place-select"
              >
                {places.map((p) => <option key={p} value={p} className="capitalize">{p}</option>)}
              </select>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Radius (km)</label>
              <input
                type="number"
                min={1}
                max={200}
                step={1}
                value={form.radius_km}
                onChange={(e) => setForm((f) => ({ ...f, radius_km: e.target.value }))}
                className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] tabular-nums"
                data-testid="emergency-radius-input"
              />
            </div>
          </div>
          <div>
            <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Public message</label>
            <textarea
              value={form.message}
              onChange={(e) => setForm((f) => ({ ...f, message: e.target.value }))}
              rows={3}
              required
              minLength={5}
              placeholder="Instructions for citizens and operators in the zone…"
              className="mt-1.5 w-full px-3 py-2 border hairline rounded-md text-[13px] resize-none"
              data-testid="emergency-message-input"
            />
          </div>
          <div className="p-3 bg-red-50 border border-red-200 rounded-md text-[11.5px] text-red-900">
            This zone is drawn on all maps and broadcast to every role — government, logistics, field and public. The action is logged in the audit trail.
          </div>
          <button
            type="submit"
            disabled={saving}
            className="w-full h-11 rounded-md bg-[#8A1512] hover:bg-[#6E100E] disabled:opacity-60 text-white text-[13px] font-medium flex items-center justify-center gap-2 transition-colors"
            data-testid="emergency-submit-button"
          >
            {saving ? <Loader2 size={15} className="animate-spin" /> : <AlertOctagon size={15} />}
            {saving ? "Declaring…" : "Declare Emergency"}
          </button>
        </form>
      </div>
    </div>
  );
}
