import { useEffect, useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import PlanCard from "../components/PlanCard";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { CreditCard, ArrowsClockwise, Crown, Ticket, X } from "@phosphor-icons/react";
import { toast } from "sonner";

const PayPalLogo = ({ size = 14 }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" aria-hidden>
    <path d="M7.076 21.337H2.47a.641.641 0 0 1-.633-.74L4.944 1.59A.641.641 0 0 1 5.578 1h7.45c2.57 0 4.578.543 5.69 1.81 1.01 1.15 1.302 2.42.997 4.298l-.018.111v.812l.633.359c.533.283.957.59 1.282.94.541.586.89 1.328 1.04 2.205.156.91.105 1.99-.146 3.21-.288 1.408-.756 2.633-1.391 3.643-.582.93-1.327 1.704-2.211 2.298-.844.566-1.84.992-2.961 1.265-1.097.27-2.34.405-3.689.405h-.86c-.621 0-1.155.451-1.252 1.066l-.043.275-.711 4.508-.033.165c-.024.108-.057.139-.107.16a.435.435 0 0 1-.157.025z"/>
  </svg>
);

export default function BillingPage() {
  const [plans, setPlans] = useState([]);
  const [lic, setLic] = useState(null);
  const [loading, setLoading] = useState(null);
  const [couponCode, setCouponCode] = useState("");
  const [couponPreview, setCouponPreview] = useState(null);

  useEffect(() => {
    api.get("/plans").then((r) => setPlans(r.data)).catch(() => {});
    api.get("/license/me").then((r) => setLic(r.data)).catch(() => {});
  }, []);

  const checkCoupon = async () => {
    if (!couponCode.trim()) { setCouponPreview(null); return; }
    try {
      const r = await api.post("/coupons/validate", { code: couponCode.trim() });
      setCouponPreview(r.data);
      toast.success(`${r.data.percent_off}% discount applied`);
    } catch (err) {
      setCouponPreview(null);
      toast.error(err?.response?.data?.detail || "Invalid coupon");
    }
  };

  const subscribeStripe = async (plan) => {
    setLoading(`stripe-${plan}`);
    try {
      const r = await api.post("/stripe/checkout", {
        plan,
        origin_url: window.location.origin,
        coupon_code: couponPreview ? couponCode.trim() : null,
      });
      window.location.href = r.data.checkout_url;
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Stripe checkout failed");
      setLoading(null);
    }
  };
  const subscribePayPal = async (plan) => {
    setLoading(`paypal-${plan}`);
    try {
      const r = await api.post("/paypal/subscribe", {
        plan,
        origin_url: window.location.origin,
        coupon_code: couponPreview ? couponCode.trim() : null,
      });
      if (!r.data.approval_url) {
        toast.error("PayPal returned no approval URL");
        setLoading(null); return;
      }
      window.location.href = r.data.approval_url + `&subscription_id=${r.data.subscription_id}`;
    } catch (err) {
      toast.error(err?.response?.data?.detail || "PayPal subscribe failed");
      setLoading(null);
    }
  };
  const openStripePortal = async () => {
    try {
      const r = await api.post("/stripe/portal", { origin_url: window.location.origin });
      window.location.href = r.data.url;
    } catch (err) { toast.error(err?.response?.data?.detail || "Could not open billing portal"); }
  };
  const cancelPayPal = async () => {
    if (!window.confirm("Cancel your PayPal subscription? You'll keep access until the period ends.")) return;
    try {
      await api.post("/paypal/cancel", { reason: "User cancelled from dashboard" });
      toast.success("PayPal subscription cancelled");
      const r = await api.get("/license/me"); setLic(r.data);
    } catch (err) { toast.error(err?.response?.data?.detail || "Cancel failed"); }
  };

  const currentPlan = lic?.license?.plan;
  const provider = lic?.license?.payment_provider;
  const isSubscribed = currentPlan && currentPlan !== "free";

  // 2 cards top row, 2 middle, 1 centered bottom (like the screenshot)
  const top = plans.slice(0, 2);   // basic, pro
  const mid = plans.slice(2, 4);   // diamond, golden
  const last = plans.slice(4, 5);  // business

  return (
    <DashboardLayout mode="user">
      <div className="max-w-6xl space-y-8 fade-up">
        <div>
          <span className="label-tech">/ billing</span>
          <h1 className="font-mono font-bold text-3xl mt-2">Plans & billing</h1>
          <p className="text-[#a0a6ad] text-sm mt-1">Pay with credit card (Stripe) or PayPal. Cancel anytime — you keep access until the period ends.</p>
        </div>

        {/* Current */}
        <div className="card-tech p-6">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <span className="label-tech">current</span>
              <div className="flex items-center gap-2 mt-1">
                <Crown size={20} weight="duotone" className="text-[#4da3ff]" />
                <h2 className="font-mono text-2xl font-bold uppercase">{currentPlan || "—"}</h2>
                <span className={`text-xs font-mono ${lic?.license?.status === "active" ? "text-[#00d4aa]" : "text-[#ffab00]"}`}>· {lic?.license?.status}</span>
                {provider && <span className="text-xs font-mono text-[#737373] ml-2">via {provider}</span>}
              </div>
              <p className="text-xs font-mono text-[#737373] mt-1">{lic?.license?.expires_at ? `Renews/Expires: ${lic.license.expires_at.slice(0, 10)}` : "No expiry"}</p>
            </div>
            {isSubscribed && (
              provider === "paypal" ? (
                <Button onClick={cancelPayPal} variant="outline" className="rounded-none h-10 border-[#ff4757]/40 text-[#ff4757] hover:bg-[#ff4757]/10 hover:text-[#ff4757]" data-testid="cancel-paypal-btn">Cancel PayPal subscription</Button>
              ) : (
                <Button onClick={openStripePortal} variant="outline" className="rounded-none h-10 border-white/15 hover:bg-white/5 hover:text-white" data-testid="manage-billing-btn">
                  <CreditCard size={14} className="mr-2" /> Manage billing
                </Button>
              )
            )}
          </div>
        </div>

        {/* Coupon */}
        <div className="card-tech p-5">
          <div className="flex items-center gap-3 flex-wrap">
            <Ticket size={18} weight="duotone" className="text-[#ffab00]" />
            <span className="label-tech">Have a coupon?</span>
            <div className="flex gap-2 flex-1 min-w-[260px] max-w-md">
              <Input
                value={couponCode}
                onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                placeholder="LAUNCH50"
                className="rounded-none bg-[#0a0a0a] border-white/15 h-10 font-mono uppercase tracking-wider"
                data-testid="billing-coupon-input"
              />
              <Button onClick={checkCoupon} className="rounded-none h-10 bg-white/5 hover:bg-white/10 border border-white/15 text-white" data-testid="billing-coupon-apply-btn">Apply</Button>
              {couponPreview && (
                <Button onClick={() => { setCouponCode(""); setCouponPreview(null); }} variant="ghost" className="rounded-none h-10 hover:bg-white/5" data-testid="billing-coupon-clear-btn"><X size={14} /></Button>
              )}
            </div>
            {couponPreview && (
              <span className="text-xs font-mono text-[#00d4aa]">
                ✓ {couponPreview.percent_off}% off — applied to all plans below
              </span>
            )}
          </div>
        </div>

        {/* Plans */}
        <PlanGrid plans={top} {...{currentPlan, loading, subscribeStripe, subscribePayPal, couponPreview}} />
        <PlanGrid plans={mid} {...{currentPlan, loading, subscribeStripe, subscribePayPal, couponPreview}} />
        {last.length > 0 && (
          <div className="grid md:grid-cols-3 gap-6">
            <div className="hidden md:block" />
            <PlanGrid plans={last} {...{currentPlan, loading, subscribeStripe, subscribePayPal, couponPreview}} singleCol />
            <div className="hidden md:block" />
          </div>
        )}

        <div className="text-xs font-mono text-[#737373] border-t border-white/10 pt-4 space-y-1">
          <p>🔒 Card payments processed by Stripe — cards never touch our servers.</p>
          <p>🅿️ PayPal recurring billing managed via PayPal Subscriptions API.</p>
        </div>
      </div>
    </DashboardLayout>
  );
}

function PlanGrid({ plans, currentPlan, loading, subscribeStripe, subscribePayPal, singleCol }) {
  return (
    <div className={`grid gap-6 ${singleCol ? "" : "md:grid-cols-2"}`}>
      {plans.map((p) => {
        const isCurrent = currentPlan === p.id;
        const ctaLabel = isCurrent ? "Current plan" : `Select ${p.name}`;
        const secondaryAction = !isCurrent ? (
          <button
            onClick={() => subscribePayPal(p.id)}
            disabled={loading !== null}
            data-testid={`pay-paypal-${p.id}`}
            className="w-full py-2.5 mt-2 text-xs font-mono font-bold uppercase tracking-wider bg-[#0070ba] hover:bg-[#005a96] text-white transition-colors flex items-center justify-center gap-2"
          >
            {loading === `paypal-${p.id}` ? <ArrowsClockwise size={12} className="animate-spin" /> : <PayPalLogo size={12} />}
            {loading === `paypal-${p.id}` ? "Redirecting…" : "or pay with PayPal"}
          </button>
        ) : null;
        return (
          <PlanCard
            key={p.id}
            plan={p}
            current={isCurrent}
            ctaLabel={loading === `stripe-${p.id}` ? "Redirecting…" : `Select ${p.name}`}
            onClick={() => subscribeStripe(p.id)}
            secondaryAction={secondaryAction}
          />
        );
      })}
    </div>
  );
}
