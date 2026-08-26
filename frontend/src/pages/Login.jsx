import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Building2, ArrowLeft, ArrowRight, Loader2, Truck, ShieldCheck, Radio, User, Eye, EyeOff } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { formatApiErrorDetail } from "@/lib/api";

const ROLE_TABS = [
  {
    key: "government",
    label: "Government",
    icon: ShieldCheck,
    subtitle: "State authorities & district officers",
    demoEmail: "gov.admin@neris.demo",
    color: "var(--accent-primary)",
  },
  {
    key: "logistics",
    label: "Logistics Client",
    icon: Truck,
    subtitle: "Fleet operators & freight networks",
    demoEmail: "logistics@neris.demo",
    color: "#1E8E3E",
  },
  {
    key: "field",
    label: "Field Officer",
    icon: Radio,
    subtitle: "On-ground reporting",
    demoEmail: "field@neris.demo",
    color: "#C77C00",
  },
  {
    key: "public",
    label: "Public",
    icon: User,
    subtitle: "Read-only advisories",
    demoEmail: "public@neris.demo",
    color: "#5B6470",
  },
];

const roleForRoute = {
  GOVERNMENT_ADMIN: "/command-center",
  GOVERNMENT_OFFICER: "/command-center",
  DISTRICT_OFFICER: "/command-center",
  SUPER_ADMIN: "/command-center",
  LOGISTICS_OPERATOR: "/logistics",
  FIELD_OFFICER: "/field",
  DRIVER: "/field",
  PUBLIC_USER: "/public",
};

