import { useEffect, useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Copy, ArrowsClockwise, Trash, Cpu, Key, ShieldCheck } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function LicensePage() {
  const [data, setData] = useState(null);

  const load = () => api.get("/license/me").then((r) => setData(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const copy = (txt) => {
    navigator.clipboard.writeText(txt);
    toast.success("Copied to clipboard");
  };

  const regen = async () => {
    try {
      await api.post("/license/regenerate-api-key");
      toast.success("API key rotated");
      load();
    } catch { toast.error("Failed to rotate key"); }
  };
  const reset = async () => {
    try {
      const r = await api.post("/license/reset-hwid");
      toast.success(`Removed ${r.data.removed} activations`);
      load();
    } catch { toast.error("Reset failed"); }
  };

  return (
    <DashboardLayout mode="user">
      <div className="max-w-4xl space-y-6 fade-up">
        <div>
          <span className="label-tech">/ license & api</span>
          <h1 className="font-mono font-bold text-3xl mt-2">License & access</h1>
        </div>

        <div className="card-tech p-6">
          <div className="flex items-start gap-4">
            <ShieldCheck size={28} weight="duotone" className="text-[#4da3ff] mt-1" />
            <div className="flex-1">
              <h3 className="font-mono font-semibold">License</h3>
              <p className="text-sm text-[#a0a6ad] mt-1">Plan: {data?.license?.plan?.toUpperCase() || "—"} · Status: {data?.license?.status}</p>
              <p className="text-xs font-mono text-[#737373] mt-1">Expires: {data?.license?.expires_at?.slice(0, 10) || "∞"}</p>
            </div>
          </div>
        </div>

        <div className="card-tech p-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Key size={18} weight="duotone" className="text-[#4da3ff]" />
              <h3 className="font-mono font-semibold">API key</h3>
            </div>
            <Button onClick={regen} size="sm" variant="outline" className="rounded-none border-white/15 hover:bg-white/5 hover:text-white" data-testid="regenerate-api-key-btn">
              <ArrowsClockwise size={14} className="mr-1.5" /> Rotate
            </Button>
          </div>
          <div className="flex items-center gap-2 bg-[#0a0a0a] border border-white/10 p-3">
            <code className="text-xs font-mono text-[#00d4aa] flex-1 break-all" data-testid="api-key-display">{data?.api_key || "—"}</code>
            <Button size="sm" variant="ghost" onClick={() => copy(data?.api_key || "")} data-testid="copy-api-key-btn" className="rounded-none hover:bg-white/5">
              <Copy size={14} />
            </Button>
          </div>
          <p className="text-xs text-[#737373] mt-2 font-mono">Use as Bearer token or X-API-Key header in xss0r CLI.</p>
        </div>

        <div className="card-tech p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Cpu size={18} weight="duotone" className="text-[#4da3ff]" />
              <h3 className="font-mono font-semibold">Device activations (HWID)</h3>
            </div>
            <Button onClick={reset} size="sm" variant="outline" className="rounded-none border-[#ff4757]/40 text-[#ff4757] hover:bg-[#ff4757]/10 hover:text-[#ff4757]" data-testid="reset-hwid-btn">
              <Trash size={14} className="mr-1.5" /> Reset all
            </Button>
          </div>
          {(data?.activations || []).length === 0 ? (
            <p className="text-sm text-[#737373] py-6 text-center font-mono">No active devices.</p>
          ) : (
            <table className="w-full text-xs font-mono" data-testid="activations-table">
              <thead className="text-left text-[#737373] border-b border-white/10">
                <tr>
                  <th className="py-2">HWID</th>
                  <th className="py-2">OS</th>
                  <th className="py-2">IP</th>
                  <th className="py-2">Activated</th>
                </tr>
              </thead>
              <tbody>
                {data.activations.map((a) => (
                  <tr key={a.activation_id} className="border-b border-white/5">
                    <td className="py-3 text-[#00d4aa]">{a.hwid}</td>
                    <td className="py-3">{a.os}</td>
                    <td className="py-3 text-[#a0a6ad]">{a.ip}</td>
                    <td className="py-3 text-[#737373]">{a.activated_at?.slice(0, 10)}</td>
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
