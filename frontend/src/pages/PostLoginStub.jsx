import { Link } from "react-router-dom";
import { LogOut, Building2, ShieldCheck, Truck, Radio, User } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const roleMeta = {
  GOVERNMENT_ADMIN: { label: "Government Admin", icon: ShieldCheck, tint: "var(--accent-primary)" },
  GOVERNMENT_OFFICER: { label: "Government Officer", icon: ShieldCheck, tint: "var(--accent-primary)" },
  DISTRICT_OFFICER: { label: "District Officer", icon: ShieldCheck, tint: "var(--accent-primary)" },
  SUPER_ADMIN: { label: "Super Admin", icon: ShieldCheck, tint: "var(--accent-primary)" },
  LOGISTICS_OPERATOR: { label: "Logistics Operator", icon: Truck, tint: "#1E8E3E" },
  FIELD_OFFICER: { label: "Field Officer", icon: Radio, tint: "#C77C00" },
  DRIVER: { label: "Driver", icon: Radio, tint: "#C77C00" },
  PUBLIC_USER: { label: "Public User", icon: User, tint: "#5B6470" },
};

export default function PostLoginStub({ pageTitle }) {
  const { user, logout } = useAuth();
  if (!user || typeof user !== "object") return null;
  const meta = roleMeta[user.role] || roleMeta.PUBLIC_USER;
  const Icon = meta.icon;

  return (
    <div className="min-h-screen bg-[var(--surface-base)]">
      <header className="border-b hairline bg-white">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-sm bg-[var(--accent-primary)] flex items-center justify-center text-white">
              <Building2 size={16} />
            </div>
            <div className="leading-tight">
              <div className="text-[13px] font-semibold">NERIS</div>
              <div className="text-[10px] uppercase tracking-widest text-neutral-500">NER Intelligence System</div>
            </div>
          </Link>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-[12px] text-neutral-600">
              <span className="status-dot" style={{ background: "#1E8E3E" }} />
              Live · Last updated 12s ago
            </div>
            <div className="flex items-center gap-2 pl-4 border-l hairline">
              <div
                className="w-7 h-7 rounded-sm flex items-center justify-center"
                style={{ backgroundColor: `${meta.tint}15`, color: meta.tint }}
              >
                <Icon size={14} />
              </div>
              <div className="leading-tight">
                <div className="text-[12px] font-medium" data-testid="auth-user-name">{user.name}</div>
                <div className="text-[10px] uppercase tracking-widest text-neutral-500" data-testid="auth-user-role">{meta.label}</div>
              </div>
            </div>
            <button
              onClick={logout}
              data-testid="logout-button"
              className="ml-2 h-8 px-3 rounded-md border hairline text-[12px] hover:bg-[var(--surface-sunken)] flex items-center gap-1.5"
            >
              <LogOut size={13} /> Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-12">
        <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold">
          {meta.label}
        </div>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight" data-testid="post-login-title">
          {pageTitle}
        </h1>
        <p className="mt-3 text-[14px] text-neutral-600 max-w-2xl">
          You are signed in. This surface is scaffolded — the full page will be built in the next iteration.
        </p>

        <div className="mt-10 grid sm:grid-cols-3 gap-4">
          {[
            { k: "Signed in as", v: user.email },
            { k: "Organization", v: user.organization || "—" },
            { k: "Department", v: user.department || "—" },
          ].map((c) => (
            <div key={c.k} className="p-5 border hairline rounded-md bg-white">
              <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold">{c.k}</div>
              <div className="mt-2 text-[14px] text-[var(--text-primary)] break-words">{c.v}</div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
