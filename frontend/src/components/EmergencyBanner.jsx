import { useEffect, useState } from "react";
import { AlertOctagon, X } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const GOV_ROLES = ["SUPER_ADMIN", "GOVERNMENT_ADMIN", "GOVERNMENT_OFFICER", "DISTRICT_OFFICER"];

export default function EmergencyBanner({ zones: zonesProp, onChanged }) {
  const { user } = useAuth();
  const isGov = user && GOV_ROLES.includes(user.role);
  const [zones, setZones] = useState(zonesProp || null);

  const fetchZones = async () => {
    try {
      const { data } = await api.get("/emergency-zones");
      setZones(data);
    } catch (e) { /* keep last */ }
  };

  useEffect(() => {
    if (zonesProp !== undefined) {
      setZones(zonesProp);
      return;
    }
    fetchZones();
    const t = setInterval(fetchZones, 15000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zonesProp]);

  const endZone = async (id) => {
    try {
      await api.patch(`/emergency-zones/${id}/end`);
      toast.success("Emergency ended — removed from all maps and alerts");
      if (onChanged) onChanged();
      else fetchZones();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Unable to end emergency");
    }
  };

  if (!zones || zones.length === 0) return null;

  return (
    <div
      className="flex-shrink-0 bg-[#8A1512] text-white px-5 py-2 flex items-center gap-2.5 text-[12px] flex-wrap"
      data-testid="emergency-banner"
    >
      <AlertOctagon size={14} className="flex-shrink-0" />
      <span className="font-semibold uppercase tracking-widest text-[10px]">Emergency Declared</span>
      {zones.map((z) => (
        <span key={z.id} className="inline-flex items-center gap-1.5 bg-white/10 rounded-full px-2.5 py-0.5" data-testid={`emergency-zone-chip-${z.id}`}>
          {z.name} ({z.radius_km} km)
          {isGov && (
            <button
              onClick={() => endZone(z.id)}
              title="End this emergency"
              className="hover:bg-white/20 rounded-full p-0.5 transition-colors"
              data-testid={`end-zone-${z.id}`}
            >
              <X size={11} />
            </button>
          )}
        </span>
      ))}
      <span className="ml-auto hidden md:block text-[11px] opacity-80 truncate max-w-md">{zones[0].message}</span>
    </div>
  );
}
