import { Link } from "react-router-dom";
import { ArrowRight, Route, Radar, ShieldCheck, PackageSearch, Radio, Building2 } from "lucide-react";

const pillars = [
  { icon: Radar, title: "Predict", body: "Flood and landslide risk modeled per-corridor before disruption strikes." },
  { icon: Route, title: "Route", body: "Vehicle-specific, hazard-aware routing that adapts in real time." },
  { icon: PackageSearch, title: "Protect", body: "Village isolation and days-to-stockout forecasts for essential supplies." },
  { icon: Radio, title: "Monitor", body: "Live fleet telemetry, field reports, and government evidence, fused." },
  { icon: ShieldCheck, title: "Respond", body: "Government-verified actions with a full, immutable audit trail." },
];

const RegionMap = () => (
  <div className="relative w-full h-full overflow-hidden hairline border rounded-md map-backdrop">
    <div className="absolute inset-0 grid-backdrop opacity-60" />
    <svg viewBox="0 0 400 300" className="absolute inset-0 w-full h-full" preserveAspectRatio="xMidYMid slice">
      <g fill="none" strokeLinecap="round">
        <path d="M40 210 Q 120 160 190 175 T 360 130" stroke="#1B4B66" strokeWidth="2.2" />
        <path d="M80 90 Q 170 110 230 90 T 370 210" stroke="#1E8E3E" strokeWidth="1.8" />
        <path d="M60 260 Q 140 240 220 250 T 380 260" stroke="#C77C00" strokeWidth="1.6" strokeDasharray="4 3" />
        <path d="M110 40 Q 150 130 200 170 T 320 250" stroke="#C4281C" strokeWidth="1.6" />
      </g>
      {[
        { cx: 90, cy: 200, c: "#1E8E3E" },
        { cx: 180, cy: 175, c: "#C77C00" },
        { cx: 250, cy: 155, c: "#C4281C" },
        { cx: 320, cy: 140, c: "#1B4B66" },
        { cx: 140, cy: 250, c: "#1E8E3E" },
        { cx: 300, cy: 240, c: "#C77C00" },
      ].map((p, i) => (
        <g key={i}>
          <circle cx={p.cx} cy={p.cy} r="8" fill={p.c} opacity="0.15" />
          <circle cx={p.cx} cy={p.cy} r="3.5" fill={p.c} />
        </g>
      ))}
    </svg>
    <div className="absolute bottom-3 left-3 flex items-center gap-2 text-[11px] uppercase tracking-wider text-neutral-500 font-medium">
      <span className="status-dot" style={{ background: "#1E8E3E" }} />
      Live corridors monitored
    </div>
    <div className="absolute top-3 right-3 text-[10px] font-mono text-neutral-400">
      NER · 26.20°N 92.94°E
    </div>
  </div>
);

