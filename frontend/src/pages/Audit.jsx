import { useCallback, useEffect, useState } from "react";
import { ScrollText, ArrowRight } from "lucide-react";
import api from "@/lib/api";
import NavRail from "@/components/NavRail";
import PageHeader from "@/components/PageHeader";

function timeAgo(iso) {
  if (!iso) return "—";
  const d = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  return d < 1 ? "just now" : d < 60 ? `${d}m ago` : `${Math.floor(d / 60)}h ago`;
}

export default function Audit() {
  const [entries, setEntries] = useState(null);
  const [error, setError] = useState("");

  const fetchAll = useCallback(async () => {
    try {
      const { data } = await api.get("/audit");
      setEntries(data);
      setError("");
    } catch (e) {
      setError(e.response?.status === 403 ? "Audit log is restricted to government roles." : "Unable to load audit log.");
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 15000);
    return () => clearInterval(t);
  }, [fetchAll]);

  return (
    <div className="h-screen flex bg-[var(--surface-base)] overflow-hidden" data-testid="audit-page">
      <NavRail />
      <div className="flex-1 flex flex-col min-w-0">
        <PageHeader title="AUDIT LOG" chip="GOVERNMENT ACTIONS · APPEND-ONLY" />
        <div className="flex-1 overflow-y-auto p-5 max-w-5xl">
          {error && (
            <div className="bg-white border hairline rounded-md p-10 text-center text-[13px] text-neutral-500" data-testid="audit-restricted">{error}</div>
          )}
          {!error && (
            <div className="bg-white border hairline rounded-md overflow-hidden">
              <table className="w-full text-[13px]" data-testid="audit-table">
                <thead>
                  <tr className="border-b hairline text-left text-[10px] uppercase tracking-widest text-neutral-500">
                    <th className="px-4 py-3 font-semibold">Time</th>
                    <th className="px-4 py-3 font-semibold">Official</th>
                    <th className="px-4 py-3 font-semibold">Action</th>
                    <th className="px-4 py-3 font-semibold">Target</th>
                    <th className="px-4 py-3 font-semibold">Change</th>
                    <th className="px-4 py-3 font-semibold">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {!entries && [1, 2, 3].map((n) => (
                    <tr key={n} className="border-b hairline">
                      {[...Array(6)].map((_, i) => <td key={i} className="px-4 py-3"><div className="h-3.5 bg-[var(--surface-sunken)] rounded animate-pulse" /></td>)}
                    </tr>
                  ))}
                  {entries && entries.length === 0 && (
                    <tr><td colSpan={6} className="px-4 py-12 text-center text-neutral-500" data-testid="audit-empty">
                      <ScrollText size={18} className="mx-auto mb-2 text-neutral-300" />No government actions recorded yet.
                    </td></tr>
                  )}
                  {entries && entries.map((a) => (
                    <tr key={a.id} className="border-b hairline hover:bg-[var(--surface-base)]" data-testid={`audit-row-${a.id}`}>
                      <td className="px-4 py-3 text-[11px] font-mono text-neutral-500 whitespace-nowrap">{timeAgo(a.timestamp)}</td>
                      <td className="px-4 py-3">
                        <div className="text-[12.5px] font-medium">{a.official_name}</div>
                        <div className="text-[10.5px] text-neutral-500 font-mono">{a.official_email}</div>
                      </td>
                      <td className="px-4 py-3 text-[12px] font-medium">{(a.action_type || "").replace(/_/g, " ")}</td>
                      <td className="px-4 py-3 text-neutral-600">{a.target_name}</td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1.5 text-[11.5px]">
                          <span className="text-neutral-500">{a.old_state}</span>
                          <ArrowRight size={11} className="text-neutral-400" />
                          <span className="font-semibold">{a.new_state}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3 text-neutral-600 max-w-[220px] truncate" title={a.reason}>{a.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
