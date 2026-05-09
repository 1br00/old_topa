import { useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Ticket } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function CouponsPage() {
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const r = await api.post("/coupons/redeem", { code });
      setResult(r.data);
      toast.success(`License extended by ${r.data.extended_days} days`);
      setCode("");
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Redemption failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <DashboardLayout mode="user">
      <div className="max-w-2xl space-y-6 fade-up">
        <div>
          <span className="label-tech">/ coupons</span>
          <h1 className="font-mono font-bold text-3xl mt-2">Redeem coupon</h1>
          <p className="text-[#a0a6ad] text-sm mt-1">Apply a coupon code to extend your license.</p>
        </div>
        <div className="card-tech p-6">
          <form onSubmit={submit} className="space-y-4" data-testid="redeem-form">
            <div>
              <Label className="label-tech">Coupon code</Label>
              <Input
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                placeholder="LAUNCH50"
                className="rounded-none bg-[#0a0a0a] border-white/15 mt-2 h-11 font-mono uppercase tracking-wider"
                data-testid="coupon-input"
              />
              <p className="text-xs text-[#737373] mt-1.5 font-mono">Try LAUNCH50 or XSS0R10 for demo</p>
            </div>
            <Button type="submit" disabled={loading || !code} className="btn-primary rounded-none h-11 px-6" data-testid="redeem-btn">
              <Ticket size={16} className="mr-2" />
              {loading ? "Redeeming…" : "Redeem"}
            </Button>
          </form>
          {result && (
            <div className="mt-6 p-4 border border-[#00d4aa]/30 bg-[#00d4aa]/5 font-mono text-xs" data-testid="redeem-result">
              <p className="text-[#00d4aa]">[✓] Coupon applied — extended {result.extended_days} days.</p>
              <p className="text-[#a0a6ad] mt-1">New expiry: {result.new_expiry?.slice(0, 10)}</p>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