export default function Landing() {
  return (
    <div className="min-h-screen bg-[var(--surface-base)]">
      {/* Top bar */}
      <header className="border-b hairline bg-white" data-testid="landing-header">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-sm bg-[var(--accent-primary)] flex items-center justify-center text-white">
              <Building2 size={16} strokeWidth={2} />
            </div>
            <div className="leading-tight">
              <div className="text-[13px] font-semibold tracking-tight">NERIS</div>
              <div className="text-[10px] uppercase tracking-widest text-neutral-500">NER Intelligence System</div>
            </div>
          </div>
          <nav className="hidden md:flex items-center gap-7 text-[13px] text-neutral-600">
            <a href="#capabilities" className="hover:text-[var(--accent-primary)]">Capabilities</a>
            <a href="#roles" className="hover:text-[var(--accent-primary)]">For roles</a>
            <a href="#transparency" className="hover:text-[var(--accent-primary)]">Data sources</a>
          </nav>
          <Link
            to="/login"
            data-testid="landing-signin-link"
            className="text-[13px] font-medium text-[var(--accent-primary)] hover:text-[var(--accent-primary-hover)] flex items-center gap-1"
          >
            Sign in <ArrowRight size={14} />
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="relative">
        <div className="max-w-7xl mx-auto px-6 pt-16 pb-20 grid lg:grid-cols-12 gap-10 items-center">
          <div className="lg:col-span-6">
            <div className="inline-flex items-center gap-2 px-2.5 py-1 border hairline bg-white rounded-full text-[11px] uppercase tracking-wider text-neutral-600 mb-6">
              <span className="status-dot" style={{ background: "#1E8E3E" }} />
              SIH26002 · Prototype build
            </div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight leading-[1.05] text-[var(--text-primary)]">
              Predict disruption.<br />
              Protect connectivity.<br />
              <span className="text-[var(--accent-primary)]">Keep essential supplies moving.</span>
            </h1>
            <p className="mt-6 text-[15px] leading-relaxed text-neutral-600 max-w-xl">
              AI-assisted logistics and accessibility intelligence for the North Eastern Region.
              Government-grade command surface for road accessibility, isolation risk, and supply continuity.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                to="/login"
                data-testid="landing-cta-command-center"
                className="inline-flex items-center gap-2 h-11 px-5 rounded-md bg-[var(--accent-primary)] hover:bg-[var(--accent-primary-hover)] text-white text-[14px] font-medium transition-colors"
              >
                Open Command Center <ArrowRight size={16} />
              </Link>
              <Link
                to="/login?role=logistics"
                data-testid="landing-cta-logistics"
                className="inline-flex items-center gap-2 h-11 px-5 rounded-md border hairline bg-white hover:bg-[var(--surface-sunken)] text-[14px] font-medium text-[var(--text-primary)] transition-colors"
              >
                Logistics operator login
              </Link>
            </div>
            <div className="mt-10 grid grid-cols-3 gap-6 max-w-md">
              {[
                { k: "Corridors", v: "1,284" },
                { k: "Districts", v: "104" },
                { k: "Villages", v: "38,921" },
              ].map((s) => (
                <div key={s.k}>
                  <div className="text-2xl font-semibold tabular-nums">{s.v}</div>
                  <div className="text-[11px] uppercase tracking-widest text-neutral-500 mt-1">{s.k}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="lg:col-span-6 h-[420px]">
            <RegionMap />
          </div>
        </div>
      </section>

      {/* Pillars */}
      <section id="capabilities" className="border-t hairline bg-white">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <div className="max-w-2xl">
            <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold">What NERIS does</div>
            <h2 className="mt-2 text-2xl sm:text-3xl font-semibold tracking-tight">
              A single operational surface for a fragile geography.
            </h2>
          </div>
          <div className="mt-10 grid sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {pillars.map((p) => (
              <div key={p.title} className="p-5 border hairline rounded-md bg-white hover:border-[var(--accent-primary)] transition-colors">
                <div className="w-9 h-9 rounded-sm bg-[var(--accent-soft)] text-[var(--accent-primary)] flex items-center justify-center mb-4">
                  <p.icon size={18} strokeWidth={1.75} />
                </div>
                <div className="text-[15px] font-semibold text-[var(--text-primary)]">{p.title}</div>
                <div className="mt-1.5 text-[13px] leading-relaxed text-neutral-600">{p.body}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Roles */}
      <section id="roles" className="border-t hairline">
        <div className="max-w-7xl mx-auto px-6 py-16 grid lg:grid-cols-2 gap-8">
          {[
            {
              title: "For Government",
              sub: "State authorities · District officers · Disaster cells",
              body: "Command Center, road override, verified incidents, isolation forecasts, and an immutable action log.",
              cta: "Government sign in",
              to: "/login?role=government",
              testId: "role-card-government",
            },
            {
              title: "For Logistics Clients",
              sub: "Fleet operators · Freight companies · Supply networks",
              body: "Vehicle-specific routing, real-time reroute alerts, delivery risk, and ETA impact from active hazards.",
              cta: "Logistics sign in",
              to: "/login?role=logistics",
              testId: "role-card-logistics",
            },
          ].map((r) => (
            <div key={r.title} className="p-8 bg-white border hairline rounded-md" data-testid={r.testId}>
              <div className="text-[11px] uppercase tracking-widest text-neutral-500 font-semibold">{r.sub}</div>
              <div className="mt-2 text-2xl font-semibold tracking-tight">{r.title}</div>
              <p className="mt-3 text-[14px] leading-relaxed text-neutral-600">{r.body}</p>
              <Link
                to={r.to}
                className="mt-6 inline-flex items-center gap-1.5 text-[13px] font-medium text-[var(--accent-primary)] hover:text-[var(--accent-primary-hover)]"
              >
                {r.cta} <ArrowRight size={14} />
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* Transparency */}
      <section id="transparency" className="border-t hairline bg-white">
        <div className="max-w-7xl mx-auto px-6 py-10 flex flex-wrap items-center justify-between gap-4 text-[12px] text-neutral-500">
          <div>
            This prototype uses simulated and demo data clearly labeled throughout —
            every prediction carries a provenance chip: <span className="font-medium text-neutral-700">LIVE / HISTORICAL / SIMULATED / GOVERNMENT-VERIFIED</span>.
          </div>
          <div className="font-mono text-[11px]">© NERIS · SIH26002</div>
        </div>
      </section>
    </div>
  );
}
