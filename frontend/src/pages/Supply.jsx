import { useCallback, useEffect, useState } from "react";
import { Pill, Wheat, Droplets, Fuel, Users } from "lucide-react";
import api from "@/lib/api";
import NavRail from "@/components/NavRail";
import PageHeader from "@/components/PageHeader";

const SEV_COLORS = { INFO: "#4C7EA8", WARNING: "#C77C00", HIGH: "#D9622B", CRITICAL: "#C4281C" };
const RISK_COLORS = { LOW: "#1E8E3E", MEDIUM: "#C77C00", HIGH: "#D9622B", CRITICAL: "#C4281C" };
const COMMODITY_ICONS = { MEDICINE: Pill, FOOD: Wheat, WATER: Droplets, FUEL: Fuel };

export default function Supply() {
  const [data, setData] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const { data: d } = await api.get("/dashboard/summary");
      setData(d);
    } catch (e) { /* keep last */ }
  }, []);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 15000);
    return () => clearInterval(t);
  }, [fetchAll]);

  const villages = data?.villages_list || data?.villages || [];

  return (
    <div className="h-screen flex bg-[var(--surface-base)] overflow-hidden" data-testid="supply-page">
      <NavRail />
      <div className="flex-1 flex flex-col min-w-0">
        <PageHeader title="SUPPLY INTELLIGENCE" chip="DEMO DATA" />
        <div className="flex-1 overflow-y-auto p-5">
          <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold mb-3">Commodity risk</div>
          <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4" data-testid="supply-commodity-cards">
            {!data && [1, 2, 3, 4].map((n) => <div key={n} className="h-24 bg-white border hairline rounded-md animate-pulse" />)}
            {data && data.supply.map((s) => {
              const Icon = COMMODITY_ICONS[s.commodity] || Wheat;
              return (
                <div key={s.commodity} className="bg-white border hairline rounded-md p-5" style={{ borderTop: `3px solid ${SEV_COLORS[s.severity]}` }} data-testid={`supply-commodity-${s.commodity.toLowerCase()}`}>
                  <div className="flex items-center gap-2.5">
                    <span className="w-9 h-9 rounded-sm flex items-center justify-center" style={{ background: `${SEV_COLORS[s.severity]}14`, color: SEV_COLORS[s.severity] }}>
                      <Icon size={17} strokeWidth={1.75} />
                    </span>
                    <div>
                      <div className="text-[14px] font-semibold capitalize">{s.commodity.toLowerCase()}</div>
                      <div className="text-[11px] font-semibold" style={{ color: SEV_COLORS[s.severity] }}>{s.severity}</div>
                    </div>
                    <div className="ml-auto text-right">
                      <div className="text-2xl font-semibold tabular-nums">{s.at_risk_count}</div>
                      <div className="text-[10px] uppercase tracking-widest text-neutral-500">at-risk</div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold mt-8 mb-3">Villages at isolation risk</div>
          <div className="bg-white border hairline rounded-md overflow-hidden">
            <table className="w-full text-[13px]" data-testid="villages-table">
              <thead>
                <tr className="border-b hairline text-left text-[10px] uppercase tracking-widest text-neutral-500">
                  <th className="px-4 py-3 font-semibold">Village / Cluster</th>
                  <th className="px-4 py-3 font-semibold">District</th>
                  <th className="px-4 py-3 font-semibold text-right">Population</th>
                  <th className="px-4 py-3 font-semibold">Isolation Risk</th>
                  <th className="px-4 py-3 font-semibold text-right">Days to Stockout</th>
                  <th className="px-4 py-3 font-semibold">Primary Commodity</th>
                </tr>
              </thead>
              <tbody>
                {!data && [1, 2, 3, 4].map((n) => (
                  <tr key={n} className="border-b hairline">
                    {[...Array(6)].map((_, i) => <td key={i} className="px-4 py-3"><div className="h-3.5 bg-[var(--surface-sunken)] rounded animate-pulse" /></td>)}
                  </tr>
                ))}
                {data && villages.map((v) => (
                  <tr key={v.id} className="border-b hairline hover:bg-[var(--surface-base)]" data-testid={`village-row-${v.id}`}>
                    <td className="px-4 py-3 font-medium">{v.name}</td>
                    <td className="px-4 py-3 text-neutral-600">{v.district}</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      <span className="inline-flex items-center gap-1"><Users size={12} className="text-neutral-400" />{v.population.toLocaleString()}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded" style={{ background: `${RISK_COLORS[v.isolation_risk]}14`, color: RISK_COLORS[v.isolation_risk] }}>
                        {v.isolation_risk}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums font-medium" style={{ color: v.days_to_stockout <= 3 ? "#C4281C" : v.days_to_stockout <= 7 ? "#C77C00" : undefined }}>
                      {v.days_to_stockout}d
                    </td>
                    <td className="px-4 py-3 text-neutral-600 capitalize">{(v.primary_commodity || "—").toLowerCase()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
