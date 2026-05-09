import { useEffect, useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { CreditCard, ArrowsClockwise, Lightning, CheckCircle, Crown } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function BillingPage() {
  const [plans, setPlans] = useState([]);
  const [lic, setLic] = useState(null);
  const [loading, setLoading] = useState(null);

  useEffect(() => {
    api.get("/plans").then((r) => setPlans(r.data)).catch(() => {});
    api.get("/license/me").then((r) => setLic(r.data)).catch(() => {});
  }, []);

  const subscribe = async (plan) => {
    setLoading(plan);
    try {
      const r = await api.post("/stripe/checkout", {
        plan,
        origin_url: window.location.origin,
      });
      window.location.href = r.data.checkout_url;
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Checkout failed");
      setLoading(null);
    }
  };

  const openPortal = async () => {
    try {
      const r = await api.post("/stripe/portal", { origin_url: window.location.origin });
      window.location.href = r.data.url;
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not open billing portal");
    }
  };

  const currentPlan = lic?.license?.plan;
  const isSubscribed = currentPlan === "pro" || currentPlan === "enterprise";

  return (
    <DashboardLayout mode="user">
      <div className="max-w-5xl space-y-6 fade-up">
        <div>
          <span className="label-tech">/ billing</span>
          <h1 className="font-mono font-bold text-3xl mt-2">Plans & billing</h1>
          <p className="text-[#a0a6ad] text-sm mt-1">Manage your subscription. Cancel anytime — you keep access until the period ends.</p>
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
              </div>
              <p className="text-xs font-mono text-[#737373] mt-1">
                {lic?.license?.expires_at ? `Renews/Expires: ${lic.license.expires_at.slice(0, 10)}` : "No expiry"}
              </p>
            </div>
            {isSubscribed && (
              <Button onClick={openPortal} variant="outline" className="rounded-none h-10 border-white/15 hover:bg-white/5 hover:text-white" data-testid="manage-billing-btn">
                <CreditCard size={14} className="mr-2" /> Manage billing
              </Button>
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
                  <Button
                    onClick={() => subscribe(p.id)}
                    disabled={loading === p.id}
                    className={`w-full rounded-none h-10 ${p.id === "pro" ? "btn-primary" : "bg-white/5 hover:bg-white/10 text-white border border-white/15"}`}
                    data-testid={`subscribe-${p.id}-btn`}
                  >
                    {loading === p.id ? <ArrowsClockwise size={14} className="mr-1.5 animate-spin" /> : <Lightning size={14} className="mr-1.5" weight="duotone" />}
                    {loading === p.id ? "Redirecting…" : (isSubscribed ? `Switch to ${p.name}` : `Subscribe`)}
                  </Button>
                )}
              </div>
            );
          })}
        </div>

        <div className="text-xs font-mono text-[#737373] border-t border-white/10 pt-4">
          🔒 Payments processed securely by Stripe. Cards are never stored on our servers.
        </div>
      </div>
    </DashboardLayout>
  );
}
