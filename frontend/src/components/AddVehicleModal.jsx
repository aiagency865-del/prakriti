import { useState } from "react";
import { X, Truck, Loader2 } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "@/lib/api";

const TYPES = ["TRUCK", "LIGHT", "SUV", "TWO_WHEELER", "EMERGENCY"];
const COMMODITIES = ["", "MEDICINE", "FOOD", "WATER", "FUEL", "CONSTRUCTION", "AGRICULTURAL", "EMERGENCY_EQUIPMENT"];

export default function AddVehicleModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ number: "", type: "TRUCK", destination: "", commodity: "", lat: "26.1500", lng: "91.7400" });
  const [saving, setSaving] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const { data } = await api.post("/vehicles", {
        number: form.number.trim(),
        type: form.type,
        lat: parseFloat(form.lat),
        lng: parseFloat(form.lng),
        destination: form.destination.trim() || null,
        commodity: form.commodity || null,
      });
      toast.success(`Vehicle ${data.number} registered`);
      onCreated?.(data);
      onClose();
    } catch (err) {
      toast.error(formatApiErrorDetail(err.response?.data?.detail) || "Unable to register vehicle");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/30" data-testid="add-vehicle-modal">
      <div className="bg-white rounded-md border hairline shadow-xl w-[420px]">
        <div className="px-5 py-4 border-b hairline flex items-center justify-between">
          <div className="flex items-center gap-2 text-[var(--accent-primary)]">
            <Truck size={16} />
            <span className="text-[14px] font-semibold">Register Vehicle</span>
          </div>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-700" data-testid="add-vehicle-close">
            <X size={16} />
          </button>
        </div>

        <form onSubmit={submit} className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Vehicle number</label>
              <input value={form.number} onChange={(e) => setForm((f) => ({ ...f, number: e.target.value }))}
                placeholder="AS-01-XY-1234" required minLength={3}
                className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] font-mono uppercase" data-testid="vehicle-number-input" />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Type</label>
              <select value={form.type} onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}
                className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] bg-white" data-testid="vehicle-type-select">
                {TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Latitude</label>
              <input value={form.lat} onChange={(e) => setForm((f) => ({ ...f, lat: e.target.value }))} required
                className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] font-mono" data-testid="vehicle-lat-input" />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Longitude</label>
              <input value={form.lng} onChange={(e) => setForm((f) => ({ ...f, lng: e.target.value }))} required
                className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] font-mono" data-testid="vehicle-lng-input" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Destination</label>
              <input value={form.destination} onChange={(e) => setForm((f) => ({ ...f, destination: e.target.value }))}
                placeholder="Optional"
                className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px]" data-testid="vehicle-destination-input" />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Commodity</label>
              <select value={form.commodity} onChange={(e) => setForm((f) => ({ ...f, commodity: e.target.value }))}
                className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] bg-white" data-testid="vehicle-commodity-select">
                {COMMODITIES.map((c) => <option key={c} value={c}>{c ? c.replace("_", " ") : "— None —"}</option>)}
              </select>
            </div>
          </div>
          <button type="submit" disabled={saving}
            className="w-full h-11 rounded-md bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] disabled:opacity-60 text-white text-[13px] font-medium flex items-center justify-center gap-2 transition-colors"
            data-testid="vehicle-submit-button">
            {saving ? <Loader2 size={15} className="animate-spin" /> : <Truck size={15} />}
            {saving ? "Registering…" : "Register Vehicle"}
          </button>
        </form>
      </div>
    </div>
  );
}
