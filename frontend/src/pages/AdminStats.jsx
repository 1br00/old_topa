import { useEffect, useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { api } from "../lib/api";
import { Users, ShieldCheck, Bug, Ticket, Package, Download, Prohibit } from "@phosphor-icons/react";

export default function AdminStats() {
  const [s, setS] = useState({});
  useEffect(() => { api.get("/admin/stats").then((r) => setS(r.data)).catch(() => {}); }, []);

  const cards = [
    { icon: Users, label: "Total users", value: s.total_users ?? "—", color: "#4da3ff" },
    { icon: ShieldCheck, label: "Active licenses", value: s.active_licenses ?? "—", color: "#00d4aa" },
    { icon: Prohibit, label: "Banned users", value: s.banned_users ?? "—", color: "#ff4757" },
    { icon: Bug, label: "Total scans", value: s.total_scans ?? "—", color: "#ffab00" },
    { icon: Ticket, label: "Coupons", value: s.total_coupons ?? "—", color: "#4da3ff" },
    { icon: Package, label: "Builds", value: s.total_builds ?? "—", color: "#a0a6ad" },
    { icon: Download, label: "Total downloads", value: s.total_downloads ?? 0, color: "#00d4aa" },
  ];

  return (
    <DashboardLayout mode="admin">
      <div className="max-w-6xl space-y-6 fade-up">
        <div>
          <span className="label-tech">/ admin</span>
          <h1 className="font-mono font-bold text-3xl mt-2">Operations dashboard</h1>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-px bg-white/10" data-testid="admin-stats-grid">
          {cards.map((c, i) => (
            <div key={i} className="bg-[#0a0a0a] p-6 hover:bg-[#121212] transition-colors">
              <c.icon size={20} weight="duotone" style={{ color: c.color }} className="mb-3" />
              <div className="label-tech">{c.label}</div>
              <div className="font-mono text-3xl font-bold mt-1">{c.value}</div>
            </div>
          ))}
        </div>
      </div>
    </DashboardLayout>
  );
}
