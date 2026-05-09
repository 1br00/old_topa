import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import DashboardLayout from "../components/DashboardLayout";
import { api } from "../lib/api";
import { useAuth } from "../contexts/AuthContext";
import { Button } from "../components/ui/button";
import { ShieldCheck, Key, Download, Bug, Calendar, ArrowRight, Cpu } from "@phosphor-icons/react";

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "2-digit" });
  } catch {
    return iso;
  }
}
function daysLeft(iso) {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  return Math.max(0, Math.ceil(ms / 86400000));
}

export default function Dashboard() {
  const { user } = useAuth();
  const [lic, setLic] = useState(null);
  const [scans, setScans] = useState([]);
  const [builds, setBuilds] = useState([]);

  useEffect(() => {
    api.get("/license/me").then((r) => setLic(r.data)).catch(() => {});
    api.get("/scans").then((r) => setScans(r.data)).catch(() => {});
    api.get("/builds").then((r) => setBuilds(r.data)).catch(() => {});
  }, []);

  const remaining = daysLeft(lic?.license?.expires_at);

  return (
    <DashboardLayout mode="user">
      <div className="max-w-6xl space-y-8 fade-up">
        <div className="flex items-end justify-between flex-wrap gap-4">
          <div>
            <span className="label-tech">/ overview</span>
            <h1 className="font-mono font-bold text-3xl mt-2">Welcome back, {user?.name?.split(" ")[0] || "operator"}.</h1>
          </div>
          <div className="text-xs font-mono text-[#737373]">
            <span className="kbd mr-2">{user?.email}</span>
            <span className="kbd">{lic?.license?.plan?.toUpperCase() || "—"}</span>
          </div>
        </div>

        {/* License card */}
        <div className="card-tech p-6 lg:p-8" data-testid="license-card">
          <div className="grid lg:grid-cols-4 gap-6">
            <div className="lg:col-span-2">
              <div className="flex items-center gap-2 mb-3">
                <ShieldCheck size={20} weight="duotone" className="text-[#4da3ff]" />
                <span className="label-tech">active license</span>
              </div>
              <h2 className="font-mono text-3xl font-bold tracking-tight">
                {lic?.license?.plan?.toUpperCase() || "—"}
              </h2>
              <p className="text-[#a0a6ad] text-sm mt-1">
                Status: <span className={lic?.license?.status === "active" ? "text-[#00d4aa]" : "text-[#ffab00]"}>{lic?.license?.status || "—"}</span>
              </p>
            </div>
            <Stat label="Expires" value={fmtDate(lic?.license?.expires_at)} accent={remaining !== null && remaining < 7 ? "#ffab00" : undefined} />
            <Stat label="Days remaining" value={remaining ?? "∞"} />
          </div>
          <div className="grid sm:grid-cols-3 gap-4 mt-8 pt-6 border-t border-white/10">
            <Link to="/dashboard/billing" data-testid="quick-billing">
              <Button variant="outline" className="rounded-none h-11 w-full border-white/15 hover:bg-white/5 hover:text-white justify-start">
                <ShieldCheck size={16} className="mr-2" /> Upgrade plan
              </Button>
            </Link>
            <Link to="/dashboard/license" data-testid="quick-license">
              <Button variant="outline" className="rounded-none h-11 w-full border-white/15 hover:bg-white/5 hover:text-white justify-start">
                <Key size={16} className="mr-2" /> API key & HWID
              </Button>
            </Link>
            <Link to="/dashboard/downloads" data-testid="quick-downloads">
              <Button variant="outline" className="rounded-none h-11 w-full border-white/15 hover:bg-white/5 hover:text-white justify-start">
                <Download size={16} className="mr-2" /> Downloads
              </Button>
            </Link>
          </div>
        </div>

        {/* Activations + Recent scans */}
        <div className="grid lg:grid-cols-2 gap-6">
          <div className="card-tech p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <span className="label-tech">/ device activations</span>
                <h3 className="font-mono font-semibold mt-1">HWID activations</h3>
              </div>
              <span className="text-xs font-mono text-[#737373]">
                {lic?.activations?.length || 0} / {lic?.license?.max_activations || "—"}
              </span>
            </div>
            {(lic?.activations || []).length === 0 ? (
              <p className="text-sm text-[#737373] py-6 text-center font-mono">No devices activated yet.</p>
            ) : (
              <ul className="space-y-2 text-xs font-mono" data-testid="activations-list">
                {lic.activations.map((a) => (
                  <li key={a.activation_id} className="flex items-center justify-between border-b border-white/10 pb-2">
                    <div className="flex items-center gap-2">
                      <Cpu size={14} className="text-[#4da3ff]" />
                      <span>{a.os || "Unknown OS"}</span>
                    </div>
                    <span className="text-[#737373]">{a.hwid?.slice(0, 14)}…</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="card-tech p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <span className="label-tech">/ recent</span>
                <h3 className="font-mono font-semibold mt-1">Scan history</h3>
              </div>
              <Link to="/dashboard/scans" className="text-xs text-[#4da3ff] hover:underline" data-testid="view-all-scans">
                View all <ArrowRight size={12} className="inline" />
              </Link>
            </div>
            {scans.length === 0 ? (
              <p className="text-sm text-[#737373] py-6 text-center font-mono">No scans yet.</p>
            ) : (
              <ul className="space-y-2 text-xs font-mono" data-testid="recent-scans">
                {scans.slice(0, 4).map((s) => (
                  <li key={s.scan_id} className="flex items-center justify-between border-b border-white/10 pb-2 gap-3">
                    <div className="flex items-center gap-2 truncate">
                      <Bug size={14} className={s.vulns_found > 0 ? "text-[#ff4757]" : "text-[#737373]"} />
                      <span className="truncate">{s.target}</span>
                    </div>
                    <span className="text-[#a0a6ad] flex-shrink-0">{s.vulns_found} vulns</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Latest builds */}
        <div className="card-tech p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <span className="label-tech">/ latest releases</span>
              <h3 className="font-mono font-semibold mt-1">Available builds</h3>
            </div>
            <Link to="/dashboard/downloads" className="text-xs text-[#4da3ff] hover:underline" data-testid="view-all-builds">
              All builds <ArrowRight size={12} className="inline" />
            </Link>
          </div>
          <div className="grid sm:grid-cols-2 gap-3">
            {builds.slice(0, 2).map((b) => (
              <div key={b.build_id} className="border border-white/10 p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-xs label-tech">{b.platform}</span>
                  <span className="font-mono text-xs text-[#4da3ff]">v{b.version}</span>
                </div>
                <p className="text-xs text-[#737373] line-clamp-2 mb-3 whitespace-pre-line">{b.changelog}</p>
                <Link to="/dashboard/downloads">
                  <Button size="sm" variant="outline" className="rounded-none border-white/15 hover:bg-white/5 hover:text-white text-xs h-8">
                    <Download size={12} className="mr-1.5" /> Get build
                  </Button>
                </Link>
              </div>
            ))}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

function Stat({ label, value, accent }) {
  return (
    <div>
      <div className="label-tech">{label}</div>
      <div className="font-mono text-2xl mt-1" style={{ color: accent || "#f0f2f5" }}>{value}</div>
    </div>
  );
}
