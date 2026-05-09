import { useEffect, useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { api } from "../lib/api";
import { Bug } from "@phosphor-icons/react";

export default function ScansPage() {
  const [scans, setScans] = useState([]);
  useEffect(() => { api.get("/scans").then((r) => setScans(r.data)).catch(() => {}); }, []);

  return (
    <DashboardLayout mode="user">
      <div className="max-w-6xl space-y-6 fade-up">
        <div>
          <span className="label-tech">/ scan history</span>
          <h1 className="font-mono font-bold text-3xl mt-2">Scan history</h1>
        </div>
        <div className="card-tech overflow-hidden">
          {scans.length === 0 ? (
            <div className="p-12 text-center">
              <p className="text-[#737373] font-mono">No scans recorded yet. Start a scan from the CLI.</p>
            </div>
          ) : (
            <table className="w-full text-xs font-mono" data-testid="scans-table">
              <thead className="border-b border-white/10 text-[#737373] text-left">
                <tr>
                  <th className="px-4 py-3">Scan ID</th>
                  <th className="px-4 py-3">Target</th>
                  <th className="px-4 py-3">Vulns</th>
                  <th className="px-4 py-3">Duration</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Started</th>
                </tr>
              </thead>
              <tbody>
                {scans.map((s) => (
                  <tr key={s.scan_id} className="border-b border-white/5 hover:bg-white/[0.02]">
                    <td className="px-4 py-3 text-[#737373]">{s.scan_id}</td>
                    <td className="px-4 py-3 truncate max-w-xs">{s.target}</td>
                    <td className="px-4 py-3">
                      <span className={`flex items-center gap-1 ${s.vulns_found > 0 ? "text-[#ff4757]" : "text-[#00d4aa]"}`}>
                        <Bug size={12} /> {s.vulns_found}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[#a0a6ad]">{s.duration_seconds}s</td>
                    <td className="px-4 py-3 text-[#00d4aa]">{s.status}</td>
                    <td className="px-4 py-3 text-[#737373]">{s.created_at?.slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
