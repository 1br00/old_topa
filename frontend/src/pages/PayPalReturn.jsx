import { useEffect, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { CheckCircle, Warning, ArrowRight } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function PayPalReturn() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const subscriptionId = params.get("subscription_id");
  const [status, setStatus] = useState("checking"); // checking | active | pending | error

  useEffect(() => {
    if (!subscriptionId) { setStatus("error"); return; }
    let attempts = 0;
    const max = 8;
    const poll = async () => {
      attempts += 1;
      try {
        const r = await api.get(`/paypal/subscription-status/${subscriptionId}`);
        const s = (r.data.status || "").toUpperCase();
        if (s === "ACTIVE") {
          setStatus("active");
          toast.success("PayPal subscription active");
          return;
        }
        if (s === "CANCELLED" || s === "EXPIRED") {
          setStatus("error");
          return;
        }
        if (attempts >= max) {
          setStatus("pending");
          return;
        }
        setTimeout(poll, 2500);
      } catch (err) {
        const code = err?.response?.status;
        // Non-retryable errors — fail fast
        if (code === 400 || code === 404 || code === 503) {
          setStatus("error");
          return;
        }
        if (attempts >= max) setStatus("error");
        else setTimeout(poll, 2500);
      }
    };
    poll();
  }, [subscriptionId]);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-[#f0f2f5] flex items-center justify-center px-6">
      <div className="card-tech p-10 max-w-md w-full text-center fade-up" data-testid="paypal-return">
        {status === "checking" && (
          <>
            <div className="font-mono text-sm text-[#a0a6ad] mb-2">verifying paypal subscription</div>
            <div className="cursor-blink font-mono text-[#4da3ff]"></div>
          </>
        )}
        {status === "active" && (
          <>
            <CheckCircle size={56} weight="duotone" className="text-[#00d4aa] mx-auto mb-4" />
            <h1 className="font-mono font-bold text-2xl mb-2">Subscription active</h1>
            <p className="text-sm text-[#a0a6ad] mb-6">Your PayPal subscription is live. Receipt sent via PayPal.</p>
            <Button onClick={() => navigate("/dashboard")} className="btn-primary rounded-none h-11 w-full" data-testid="go-dashboard-btn">
              Open dashboard <ArrowRight size={14} className="ml-2" />
            </Button>
          </>
        )}
        {status === "pending" && (
          <>
            <Warning size={56} weight="duotone" className="text-[#ffab00] mx-auto mb-4" />
            <h1 className="font-mono font-bold text-2xl mb-2">Almost there</h1>
            <p className="text-sm text-[#a0a6ad] mb-6">PayPal is finalizing your subscription. It will activate within a minute.</p>
            <Button onClick={() => navigate("/dashboard")} className="btn-primary rounded-none h-11 w-full">Go to dashboard</Button>
          </>
        )}
        {status === "error" && (
          <>
            <Warning size={56} weight="duotone" className="text-[#ff4757] mx-auto mb-4" />
            <h1 className="font-mono font-bold text-2xl mb-2">Couldn't verify</h1>
            <p className="text-sm text-[#a0a6ad] mb-6">PayPal subscription couldn't be verified. Contact support if you were charged.</p>
            <Link to="/dashboard"><Button variant="outline" className="rounded-none h-11 w-full border-white/15 hover:bg-white/5 hover:text-white">Back to dashboard</Button></Link>
          </>
        )}
      </div>
    </div>
  );
}
