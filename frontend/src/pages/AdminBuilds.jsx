import { useEffect, useRef, useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Trash, Upload, Package } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function AdminBuilds() {
  const [builds, setBuilds] = useState([]);
  const [version, setVersion] = useState("");
  const [platform, setPlatform] = useState("windows");
  const [changelog, setChangelog] = useState("");
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const load = () => api.get("/admin/builds").then((r) => setBuilds(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const upload = async (e) => {
    e.preventDefault();
    if (!file) { toast.error("Select a file"); return; }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("version", version);
      fd.append("platform", platform);
      fd.append("changelog", changelog);
      await api.post("/admin/builds", fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Build uploaded");
      setVersion(""); setChangelog(""); setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const remove = async (id) => {
    try {
      await api.delete(`/admin/builds/${id}`);
      toast.success("Build removed");
      load();
    } catch { toast.error("Delete failed"); }
  };

  return (
    <DashboardLayout mode="admin">
      <div className="space-y-6 fade-up">
        <div>
          <span className="label-tech">/ admin / builds</span>
          <h1 className="font-mono font-bold text-3xl mt-2">Builds & releases</h1>
        </div>

        <form onSubmit={upload} className="card-tech p-6 space-y-4" data-testid="upload-build-form">
          <div className="grid md:grid-cols-3 gap-4">
            <div>
              <Label className="label-tech">Version</Label>
              <Input value={version} onChange={(e) => setVersion(e.target.value)} required placeholder="1.4.3" className="rounded-none bg-[#0a0a0a] border-white/15 mt-2 h-10 font-mono" data-testid="build-version-input" />
            </div>
            <div>
              <Label className="label-tech">Platform</Label>
              <Select value={platform} onValueChange={setPlatform}>
                <SelectTrigger className="rounded-none bg-[#0a0a0a] border-white/15 mt-2 h-10 font-mono" data-testid="build-platform-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="rounded-none bg-[#121212] border-white/15 font-mono">
                  <SelectItem value="windows">Windows</SelectItem>
                  <SelectItem value="linux">Linux</SelectItem>
                  <SelectItem value="macos">macOS</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="label-tech">File</Label>
              <Input ref={fileRef} type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} required className="rounded-none bg-[#0a0a0a] border-white/15 mt-2 h-10 font-mono text-xs file:bg-white/10 file:text-white file:border-0 file:mr-3 file:px-3 file:py-2" data-testid="build-file-input" />
            </div>
          </div>
          <div>
            <Label className="label-tech">Changelog</Label>
            <Textarea value={changelog} onChange={(e) => setChangelog(e.target.value)} rows={4} placeholder="- Improved DOM XSS detection&#10;- New header payloads" className="rounded-none bg-[#0a0a0a] border-white/15 mt-2 font-mono text-xs" data-testid="build-changelog-input" />
          </div>
          <Button type="submit" disabled={uploading} className="btn-primary rounded-none h-10 px-6" data-testid="upload-build-btn">
            <Upload size={14} className="mr-2" /> {uploading ? "Uploading…" : "Upload build"}
          </Button>
        </form>

        <div className="card-tech overflow-x-auto">
          <table className="w-full text-xs font-mono min-w-[700px]" data-testid="builds-table">
            <thead className="text-left text-[#737373] border-b border-white/10">
              <tr>
                <th className="px-4 py-3">Version</th>
                <th className="px-4 py-3">Platform</th>
                <th className="px-4 py-3">Filename</th>
                <th className="px-4 py-3">Size</th>
                <th className="px-4 py-3">Downloads</th>
                <th className="px-4 py-3">Uploaded</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {builds.map((b) => (
                <tr key={b.build_id} className="border-b border-white/5">
                  <td className="px-4 py-3 text-[#4da3ff] flex items-center gap-2"><Package size={12} weight="duotone" />v{b.version}</td>
                  <td className="px-4 py-3 uppercase">{b.platform}</td>
                  <td className="px-4 py-3 text-[#a0a6ad] truncate max-w-xs">{b.filename}</td>
                  <td className="px-4 py-3 text-[#737373]">{(b.size / 1024 / 1024).toFixed(2)} MB</td>
                  <td className="px-4 py-3 text-[#00d4aa]">{b.download_count || 0}</td>
                  <td className="px-4 py-3 text-[#737373]">{b.created_at?.slice(0, 10)}</td>
                  <td className="px-4 py-3">
                    <Button size="sm" variant="ghost" onClick={() => remove(b.build_id)} className="text-[#ff4757] hover:bg-[#ff4757]/10 rounded-none h-8" data-testid={`delete-build-${b.build_id}`}>
                      <Trash size={12} />
                    </Button>
                  </td>
                </tr>
              ))}
              {builds.length === 0 && <tr><td colSpan="7" className="text-center py-8 text-[#737373]">No builds yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </DashboardLayout>
  );
}
