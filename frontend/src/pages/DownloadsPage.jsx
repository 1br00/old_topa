import { useEffect, useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { api, API } from "../lib/api";
import { Button } from "../components/ui/button";
import { Download, Package, Warning } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function DownloadsPage() {
  const [builds, setBuilds] = useState([]);

  useEffect(() => {
    api.get("/builds").then((r) => setBuilds(r.data)).catch(() => {});
  }, []);

  const download = async (b) => {
    if (!b.storage_path) {
      toast.error("Build file not yet uploaded by admin.");
      return;
    }
    try {
      const r = await api.get(`/builds/${b.build_id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = b.filename || `xss0r-${b.version}-${b.platform}.bin`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Download started");
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Download failed");
    }
  };

  const grouped = {
    windows: builds.filter((b) => b.platform === "windows"),
    linux: builds.filter((b) => b.platform === "linux"),
    macos: builds.filter((b) => b.platform === "macos"),
  };

  return (
    <DashboardLayout mode="user">
      <div className="max-w-5xl space-y-8 fade-up">
        <div>
          <span className="label-tech">/ downloads</span>
          <h1 className="font-mono font-bold text-3xl mt-2">Downloads</h1>
          <p className="text-[#a0a6ad] text-sm mt-1">Latest signed builds. Active license required.</p>
        </div>

        {Object.entries(grouped).map(([plat, items]) => (
          items.length === 0 ? null : (
            <section key={plat}>
              <div className="flex items-center gap-2 mb-3">
                <Package size={18} weight="duotone" className="text-[#4da3ff]" />
                <h2 className="font-mono font-semibold uppercase tracking-wider">{plat}</h2>
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                {items.map((b) => (
                  <div key={b.build_id} className="card-tech p-5" data-testid={`build-card-${b.build_id}`}>
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <p className="font-mono font-semibold text-lg">v{b.version}</p>
                        <p className="text-xs text-[#737373] font-mono mt-0.5">{b.filename}</p>
                      </div>
                      <span className={`label-tech ${b.storage_path ? "text-[#00d4aa]" : "text-[#ffab00]"}`}>
                        {b.storage_path ? "READY" : "PENDING"}
                      </span>
                    </div>
                    <pre className="text-xs text-[#a0a6ad] whitespace-pre-wrap font-mono mb-4 bg-[#0a0a0a] p-3 border border-white/5 max-h-32 overflow-auto">{b.changelog || "—"}</pre>
                    <Button
                      onClick={() => download(b)}
                      disabled={!b.storage_path}
                      className="w-full rounded-none btn-primary h-10"
                      data-testid={`download-${b.platform}-${b.version}-btn`}
                    >
                      {b.storage_path ? <><Download size={14} className="mr-2" /> Download</> : <><Warning size={14} className="mr-2" /> Awaiting upload</>}
                    </Button>
                  </div>
                ))}
              </div>
            </section>
          )
        ))}

        {builds.length === 0 && (
          <div className="card-tech p-12 text-center">
            <p className="text-[#737373] font-mono">No builds available yet.</p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
