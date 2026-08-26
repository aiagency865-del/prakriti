import { useState } from "react";
import { X, ShieldCheck, Loader2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { STATUS_COLORS } from "@/components/NerMap";

const STATUS_LABELS = {
  OPEN: "Open", AT_RISK: "At Risk", RESTRICTED: "Restricted",
  BLOCKED: "Blocked", GOVERNMENT_CLOSED: "Gov Closed", UNKNOWN: "Unknown",
};

const GOV_ROLES = ["SUPER_ADMIN", "GOVERNMENT_ADMIN", "GOVERNMENT_OFFICER", "DISTRICT_OFFICER"];

export default function RoadControlDrawer({ road, onClose, onChanged }) {
  const { user } = useAuth();
  const canEdit = user && GOV_ROLES.includes(user.role);
  const [action, setAction] = useState("OPEN");
  const [reason, setReason] = useState("");
  const [duration, setDuration] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  if (!road) return null;
  const statusColor = STATUS_COLORS[road.status] || STATUS_COLORS.UNKNOWN;

  const submit = async () => {
    setSaving(true);
    setError("");
    try {
      const { data } = await api.patch(`/roads/${road.id}/status`, {
        status: action,
        reason: reason.trim(),
        expected_duration: duration.trim() || null,
      });
      toast.success("Road status updated");
      setConfirming(false);
      onChanged?.(data);
    } catch (e) {
      setError(formatApiErrorDetail(e.response?.data?.detail) || "Unable to update road status. Please retry.");
      setConfirming(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/20 z-40" onClick={onClose} data-testid="road-drawer-backdrop" />
      <aside
        className="fixed top-0 right-0 h-full w-96 bg-white border-l hairline z-50 flex flex-col shadow-xl"
        data-testid="road-control-drawer"
      >
        <div className="px-5 py-4 border-b hairline flex items-center justify-between">
          <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold">Road Control</div>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-700" data-testid="road-drawer-close">
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          <div className="text-[17px] font-semibold tracking-tight" data-testid="road-drawer-name">{road.name}</div>
          <div className="text-[12px] text-neutral-500 mt-0.5">{road.district} · {road.road_class}</div>

          <div className="mt-4 p-3.5 border hairline rounded-md bg-[var(--surface-base)]">
            <div className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold mb-2">Current status</div>
            <div className="flex items-center gap-2">
              <span className="status-dot" style={{ background: statusColor }} />
              <span className="text-[14px] font-semibold" style={{ color: statusColor }} data-testid="road-drawer-status">
                {STATUS_LABELS[road.status] || road.status}
              </span>
              <span className="ml-auto text-[12px] tabular-nums text-neutral-500">risk {road.risk}</span>
            </div>
            {road.status_reason && (
              <div className="mt-2 text-[12px] text-neutral-600">
                <span className="font-medium">Reason:</span> {road.status_reason}
              </div>
            )}
            {road.expected_duration && (
              <div className="mt-1 text-[12px] text-neutral-600">
                <span className="font-medium">Expected duration:</span> {road.expected_duration}
              </div>
            )}
          </div>

          {canEdit ? (
            <div className="mt-6">
              <div className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold mb-2">Action</div>
              <div className="space-y-2" data-testid="road-action-group">
                {[
                  { v: "OPEN", label: "Open", hint: "Restore normal operations" },
                  { v: "RESTRICTED", label: "Restrict", hint: "Limited vehicle classes only" },
                  { v: "BLOCKED", label: "Block", hint: "Close to all traffic" },
                ].map((o) => (
                  <label
                    key={o.v}
                    className={`flex items-start gap-2.5 p-3 border rounded-md cursor-pointer transition-colors ${
                      action === o.v ? "border-[var(--accent-primary)] bg-[var(--accent-soft)]" : "hairline hover:bg-[var(--surface-base)]"
                    }`}
                  >
                    <input
                      type="radio"
                      name="road-action"
                      value={o.v}
                      checked={action === o.v}
                      onChange={() => setAction(o.v)}
                      className="mt-0.5 accent-[var(--accent-primary)]"
                      data-testid={`road-action-${o.v.toLowerCase()}`}
                    />
                    <span>
                      <span className="text-[13px] font-medium block">{o.label}</span>
                      <span className="text-[11px] text-neutral-500">{o.hint}</span>
                    </span>
                  </label>
                ))}
              </div>

              <div className="mt-4">
                <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Reason</label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={3}
                  placeholder="Official reason for this action…"
                  className="mt-1.5 w-full px-3 py-2 border hairline rounded-md text-[13px] focus:border-[var(--accent-primary)] outline-none resize-none"
                  data-testid="road-reason-input"
                />
              </div>
              <div className="mt-3">
                <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-semibold">Expected duration</label>
                <input
                  value={duration}
                  onChange={(e) => setDuration(e.target.value)}
                  placeholder="e.g. 3–5 days"
                  className="mt-1.5 w-full h-10 px-3 border hairline rounded-md text-[13px] focus:border-[var(--accent-primary)] outline-none"
                  data-testid="road-duration-input"
                />
              </div>

              {error && (
                <div className="mt-3 p-3 border rounded-md bg-red-50 border-red-200 text-red-800 text-[12px]" data-testid="road-update-error">
                  {error}
                </div>
              )}

              <button
                onClick={() => setConfirming(true)}
                disabled={reason.trim().length < 3}
                className="mt-4 w-full h-11 rounded-md bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] disabled:opacity-50 text-white text-[13px] font-medium flex items-center justify-center gap-2 transition-colors"
                data-testid="road-confirm-button"
              >
                <ShieldCheck size={15} /> Confirm Official Action
              </button>
              <div className="mt-2 text-[11px] text-neutral-500 text-center">
                This action is logged in the audit trail.
              </div>
            </div>
          ) : (
            <div className="mt-6 p-3.5 border hairline rounded-md bg-[var(--surface-base)] text-[12px] text-neutral-600 flex items-start gap-2" data-testid="road-readonly-note">
              <AlertTriangle size={14} className="mt-0.5 flex-shrink-0 text-neutral-400" />
              Road status is managed by government authorities. Your role has read-only access.
            </div>
          )}
        </div>
      </aside>

      {confirming && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/30" data-testid="road-confirm-modal">
          <div className="bg-white rounded-md border hairline shadow-xl w-[400px] p-5">
            <div className="text-[15px] font-semibold">Confirm status change</div>
            <p className="mt-2 text-[13px] text-neutral-600 leading-relaxed">
              This will change <span className="font-medium">{road.name}</span> from{" "}
              <span className="font-medium" style={{ color: statusColor }}>{STATUS_LABELS[road.status]}</span> to{" "}
              <span className="font-medium" style={{ color: STATUS_COLORS[action] }}>{STATUS_LABELS[action]}</span>.
              This action is logged and cannot be undone silently.
            </p>
            <div className="mt-5 flex gap-2 justify-end">
              <button
                onClick={() => setConfirming(false)}
                className="h-9 px-4 rounded-md border hairline text-[13px] hover:bg-[var(--surface-sunken)]"
                data-testid="road-confirm-modal-cancel"
              >
                Cancel
              </button>
              <button
                onClick={submit}
                disabled={saving}
                className="h-9 px-4 rounded-md bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] text-white text-[13px] font-medium flex items-center gap-2"
                data-testid="road-confirm-modal-confirm"
              >
                {saving && <Loader2 size={14} className="animate-spin" />}
                {saving ? "Applying…" : "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
