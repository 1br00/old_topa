import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Button } from "./ui/button";
import {
  House, Gauge, Download, Key, Ticket, Users, Package,
  ChartLine, SignOut, ShieldCheck, CreditCard, Receipt, ChartBar
} from "@phosphor-icons/react";

const userLinks = [
  { to: "/dashboard", label: "Overview", icon: Gauge, testid: "nav-overview" },
  { to: "/dashboard/license", label: "License & API", icon: Key, testid: "nav-license" },
  { to: "/dashboard/downloads", label: "Downloads", icon: Download, testid: "nav-downloads" },
  { to: "/dashboard/scans", label: "Scan History", icon: ChartLine, testid: "nav-scans" },
  { to: "/dashboard/billing", label: "Billing", icon: CreditCard, testid: "nav-billing" },
  { to: "/dashboard/coupons", label: "Redeem Coupon", icon: Ticket, testid: "nav-coupons" },
];

const adminLinks = [
  { to: "/admin", label: "Stats", icon: ChartLine, testid: "nav-admin-stats" },
  { to: "/admin/users", label: "Users", icon: Users, testid: "nav-admin-users" },
  { to: "/admin/coupons", label: "Coupons", icon: Ticket, testid: "nav-admin-coupons" },
  { to: "/admin/builds", label: "Builds", icon: Package, testid: "nav-admin-builds" },
  { to: "/admin/payments", label: "Payments", icon: Receipt, testid: "nav-admin-payments" },
  { to: "/admin/sales", label: "Sales", icon: ChartBar, testid: "nav-admin-sales" },
];

export default function DashboardLayout({ children, mode = "user" }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const links = mode === "admin" ? adminLinks : userLinks;

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex bg-[#0a0a0a] text-[#f0f2f5]">
      {/* Sidebar */}
      <aside className="hidden lg:flex w-64 flex-col border-r border-white/10 bg-[#0a0a0a] sticky top-0 h-screen">
        <Link to="/" className="px-6 py-6 border-b border-white/10 flex items-center gap-2" data-testid="sidebar-logo">
          <ShieldCheck size={22} weight="duotone" className="text-[#4da3ff]" />
          <span className="font-mono font-bold text-lg tracking-tight">xss0r</span>
          <span className="label-tech ml-auto">{mode === "admin" ? "ADMIN" : "USER"}</span>
        </Link>
        <nav className="flex-1 p-3 space-y-1">
          {links.map((l) => {
            const Icon = l.icon;
            const active = location.pathname === l.to;
            return (
              <Link
                key={l.to}
                to={l.to}
                data-testid={l.testid}
                className={`flex items-center gap-3 px-3 py-2 text-sm transition-colors ${
                  active ? "bg-white/10 text-white border-l-2 border-[#4da3ff]" : "text-[#a0a6ad] hover:bg-white/5 hover:text-white"
                }`}
              >
                <Icon size={18} weight={active ? "fill" : "regular"} />
                <span>{l.label}</span>
              </Link>
            );
          })}
          {mode === "user" && user?.role === "admin" && (
            <Link to="/admin" className="flex items-center gap-3 px-3 py-2 mt-4 text-sm text-[#4da3ff] hover:bg-white/5" data-testid="nav-switch-admin">
              <ShieldCheck size={18} weight="duotone" />
              <span>Switch to Admin</span>
            </Link>
          )}
          {mode === "admin" && (
            <Link to="/dashboard" className="flex items-center gap-3 px-3 py-2 mt-4 text-sm text-[#4da3ff] hover:bg-white/5" data-testid="nav-switch-user">
              <House size={18} />
              <span>Back to Dashboard</span>
            </Link>
          )}
        </nav>
        <div className="p-3 border-t border-white/10">
          <div className="px-3 py-2">
            <p className="text-xs text-[#737373] truncate" data-testid="sidebar-email">{user?.email}</p>
            <p className="text-xs text-[#a0a6ad] font-mono mt-1">{user?.role}</p>
          </div>
          <Button
            onClick={handleLogout}
            variant="ghost"
            className="w-full justify-start text-sm rounded-none hover:bg-white/5 text-[#a0a6ad] hover:text-white"
            data-testid="logout-btn"
          >
            <SignOut size={16} className="mr-2" />
            Sign out
          </Button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="lg:hidden glass fixed top-0 left-0 right-0 z-40 px-4 py-3 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2" data-testid="mobile-logo">
          <ShieldCheck size={20} weight="duotone" className="text-[#4da3ff]" />
          <span className="font-mono font-bold">xss0r</span>
        </Link>
        <Button onClick={handleLogout} size="sm" variant="ghost" className="rounded-none" data-testid="mobile-logout-btn">
          <SignOut size={16} />
        </Button>
      </div>

      <main className="flex-1 lg:p-8 pt-20 lg:pt-8 px-4 pb-12 max-w-full overflow-x-hidden">
        {children}
      </main>
    </div>
  );
}
