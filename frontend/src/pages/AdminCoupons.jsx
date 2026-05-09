import { useEffect, useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Plus, Trash, Ticket } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function AdminCoupons() {
  const [coupons, setCoupons] = useState([]);
  const [form, setForm] = useState({ code: "", percent_off: 20, max_uses: 100, extends_days: 30 });
  const [creating, setCreating] = useState(false);

  const load = () => api.get("/admin/coupons").then((r) => setCoupons(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      await api.post("/admin/coupons", { ...form, percent_off: Number(form.percent_off), max_uses: Number(form.max_uses), extends_days: Number(form.extends_days) });
      toast.success("Coupon created");
      setForm({ code: "", percent_off: 20, max_uses: 100, extends_days: 30 });
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Create failed");
    } finally {
      setCreating(false);
    }
  };

  const remove = async (id) => {
    try {
      await api.delete(`/admin/coupons/${id}`);
      toast.success("Coupon deleted");
      load();
    } catch { toast.error("Delete failed"); }
  };

  return (
    <DashboardLayout mode="admin">
      <div className="space-y-6 fade-up">
        <div>
          <span className="label-tech">/ admin / coupons</span>
          <h1 className="font-mono font-bold text-3xl mt-2">Coupons</h1>
        </div>

        <form onSubmit={create} className="card-tech p-6 grid md:grid-cols-5 gap-4" data-testid="create-coupon-form">
          <div>
            <Label className="label-tech">Code</Label>
            <Input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })} required className="rounded-none bg-[#0a0a0a] border-white/15 mt-2 h-10 font-mono uppercase" data-testid="coupon-code-input" />
          </div>
          <div>
            <Label className="label-tech">% Off</Label>
            <Input type="number" min="0" max="100" value={form.percent_off} onChange={(e) => setForm({ ...form, percent_off: e.target.value })} className="rounded-none bg-[#0a0a0a] border-white/15 mt-2 h-10 font-mono" data-testid="coupon-pct-input" />
          </div>
          <div>
            <Label className="label-tech">Max uses</Label>
            <Input type="number" min="1" value={form.max_uses} onChange={(e) => setForm({ ...form, max_uses: e.target.value })} className="rounded-none bg-[#0a0a0a] border-white/15 mt-2 h-10 font-mono" data-testid="coupon-maxuses-input" />
          </div>
          <div>
            <Label className="label-tech">Extends (days)</Label>
            <Input type="number" min="0" value={form.extends_days} onChange={(e) => setForm({ ...form, extends_days: e.target.value })} className="rounded-none bg-[#0a0a0a] border-white/15 mt-2 h-10 font-mono" data-testid="coupon-days-input" />
          </div>
          <div className="flex items-end">
            <Button type="submit" disabled={creating} className="btn-primary rounded-none h-10 w-full" data-testid="create-coupon-btn">
              <Plus size={14} className="mr-1" /> Create
            </Button>
          </div>
        </form>

        <div className="card-tech overflow-x-auto">
          <table className="w-full text-xs font-mono min-w-[600px]" data-testid="coupons-table">
            <thead className="text-left text-[#737373] border-b border-white/10">
              <tr>
                <th className="px-4 py-3">Code</th>
                <th className="px-4 py-3">% Off</th>
                <th className="px-4 py-3">Used / Max</th>
                <th className="px-4 py-3">Extends</th>
                <th className="px-4 py-3">Expires</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {coupons.map((c) => (
                <tr key={c.coupon_id} className="border-b border-white/5">
                  <td className="px-4 py-3 text-[#4da3ff] flex items-center gap-2"><Ticket size={12} />{c.code}</td>
                  <td className="px-4 py-3">{c.percent_off}%</td>
                  <td className="px-4 py-3 text-[#a0a6ad]">{c.used_count} / {c.max_uses}</td>
                  <td className="px-4 py-3">{c.extends_days}d</td>
                  <td className="px-4 py-3 text-[#737373]">{c.expires_at?.slice(0, 10) || "—"}</td>
                  <td className="px-4 py-3">
                    <Button size="sm" variant="ghost" onClick={() => remove(c.coupon_id)} className="text-[#ff4757] hover:bg-[#ff4757]/10 rounded-none h-8" data-testid={`delete-coupon-${c.coupon_id}`}>
                      <Trash size={12} />
                    </Button>
                  </td>
                </tr>
              ))}
              {coupons.length === 0 && (
                <tr><td colSpan="6" className="text-center py-8 text-[#737373]">No coupons yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </DashboardLayout>
  );
}
