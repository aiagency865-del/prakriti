import { useCallback, useEffect, useState } from "react";
import { ShieldCheck, Loader2, Plus } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import NavRail from "@/components/NavRail";
import PageHeader from "@/components/PageHeader";
import AddIncidentModal from "@/components/AddIncidentModal";

const SEV_COLORS = { INFO: "#4C7EA8", WARNING: "#C77C00", HIGH: "#D9622B", CRITICAL: "#C4281C" };
const STATUS_COLORS_MAP = { UNVERIFIED: "#8A9099", VERIFIED: "#1E8E3E", PROVISIONALLY_BLOCKED: "#C4281C", RESOLVED: "#5B6470" };
const GOV_ROLES = ["SUPER_ADMIN", "GOVERNMENT_ADMIN", "GOVERNMENT_OFFICER", "DISTRICT_OFFICER"];
const VERIFY_ROLES = [...GOV_ROLES, "FIELD_OFFICER"];

function timeAgo(iso) {
  if (!iso) return "—";
  const d = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  return d < 1 ? "just now" : d < 60 ? `${d}m ago` : `${Math.floor(d / 60)}h ago`;
}

export default function Incidents() {
  const { user } = useAuth();
  const canVerify = user && VERIFY_ROLES.includes(user.role);
  const [incidents, setIncidents] = useState(null);
  const [acting, setActing] = useState(null);
  const [addOpen, setAddOpen] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const { data } = await api.get("/dashboard/summary");
      setIncidents(data.incidents);
    } catch (e) { /* keep last */ }
  }, []);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 10000);
    return () => clearInterval(t);
  }, [fetchAll]);

  const act = async (id, action) => {
    setActing(id);
    try {
      await api.patch(`/incidents/${id}/${action}`);
      toast.success(action === "verify" ? "Incident verified — now visible on public advisories" : "Incident rejected");
      fetchAll();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Action failed");
    } finally {
      setActing(null);
    }
  };

  return (
    <div className="h-screen flex bg-[var(--surface-base)] overflow-hidden" data-testid="incidents-page">
      <NavRail />
      <div className="flex-1 flex flex-col min-w-0">
        <PageHeader title="INCIDENTS" chip="FUSED: AI + GPS + FIELD + PUBLIC">
          {canVerify && (
            <button
              onClick={() => setAddOpen(true)}
              className="h-8 px-3 rounded-md bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] text-white text-[12px] font-medium flex items-center gap-1.5 transition-colors"
              data-testid="add-incident-button"
            >
              <Plus size={13} /> Add Incident
            </button>
          )}
        </PageHeader>
        <div className="flex-1 overflow-y-auto p-5">
          <div className="bg-white border hairline rounded-md overflow-hidden">
            <table className="w-full text-[13px]" data-testid="incidents-table">
              <thead>
                <tr className="border-b hairline text-left text-[10px] uppercase tracking-widest text-neutral-500">
                  <th className="px-4 py-3 font-semibold">ID</th>
                  <th className="px-4 py-3 font-semibold">Incident</th>
                  <th className="px-4 py-3 font-semibold">Location</th>
                  <th className="px-4 py-3 font-semibold">Severity</th>
                  <th className="px-4 py-3 font-semibold">Source</th>
                  <th className="px-4 py-3 font-semibold text-right">Conf.</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold text-right">Time</th>
                  {canVerify && <th className="px-4 py-3 font-semibold text-right">Action</th>}
                </tr>
              </thead>
              <tbody>
                {!incidents && [1, 2, 3, 4, 5].map((n) => (
                  <tr key={n} className="border-b hairline">
                    {[...Array(canVerify ? 9 : 8)].map((_, i) => <td key={i} className="px-4 py-3"><div className="h-3.5 bg-[var(--surface-sunken)] rounded animate-pulse" /></td>)}
                  </tr>
                ))}
                {incidents && incidents.map((i) => (
                  <tr key={i.id} className="border-b hairline hover:bg-[var(--surface-base)]" data-testid={`incident-table-row-${i.id}`}>
                    <td className="px-4 py-3 font-mono text-[11.5px] text-neutral-500">{i.id}</td>
                    <td className="px-4 py-3 font-medium">{i.title}</td>
                    <td className="px-4 py-3 text-neutral-600">{i.location}</td>
                    <td className="px-4 py-3">
                      <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded" style={{ background: `${SEV_COLORS[i.severity]}14`, color: SEV_COLORS[i.severity] }}>
                        {i.severity}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-neutral-600">{i.source}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{i.confidence}%</td>
                    <td className="px-4 py-3">
                      <span className="text-[10px] font-semibold" style={{ color: STATUS_COLORS_MAP[i.status] || "#8A9099" }}>
                        {(i.status || "").replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-[11px] font-mono text-neutral-400">{timeAgo(i.created_at)}</td>
                    {canVerify && (
                      <td className="px-4 py-3 text-right">
                        {i.status === "UNVERIFIED" ? (
                          <div className="inline-flex gap-1.5 justify-end">
                            <button
                              onClick={() => act(i.id, "verify")}
                              disabled={acting === i.id}
                              className="h-7 px-2.5 rounded-md border hairline text-[11px] font-medium hover:bg-[var(--accent-soft)] text-[var(--accent-primary)] inline-flex items-center gap-1"
                              data-testid={`incident-verify-${i.id}`}
                            >
                              {acting === i.id ? <Loader2 size={12} className="animate-spin" /> : <ShieldCheck size={12} />}
                              Verify
                            </button>
                            <button
                              onClick={() => act(i.id, "reject")}
                              disabled={acting === i.id}
                              className="h-7 px-2.5 rounded-md border hairline text-[11px] font-medium text-neutral-600 hover:bg-red-50 hover:text-red-700 inline-flex items-center gap-1"
                              data-testid={`incident-reject-${i.id}`}
                            >
                              Reject
                            </button>
                          </div>
                        ) : (
                          <span className="text-[10px] text-neutral-400">—</span>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {addOpen && <AddIncidentModal onClose={() => setAddOpen(false)} onCreated={() => fetchAll()} />}
    </div>
  );
}
