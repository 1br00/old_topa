import { useEffect, useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { CreditCard, ArrowsClockwise, Lightning, CheckCircle, Crown } from "@phosphor-icons/react";
import { toast } from "sonner";

// Simple PayPal logo (inline SVG)
const PayPalLogo = ({ size = 14 }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" aria-hidden>
    <path d="M7.076 21.337H2.47a.641.641 0 0 1-.633-.74L4.944 1.59A.641.641 0 0 1 5.578 1h7.45c2.57 0 4.578.543 5.69 1.81 1.01 1.15 1.302 2.42.997 4.298l-.018.111v.812l.633.359c.533.283.957.59 1.282.94.541.586.89 1.328 1.04 2.205.156.91.105 1.99-.146 3.21-.288 1.408-.756 2.633-1.391 3.643-.582.93-1.327 1.704-2.211 2.298-.844.566-1.84.992-2.961 1.265-1.097.27-2.34.405-3.689.405h-.86c-.621 0-1.155.451-1.252 1.066l-.043.275-.711 4.508-.033.165c-.024.108-.057.139-.107.16a.435.435 0 0 1-.157.025z"/>
  </svg>
);

export default function BillingPage() {
  const [plans, setPlans] = useState([]);
  const [lic, setLic] = useState(null);
  const [loading, setLoading] = useState(null); // "stripe-pro" | "paypal-pro" etc.

  useEffect(() => {
    api.get("/plans").then((r) => setPlans(r.data)).catch(() => {});
    api.get("/license/me").then((r) => setLic(r.data)).catch(() => {});
  }, []);

  const subscribeStripe = async (plan) => {
    setLoading(`stripe-${plan}`);
    try {
      const r = await api.post("/stripe/checkout", {
        plan,
        origin_url: window.location.origin,
      });
      window.location.href = r.data.checkout_url;
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Stripe checkout failed");
      setLoading(null);
    }
  };

  const subscribePayPal = async (plan) => {
    setLoading(`paypal-${plan}`);
    try {
      const r = await api.post("/paypal/subscribe", {
        plan,
        origin_url: window.location.origin,
      });
      if (!r.data.approval_url) {
        toast.error("PayPal returned no approval URL");
        setLoading(null);
        return;
      }
      // Append subscription_id to return URL by storing in session
      sessionStorage.setItem("paypal_subscription_id", r.data.subscription_id);
      window.location.href = r.data.approval_url + `&subscription_id=${r.data.subscription_id}`;
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "PayPal subscribe failed");
      setLoading(null);
    }
  };

  const openStripePortal = async () => {
    try {
      const r = await api.post("/stripe/portal", { origin_url: window.location.origin });
      window.location.href = r.data.url;
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not open billing portal");
    }
  };

  const cancelPayPal = async () => {
    if (!confirm("Cancel your PayPal subscription? You'll keep access until the period ends.")) return;
    try {
      await api.post("/paypal/cancel", { reason: "User cancelled from dashboard" });
      toast.success("PayPal subscription cancelled");
      const r = await api.get("/license/me");
      setLic(r.data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Cancel failed");
    }
  };

  const currentPlan = lic?.license?.plan;
  const provider = lic?.license?.payment_provider; // "paypal" | undefined (Stripe)
  const isSubscribed = currentPlan === "pro" || currentPlan === "enterprise";

  return (
    <DashboardLayout mode="user">
      <div className="max-w-5xl space-y-6 fade-up">
        <div>
          <span className="label-tech">/ billing</span>
          <h1 className="font-mono font-bold text-3xl mt-2">Plans & billing</h1>
          <p className="text-[#a0a6ad] text-sm mt-1">Pay with credit card (Stripe) or PayPal. Recurring monthly. Cancel anytime.</p>
        </div>

        {/* Current */}
        <div className="card-tech p-6">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <span className="label-tech">current</span>
              <div className="flex items-center gap-2 mt-1">
                <Crown size={20} weight="duotone" className="text-[#4da3ff]" />
                <h2 className="font-mono text-2xl font-bold">{(currentPlan || "—").toUpperCase()}</h2>
                <span className={`text-xs font-mono ${lic?.license?.status === "active" ? "text-[#00d4aa]" : "text-[#ffab00]"}`}>
                  · {lic?.license?.status}
                </span>
                {provider && (
                  <span className="text-xs font-mono text-[#737373] ml-2">via {provider}</span>
                )}
              </div>
              <p className="text-xs font-mono text-[#737373] mt-1">
                {lic?.license?.expires_at ? `Renews/Expires: ${lic.license.expires_at.slice(0, 10)}` : "No expiry"}
              </p>
            </div>
            {isSubscribed && (
              <div className="flex gap-2">
                {provider === "paypal" ? (
                  <Button onClick={cancelPayPal} variant="outline" className="rounded-none h-10 border-[#ff4757]/40 text-[#ff4757] hover:bg-[#ff4757]/10 hover:text-[#ff4757]" data-testid="cancel-paypal-btn">
                    Cancel PayPal subscription
                  </Button>
                ) : (
                  <Button onClick={openStripePortal} variant="outline" className="rounded-none h-10 border-white/15 hover:bg-white/5 hover:text-white" data-testid="manage-billing-btn">
                    <CreditCard size={14} className="mr-2" /> Manage billing
                  </Button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Plan cards */}
        <div className="grid md:grid-cols-3 gap-4">
          {plans.map((p) => {
            const isCurrent = currentPlan === p.id;
            const free = p.id === "free";
            return (
              <div
                key={p.id}
                className={`card-tech p-6 relative ${p.id === "pro" ? "border-[#4da3ff]/40" : ""}`}
                data-testid={`billing-plan-${p.id}`}
              >
                {p.id === "pro" && (
                  <span className="absolute top-0 right-0 bg-[#4da3ff] text-[#0a0a0a] text-xs font-mono px-2 py-1 font-bold">POPULAR</span>
                )}
                <h3 className="font-mono font-bold text-xl">{p.name}</h3>
                <div className="my-4">
                  <span className="text-3xl font-mono font-bold">${p.price}</span>
                  <span className="text-[#a0a6ad] text-xs ml-2">/ {p.period}</span>
                </div>
                <ul className="space-y-2 mb-6 text-xs text-[#a0a6ad]">
                  {p.features.map((f, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <CheckCircle size={14} weight="fill" className="text-[#00d4aa] mt-0.5 flex-shrink-0" />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
                {isCurrent ? (
                  <Button disabled className="w-full rounded-none h-10 bg-white/5 text-[#737373] cursor-not-allowed">
                    Current plan
                  </Button>
                ) : free ? (
                  <Button disabled className="w-full rounded-none h-10 bg-white/5 text-[#737373]">
                    {currentPlan === "free" ? "Current plan" : "—"}
                  </Button>
                ) : (
                  <div className="space-y-2">
                    <Button
                      onClick={() => subscribeStripe(p.id)}
                      disabled={loading !== null}
                      className={`w-full rounded-none h-10 ${p.id === "pro" ? "btn-primary" : "bg-white/5 hover:bg-white/10 text-white border border-white/15"}`}
                      data-testid={`subscribe-${p.id}-stripe-btn`}
                    >
                      {loading === `stripe-${p.id}` ? <ArrowsClockwise size={14} className="mr-1.5 animate-spin" /> : <CreditCard size={14} className="mr-1.5" />}
                      {loading === `stripe-${p.id}` ? "Redirecting…" : "Pay with card"}
                    </Button>
                    <Button
                      onClick={() => subscribePayPal(p.id)}
                      disabled={loading !== null}
                      className="w-full rounded-none h-10 bg-[#0070ba] hover:bg-[#005a96] text-white"
                      data-testid={`subscribe-${p.id}-paypal-btn`}
                    >
                      {loading === `paypal-${p.id}` ? <ArrowsClockwise size={14} className="mr-1.5 animate-spin" /> : <PayPalLogo size={14} />}
                      <span className="ml-1.5">{loading === `paypal-${p.id}` ? "Redirecting…" : "Pay with PayPal"}</span>
                    </Button>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="text-xs font-mono text-[#737373] border-t border-white/10 pt-4 space-y-1">
          <p>🔒 Card payments processed by Stripe — cards never touch our servers.</p>
          <p>🅿️ PayPal recurring billing managed via PayPal Subscriptions API.</p>
        </div>
      </div>
    </DashboardLayout>
  );
}