export default function Login() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { login, user } = useAuth();

  const initialRole = params.get("role") || "government";
  const [activeRole, setActiveRole] = useState(
    ROLE_TABS.find((t) => t.key === initialRole)?.key || "government"
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (user && typeof user === "object") {
      navigate(roleForRoute[user.role] || "/command-center", { replace: true });
    }
  }, [user, navigate]);

  const activeTab = ROLE_TABS.find((t) => t.key === activeRole);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const u = await login(email.trim().toLowerCase(), password);
      navigate(roleForRoute[u.role] || "/command-center", { replace: true });
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || "Incorrect email or password");
    } finally {
      setLoading(false);
    }
  };

  const useDemo = () => {
    setEmail(activeTab.demoEmail);
    setPassword("Demo@2026");
    setError("");
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-[var(--surface-base)]">
      {/* LEFT — brand / narrative */}
      <div className="hidden lg:flex flex-col justify-between p-10 bg-white border-r hairline relative overflow-hidden">
        <div className="absolute inset-0 grid-backdrop opacity-60 pointer-events-none" />
        <div className="relative flex items-center gap-2">
          <div className="w-8 h-8 rounded-sm bg-[var(--accent-primary)] flex items-center justify-center text-white">
            <Building2 size={17} />
          </div>
          <div className="leading-tight">
            <div className="text-[13px] font-semibold">NERIS</div>
            <div className="text-[10px] uppercase tracking-widest text-neutral-500">NER Intelligence System</div>
          </div>
        </div>

        <div className="relative">
          <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold">Command surface</div>
          <h2 className="mt-3 text-3xl xl:text-4xl font-semibold tracking-tight leading-tight max-w-md">
            One operational picture for a fragile geography.
          </h2>
          <p className="mt-4 text-[14px] leading-relaxed text-neutral-600 max-w-md">
            Live road accessibility, hazard prediction, vehicle-specific routing, and supply continuity — fused into a single, government-verified surface.
          </p>

          <div className="mt-10 space-y-3 max-w-md">
            {[
              { c: "#1E8E3E", k: "OPEN", v: "Corridors operating normally" },
              { c: "#C77C00", k: "AT RISK", v: "Elevated hazard indicators" },
              { c: "#C4281C", k: "BLOCKED", v: "Field-verified disruption" },
              { c: "#8A1512", k: "GOV CLOSED", v: "Government-declared closure" },
            ].map((r) => (
              <div key={r.k} className="flex items-center gap-3 text-[13px]">
                <span className="status-dot" style={{ background: r.c }} />
                <span className="font-medium tracking-wider text-[11px] uppercase w-24 text-neutral-700">{r.k}</span>
                <span className="text-neutral-600">{r.v}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="relative flex items-center justify-between text-[11px] text-neutral-500">
          <div className="font-mono">SIH26002 · v0.1 prototype</div>
          <div>© NERIS</div>
        </div>
      </div>

      {/* RIGHT — form */}
      <div className="flex flex-col">
        <div className="p-6 flex items-center justify-between">
          <Link
            to="/"
            data-testid="login-back-link"
            className="inline-flex items-center gap-1.5 text-[13px] text-neutral-500 hover:text-[var(--accent-primary)]"
          >
            <ArrowLeft size={14} /> Back to overview
          </Link>
          <div className="text-[11px] font-mono text-neutral-400">SECURE · TLS 1.3</div>
        </div>

        <div className="flex-1 flex items-center justify-center px-6 pb-10">
          <div className="w-full max-w-md">
            <div className="mb-8">
              <h1 className="text-3xl font-semibold tracking-tight">Sign in to NERIS</h1>
              <p className="mt-2 text-[14px] text-neutral-600">
                Access is scoped to your assigned role. Actions are logged.
              </p>
            </div>

            {/* Role tabs */}
            <div
              className="grid grid-cols-4 gap-1 p-1 bg-[var(--surface-sunken)] rounded-md mb-6"
              role="tablist"
              data-testid="login-role-tabs"
            >
              {ROLE_TABS.map((t) => {
                const active = t.key === activeRole;
                return (
                  <button
                    key={t.key}
                    role="tab"
                    aria-selected={active}
                    data-testid={`login-role-tab-${t.key}`}
                    onClick={() => setActiveRole(t.key)}
                    className={`flex flex-col items-center gap-1 py-2.5 rounded-[5px] text-[11px] font-medium transition-colors ${
                      active
                        ? "bg-white shadow-sm text-[var(--text-primary)]"
                        : "text-neutral-500 hover:text-[var(--text-primary)]"
                    }`}
                  >
                    <t.icon size={16} strokeWidth={1.75} style={{ color: active ? t.color : undefined }} />
                    {t.label}
                  </button>
                );
              })}
            </div>

            <div className="mb-6 p-3.5 border hairline rounded-md bg-white flex items-start gap-3">
              <div
                className="w-8 h-8 rounded-sm flex items-center justify-center flex-shrink-0"
                style={{ backgroundColor: `${activeTab.color}12`, color: activeTab.color }}
              >
                <activeTab.icon size={16} />
              </div>
              <div>
                <div className="text-[13px] font-medium text-[var(--text-primary)]">
                  Signing in as {activeTab.label}
                </div>
                <div className="text-[12px] text-neutral-500 mt-0.5">{activeTab.subtitle}</div>
              </div>
            </div>

            <form onSubmit={onSubmit} className="space-y-4" data-testid="login-form">
              <div>
                <label className="text-[12px] font-medium text-neutral-700 uppercase tracking-wider">Email</label>
                <input
                  type="email"
                  required
                  autoComplete="email"
                  data-testid="login-email-input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@department.gov.in"
                  className="mt-1.5 w-full h-11 px-3 border hairline rounded-md bg-white text-[14px] focus:border-[var(--accent-primary)] outline-none transition-colors"
                />
              </div>

              <div>
                <div className="flex items-center justify-between">
                  <label className="text-[12px] font-medium text-neutral-700 uppercase tracking-wider">Password</label>
                  <button
                    type="button"
                    onClick={() => setShowPass((s) => !s)}
                    className="text-[11px] text-neutral-500 hover:text-[var(--accent-primary)] flex items-center gap-1"
                    data-testid="login-toggle-password"
                  >
                    {showPass ? <EyeOff size={12} /> : <Eye size={12} />}
                    {showPass ? "Hide" : "Show"}
                  </button>
                </div>
                <input
                  type={showPass ? "text" : "password"}
                  required
                  autoComplete="current-password"
                  data-testid="login-password-input"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="mt-1.5 w-full h-11 px-3 border hairline rounded-md bg-white text-[14px] focus:border-[var(--accent-primary)] outline-none transition-colors"
                />
              </div>

              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 text-[13px] text-neutral-600 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={remember}
                    onChange={(e) => setRemember(e.target.checked)}
                    className="w-4 h-4 accent-[var(--accent-primary)]"
                    data-testid="login-remember-checkbox"
                  />
                  Remember this device
                </label>
                <a href="#" className="text-[13px] text-[var(--accent-primary)] hover:text-[var(--accent-primary-hover)]">
                  Forgot password?
                </a>
              </div>

              {error && (
                <div
                  data-testid="login-error"
                  className="p-3 border rounded-md bg-red-50 border-red-200 text-red-800 text-[13px]"
                >
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                data-testid="login-submit-button"
                className="w-full h-11 rounded-md bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] disabled:opacity-60 text-white text-[14px] font-medium flex items-center justify-center gap-2 transition-colors"
              >
                {loading ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}
                {loading ? "Signing in…" : "Sign in"}
              </button>
            </form>

            {/* Demo access */}
            <div className="mt-8 pt-6 border-t hairline">
              <div className="flex items-center justify-between mb-3">
                <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold">
                  Demo access · For evaluation only
                </div>
              </div>
              <button
                onClick={useDemo}
                data-testid="login-use-demo-button"
                className="w-full h-10 rounded-md border hairline bg-white hover:bg-[var(--surface-sunken)] text-[13px] font-medium text-[var(--text-primary)] transition-colors flex items-center justify-center gap-2"
              >
                <activeTab.icon size={14} style={{ color: activeTab.color }} />
                Fill demo credentials for {activeTab.label}
              </button>
              <div className="mt-2 text-[11px] text-neutral-500 font-mono text-center">
                {activeTab.demoEmail} · Demo@2026
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
