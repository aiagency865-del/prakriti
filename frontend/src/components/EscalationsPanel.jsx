import { useCallback, useEffect, useState } from "react";
import { Bot, Timer, ShieldCheck, OctagonX, Navigation, Loader2 } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "@/lib/api";
import { ensureWS, subscribeWS } from "@/lib/ws";

const STATUS_META = {
  ACKED: { label: "Monitoring", color: "#1B4B66" },
  AUTO_BLOCKED: { label: "Auto-blocked", color: "#C4281C" },
  BLOCKED_MANUAL: { label: "Blocked by officer", color: "#C4281C" },
};

function fmtCountdown(deadlineIso, now) {
  const ms = new Date(deadlineIso).getTime() - now;
  if (ms <= 0) return "auto-blocking…";
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export default function EscalationsPanel() {
  const [data, setData] = useState(null);
  const [tripsInfo, setTripsInfo] = useState(null);
  const [now, setNow] = useState(Date.now());
  const [denied, setDenied] = useState(false);
  const [acting, setActing] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const [{ data: esc }, { data: ts }] = await Promise.all([
        api.get("/ai/escalations"),
        api.get("/trips/summary"),
      ]);
      setData(esc);
      setTripsInfo(ts);
    } catch (e) {
      if (e.response?.status === 403) setDenied(true);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 15000);
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => { clearInterval(t); clearInterval(tick); };
  }, [fetchAll]);

  useEffect(() => {
    ensureWS();
    const unsub = subscribeWS((msg) => {
      if (msg.type === "AI_ESCALATION") {
        toast.warning(`AI alert: ${msg.road_name} — ${msg.hazard.toLowerCase()} risk ${Math.round(msg.probability * 100)}%. Respond within 5 min or the road auto-blocks.`, { duration: 8000 });
        fetchAll();
      } else if (msg.type === "ROAD_STATUS_CHANGED") {
        fetchAll();
      }
    });
    return unsub;
  }, [fetchAll]);

  if (denied) return null;

  const ack = async (id, action) => {
    setActing(id + action);
    try {
      await api.post(`/ai/escalations/${id}/ack`, { action });
      toast.success(action === "BLOCK_NOW" ? "Road blocked and drivers rerouted" : "Marked as monitoring — auto-block cancelled");
      fetchAll();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Action failed");
    } finally {
      setActing(null);
    }
  };

  const pending = (data?.escalations || []).filter((e) => e.status === "PENDING");
  const history = (data?.escalations || []).filter((e) => e.status !== "PENDING").slice(0, 4);

  return (
    <div className="border-b hairline" data-testid="escalations-panel">
      <div className="px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-widest text-neutral-500 font-semibold">
          <Bot size={13} /> AI Escalations
        </div>
        <div className="flex items-center gap-2">
          {pending.length > 0 && (
            <span className="text-[9.5px] font-semibold px-1.5 py-0.5 rounded bg-red-50 text-red-700" data-testid="escalations-pending-count">
              {pending.length} PENDING
            </span>
          )}
          {tripsInfo && (
            <span className="text-[9.5px] font-mono px-1.5 py-0.5 rounded bg-[var(--surface-sunken)] text-neutral-600 flex items-center gap-1" data-testid="trips-active-count">
              <Navigation size={10} /> {tripsInfo.active_count} TRIPS
            </span>
          )}
        </div>
      </div>

      {data && pending.length === 0 && (
        <div className="px-4 pb-3 text-[11.5px] text-neutral-500" data-testid="escalations-clear">
          No corridor above the {Math.round((data?.threshold || 0.75) * 100)}% hazard threshold.
        </div>
      )}

      {pending.map((e) => (
        <div key={e.id} className="px-4 py-3 border-t hairline bg-red-50/50" data-testid={`escalation-row-${e.id}`}>
          <div className="flex items-center justify-between gap-2">
            <div className="text-[12.5px] font-medium">{e.road_name}</div>
            <span className="text-[10px] font-mono font-semibold text-red-700 flex items-center gap-1" data-testid={`escalation-countdown-${e.id}`}>
              <Timer size={11} /> {fmtCountdown(e.deadline_at, now)}
            </span>
          </div>
          <div className="mt-1 text-[11px] text-neutral-600">
            {e.hazard === "FLOOD" ? "Flood" : "Landslide"} probability <span className="font-semibold tabular-nums">{Math.round(e.probability * 100)}%</span> — auto-blocks if unanswered
          </div>
          <div className="flex gap-2 mt-2">
            <button
              onClick={() => ack(e.id, "MONITOR")}
              disabled={acting === e.id + "MONITOR"}
              className="h-7 px-2.5 rounded-md border hairline text-[11px] font-medium hover:bg-white flex items-center gap-1"
              data-testid={`escalation-monitor-${e.id}`}
            >
              {acting === e.id + "MONITOR" ? <Loader2 size={11} className="animate-spin" /> : <ShieldCheck size={11} />}
              Acknowledge
            </button>
            <button
              onClick={() => ack(e.id, "BLOCK_NOW")}
              disabled={acting === e.id + "BLOCK_NOW"}
              className="h-7 px-2.5 rounded-md bg-red-700 hover:bg-red-800 text-white text-[11px] font-medium flex items-center gap-1"
              data-testid={`escalation-block-${e.id}`}
            >
              {acting === e.id + "BLOCK_NOW" ? <Loader2 size={11} className="animate-spin" /> : <OctagonX size={11} />}
              Block now
            </button>
          </div>
        </div>
      ))}

      {history.map((e) => {
        const meta = STATUS_META[e.status] || { label: e.status, color: "#8A9099" };
        return (
          <div key={e.id} className="px-4 py-2 border-t hairline flex items-center gap-2 text-[11px] text-neutral-500" data-testid={`escalation-history-${e.id}`}>
            <span className="truncate">{e.road_name}</span>
            <span className="tabular-nums">{Math.round(e.probability * 100)}%</span>
            <span className="ml-auto font-semibold uppercase tracking-wider text-[9px]" style={{ color: meta.color }}>{meta.label}</span>
          </div>
        );
      })}

      {tripsInfo && tripsInfo.active_count > 0 && (
        <div className="px-4 py-2.5 border-t hairline" data-testid="trips-by-road">
          <div className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold mb-1.5">
            Vehicles per corridor
          </div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(tripsInfo.by_road).map(([rid, info]) => (
              <span key={rid} className="text-[10px] px-2 py-1 rounded-full border hairline bg-white text-neutral-700" data-testid={`trips-road-${rid}`}>
                {info.name.split(" ")[0]} · <span className="font-semibold tabular-nums">{info.count}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
