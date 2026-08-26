import { useCallback, useEffect, useState } from "react";
import { X, Truck, Bike, Car, Ambulance, Package, Plus } from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import NavRail from "@/components/NavRail";
import NerMap from "@/components/NerMap";
import AddVehicleModal from "@/components/AddVehicleModal";

const TYPE_META = {
  TRUCK: { label: "Truck", icon: Truck },
  LIGHT: { label: "Light", icon: Car },
  SUV: { label: "SUV", icon: Car },
  TWO_WHEELER: { label: "2W", icon: Bike },
  EMERGENCY: { label: "Emergency", icon: Ambulance },
};
const STATUS_META = {
  IN_TRANSIT: { label: "In Transit", color: "#1B4B66" },
  DELAYED: { label: "Delayed", color: "#C77C00" },
  IDLE: { label: "Idle", color: "#8A9099" },
};

function riskMeta(risk) {
  if (risk >= 60) return { label: "HIGH", color: "#C4281C" };
  if (risk >= 30) return { label: "MEDIUM", color: "#C77C00" };
  return { label: "LOW", color: "#1E8E3E" };
}

function eta(mins) {
  if (mins == null) return "—";
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

const ADD_ROLES = ["SUPER_ADMIN", "GOVERNMENT_ADMIN", "GOVERNMENT_OFFICER", "DISTRICT_OFFICER", "FIELD_OFFICER", "LOGISTICS_OPERATOR"];

export default function Vehicles() {
  const { user } = useAuth();
  const canAdd = user && ADD_ROLES.includes(user.role);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [selected, setSelected] = useState(null);
  const [addOpen, setAddOpen] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const { data: d } = await api.get("/dashboard/summary");
      setData(d);
      setError("");
    } catch (e) {
      setError("Unable to load fleet data. Please retry.");
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 15000);
    return () => clearInterval(t);
  }, [fetchAll]);

  const vehicles = (data?.vehicles || []).filter(
    (v) => (typeFilter === "ALL" || v.type === typeFilter) && (statusFilter === "ALL" || v.status === statusFilter)
  );

  return (
    <div className="h-screen flex bg-[var(--surface-base)] overflow-hidden" data-testid="vehicles-page">
      <NavRail />
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 flex-shrink-0 bg-white border-b hairline px-5 flex items-center justify-between">
          <h1 className="text-[15px] font-semibold tracking-tight">FLEET TRACKING</h1>
          <div className="flex items-center gap-2">
            {canAdd && (
              <button
                onClick={() => setAddOpen(true)}
                className="h-8 px-3 rounded-md bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] text-white text-[12px] font-medium flex items-center gap-1.5 transition-colors"
                data-testid="add-vehicle-button"
              >
                <Plus size={13} /> Add Vehicle
              </button>
            )}
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="h-8 px-2 border hairline rounded-md text-[12px] bg-white"
              data-testid="vehicles-filter-type"
            >
              <option value="ALL">All types</option>
              {Object.entries(TYPE_META).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-8 px-2 border hairline rounded-md text-[12px] bg-white"
              data-testid="vehicles-filter-status"
            >
              <option value="ALL">All statuses</option>
              {Object.entries(STATUS_META).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}
            </select>
          </div>
        </header>

        {error && (
          <div className="bg-red-50 border-b border-red-200 px-5 py-2 text-[12px] text-red-800" data-testid="vehicles-error">{error}</div>
        )}

        <div className="flex-1 overflow-auto p-5">
          <div className="bg-white border hairline rounded-md overflow-hidden">
            <table className="w-full text-[13px]" data-testid="vehicles-table">
              <thead>
                <tr className="border-b hairline text-left text-[10px] uppercase tracking-widest text-neutral-500">
                  <th className="px-4 py-3 font-semibold">Vehicle</th>
                  <th className="px-4 py-3 font-semibold">Type</th>
                  <th className="px-4 py-3 font-semibold">Destination</th>
                  <th className="px-4 py-3 font-semibold text-right">Speed</th>
                  <th className="px-4 py-3 font-semibold text-right">ETA</th>
                  <th className="px-4 py-3 font-semibold">Route Risk</th>
                  <th className="px-4 py-3 font-semibold">Commodity</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody>
                {!data && [1, 2, 3, 4, 5, 6].map((n) => (
                  <tr key={n} className="border-b hairline">
                    {[...Array(8)].map((_, i) => (
                      <td key={i} className="px-4 py-3"><div className="h-3.5 bg-[var(--surface-sunken)] rounded animate-pulse" /></td>
                    ))}
                  </tr>
                ))}
                {data && vehicles.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center text-neutral-500" data-testid="vehicles-empty">
                      No vehicles match these filters.
                    </td>
                  </tr>
                )}
                {data && vehicles.map((v) => {
                  const T = TYPE_META[v.type] || TYPE_META.LIGHT;
                  const S = STATUS_META[v.status] || STATUS_META.IDLE;
                  const R = riskMeta(v.risk);
                  return (
                    <tr
                      key={v.id}
                      onClick={() => setSelected(v)}
                      className="border-b hairline hover:bg-[var(--surface-base)] cursor-pointer transition-colors"
                      data-testid={`vehicle-row-${v.id}`}
                    >
                      <td className="px-4 py-3 font-medium tabular-nums">{v.number}</td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1.5 text-neutral-600">
                          <T.icon size={14} strokeWidth={1.75} /> {T.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-neutral-600">{v.destination}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{v.speed} km/h</td>
                      <td className="px-4 py-3 text-right tabular-nums">{eta(v.eta_minutes)}</td>
                      <td className="px-4 py-3">
                        <span
                          className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded"
                          style={{ background: `${R.color}14`, color: R.color }}
                          data-testid={`vehicle-risk-${v.id}`}
                        >
                          <span className="status-dot" style={{ background: R.color }} />
                          {R.label} · {v.risk}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-neutral-600 capitalize">{(v.commodity || "—").toLowerCase().replace("_", " ")}</td>
                      <td className="px-4 py-3">
                        <span className="text-[11px] font-medium" style={{ color: S.color }}>{S.label}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {addOpen && <AddVehicleModal onClose={() => setAddOpen(false)} onCreated={() => fetchAll()} />}

      {selected && (
        <>
          <div className="fixed inset-0 bg-black/20 z-40" onClick={() => setSelected(null)} />
          <aside className="fixed top-0 right-0 h-full w-[420px] bg-white border-l hairline z-50 flex flex-col shadow-xl" data-testid="vehicle-drawer">
            <div className="px-5 py-4 border-b hairline flex items-center justify-between">
              <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold">Vehicle Detail</div>
              <button onClick={() => setSelected(null)} className="text-neutral-400 hover:text-neutral-700" data-testid="vehicle-drawer-close">
                <X size={16} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              <div className="text-[17px] font-semibold tracking-tight tabular-nums">{selected.number}</div>
              <div className="text-[12px] text-neutral-500 mt-0.5">
                {(TYPE_META[selected.type] || {}).label} · GPS feed: DEMO
              </div>

              <div className="mt-4 h-52 border hairline rounded-md overflow-hidden relative" data-testid="vehicle-minimap">
                <NerMap
                  roads={data?.roads}
                  vehicles={[selected]}
                  incidents={[]}
                  layers={{ roads: true, vehicles: true, incidents: false }}
                  center={[selected.lng, selected.lat]}
                  zoom={8.5}
                />
              </div>

              <dl className="mt-4 space-y-0 border hairline rounded-md divide-y divide-[var(--border-default)]">
                {[
                  ["Cargo", (selected.commodity || "—").toLowerCase().replace("_", " ")],
                  ["Destination", selected.destination],
                  ["ETA", eta(selected.eta_minutes)],
                  ["Route risk", `${selected.risk}%`],
                  ["Route", selected.risk >= 60 ? "Unsafe" : selected.risk >= 30 ? "At risk" : "Safe"],
                  ["Status", (STATUS_META[selected.status] || {}).label],
                  ["Speed", `${selected.speed} km/h`],
                  ["Position", `${selected.lat.toFixed(3)}°N ${selected.lng.toFixed(3)}°E`],
                ].map(([k, val]) => (
                  <div key={k} className="flex items-center justify-between px-3.5 py-2.5">
                    <dt className="text-[11px] uppercase tracking-wider text-neutral-500 font-medium">{k}</dt>
                    <dd className="text-[13px] font-medium text-[var(--text-primary)] capitalize">{val}</dd>
                  </div>
                ))}
              </dl>

              <div className="mt-4 p-3 border hairline rounded-md bg-[var(--surface-base)] text-[11px] text-neutral-500 flex items-center gap-2">
                <Package size={13} />
                Telemetry and positions shown are simulated demo data.
              </div>
            </div>
          </aside>
        </>
      )}
    </div>
  );
}
