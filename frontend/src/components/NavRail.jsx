import { Link, useLocation } from "react-router-dom";
import { Building2, LayoutDashboard, Map as MapIcon, Truck, TriangleAlert, Package, Bell, Radar, Radio, User as UserIcon, ScrollText, Route as RouteIcon, Boxes, LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const NAV_GROUPS = {
  gov: [
    { to: "/command-center", icon: LayoutDashboard, label: "Command" },
    { to: "/map", icon: MapIcon, label: "GIS Map" },
    { to: "/vehicles", icon: Truck, label: "Fleet" },
    { to: "/incidents", icon: TriangleAlert, label: "Incidents" },
    { to: "/supply", icon: Boxes, label: "Supply" },
    { to: "/predictions", icon: Radar, label: "Predictions" },
    { to: "/alerts", icon: Bell, label: "Alerts" },
    { to: "/audit", icon: ScrollText, label: "Audit" },
  ],
  logistics: [
    { to: "/logistics", icon: Package, label: "Workspace" },
    { to: "/vehicles", icon: Truck, label: "Fleet" },
    { to: "/routes", icon: RouteIcon, label: "Routes" },
    { to: "/alerts", icon: Bell, label: "Alerts" },
  ],
  field: [{ to: "/field", icon: Radio, label: "Report" }],
  public: [{ to: "/public", icon: UserIcon, label: "Advisories" }],
};

function groupFor(role) {
  if (["SUPER_ADMIN", "GOVERNMENT_ADMIN", "GOVERNMENT_OFFICER", "DISTRICT_OFFICER"].includes(role)) return "gov";
  if (role === "LOGISTICS_OPERATOR") return "logistics";
  if (["FIELD_OFFICER", "DRIVER"].includes(role)) return "field";
  return "public";
}

export default function NavRail() {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  if (!user || typeof user !== "object") return null;
  const items = NAV_GROUPS[groupFor(user.role)] || [];

  return (
    <nav
      data-testid="nav-rail"
      className="w-16 flex-shrink-0 bg-white border-r hairline flex flex-col items-center py-3 gap-1"
      aria-label="Primary"
    >
      <Link
        to="/"
        className="w-9 h-9 rounded-sm bg-[var(--accent-primary)] flex items-center justify-center text-white mb-3"
        title="NERIS home"
        data-testid="nav-home"
      >
        <Building2 size={17} />
      </Link>

      {items.map((it) => {
        const active = pathname === it.to || pathname.startsWith(it.to + "/");
        return (
          <Link
            key={it.to}
            to={it.to}
            title={it.label}
            data-testid={`nav-${it.label.toLowerCase().replace(/\s+/g, "-")}`}
            className={`w-12 py-2 rounded-md flex flex-col items-center gap-0.5 text-[9.5px] font-medium tracking-wide transition-colors ${
              active
                ? "bg-[var(--accent-soft)] text-[var(--accent-primary)]"
                : "text-neutral-500 hover:text-[var(--text-primary)] hover:bg-[var(--surface-sunken)]"
            }`}
            aria-current={active ? "page" : undefined}
          >
            <it.icon size={17} strokeWidth={1.75} />
            {it.label}
          </Link>
        );
      })}

      <div className="flex-1" />

      <div
        className="w-8 h-8 rounded-full bg-[var(--accent-primary)] text-white flex items-center justify-center text-[11px] font-semibold"
        title={`${user.name} · ${user.role}`}
        data-testid="nav-user-avatar"
      >
        {(user.name || "U").slice(0, 1).toUpperCase()}
      </div>
      <button
        onClick={logout}
        title="Sign out"
        data-testid="nav-logout-button"
        className="mt-1 w-10 py-1.5 rounded-md text-neutral-500 hover:text-[var(--status-blocked)] hover:bg-red-50 flex items-center justify-center"
      >
        <LogOut size={15} />
      </button>
    </nav>
  );
}
