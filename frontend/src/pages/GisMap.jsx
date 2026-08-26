import { useCallback, useEffect, useState } from "react";
import { Layers } from "lucide-react";
import api from "@/lib/api";
import { ensureWS, subscribeWS } from "@/lib/ws";
import { useAuth } from "@/context/AuthContext";
import NavRail from "@/components/NavRail";
import PageHeader from "@/components/PageHeader";
import NerMap, { STATUS_COLORS } from "@/components/NerMap";
import RoadControlDrawer from "@/components/RoadControlDrawer";

export default function GisMap() {
  const { user } = useAuth();
  const canSeeLiveVehicles = user && ["SUPER_ADMIN", "GOVERNMENT_ADMIN", "GOVERNMENT_OFFICER", "DISTRICT_OFFICER", "FIELD_OFFICER"].includes(user.role);
  const [data, setData] = useState(null);
  const [zones, setZones] = useState([]);
  const [environment, setEnvironment] = useState(null);
  const [layers, setLayers] = useState({ roads: true, vehicles: true, incidents: true });
  const [selectedRoad, setSelectedRoad] = useState(null);

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
    } catch (e) { /* keep last */ }
  }, []);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 15000);
    return () => clearInterval(t);
  }, [fetchAll]);

  useEffect(() => {
    ensureWS();
    const unsub = subscribeWS((msg) => {
      if (["ROAD_STATUS_CHANGED", "INCIDENT_CREATED", "INCIDENT_VERIFIED", "EMERGENCY_DECLARED", "EMERGENCY_ENDED", "VEHICLE_ADDED"].includes(msg.type)) {
        fetchAll();
      }
    });
    return unsub;
  }, [fetchAll]);

  return (
    <div className="h-screen flex bg-[var(--surface-base)] overflow-hidden" data-testid="gis-map-page">
      <NavRail />
      <div className="flex-1 flex flex-col min-w-0">
        <PageHeader title="GIS MAP" chip="LIVE ROAD STATE" />
        <div className="flex-1 relative min-h-0">
          {data ? (
            <NerMap
              roads={data.roads}
              vehicles={canSeeLiveVehicles ? data.vehicles : []}
              incidents={data.incidents.filter((i) => i.status !== "RESOLVED")}
              layers={{ ...layers, vehicles: layers.vehicles && canSeeLiveVehicles }}
              onRoadClick={(props) => setSelectedRoad(props)}
              zones={zones}
              environment={environment}
            />
          ) : (
            <div className="absolute inset-0 bg-[var(--surface-sunken)] animate-pulse" />
          )}

          <div className="absolute top-3 right-3 bg-white border hairline rounded-md shadow-sm p-2.5 w-44 z-10" data-testid="gis-layer-control">
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-neutral-500 font-semibold mb-2">
              <Layers size={12} /> Layers
            </div>
            {[
              { key: "roads", label: "Road Status" },
              ...(canSeeLiveVehicles ? [{ key: "vehicles", label: "Vehicles (live)" }] : []),
              { key: "incidents", label: "Incidents" },
            ].map((l) => (
              <label key={l.key} className="flex items-center gap-2 py-1 text-[12px] text-neutral-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={layers[l.key]}
                  onChange={(e) => setLayers((s) => ({ ...s, [l.key]: e.target.checked }))}
                  className="w-3.5 h-3.5 accent-[var(--accent-primary)]"
                  data-testid={`gis-layer-toggle-${l.key}`}
                />
                {l.label}
              </label>
            ))}
          </div>

          <div className="absolute bottom-3 left-3 bg-white/95 border hairline rounded-md shadow-sm px-3 py-2 z-10" data-testid="gis-map-legend">
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
            </div>
          </div>
        </div>
      </div>

      {selectedRoad && (
        <RoadControlDrawer
          road={data?.roads?.features?.find((f) => f.properties.id === selectedRoad.id)?.properties || selectedRoad}
          onClose={() => setSelectedRoad(null)}
          onChanged={(updated) => { setSelectedRoad(updated); fetchAll(); }}
        />
      )}
    </div>
  );
}
