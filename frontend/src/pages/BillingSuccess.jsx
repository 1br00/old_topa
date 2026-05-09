import { useEffect, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { CheckCircle, Warning, ArrowRight } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function BillingSuccess() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const sessionId = params.get("session_id");
  const [status, setStatus] = useState("checking"); // checking | paid | pending | error

  useEffect(() => {
    if (!sessionId) { setStatus("error"); return; }
    let attempts = 0;
    const maxAttempts = 8;
    const poll = async () => {
      attempts += 1;
      try {
        const r = await api.get(`/stripe/checkout-status/${sessionId}`);
        const ps = r.data.payment_status;
        if (ps === "paid") {
          setStatus("paid");
          toast.success("Subscription activated");
          return;
        }
        if (r.data.status === "expired") {
          setStatus("error");
          return;
        }
        if (attempts >= maxAttempts) {
          setStatus("pending");
          return;
        }
        setTimeout(poll, 2000);
      } catch {
        if (attempts >= maxAttempts) setStatus("error");
        else setTimeout(poll, 2000);
      }
    };
    poll();
  }, [sessionId]);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-[#f0f2f5] flex items-center justify-center px-6">
      <div className="card-tech p-10 max-w-md w-full text-center fade-up" data-testid="billing-success">
        {status === "checking" && (
          <>
            <div className="font-mono text-sm text-[#a0a6ad] mb-2">processing payment</div>
            <div className="cursor-blink font-mono text-[#4da3ff]"></div>
          </>
        )}
        {status === "paid" && (
          <>
            <CheckCircle size={56} weight="duotone" className="text-[#00d4aa] mx-auto mb-4" />
            <h1 className="font-mono font-bold text-2xl mb-2">Payment confirmed</h1>
            <p className="text-sm text-[#a0a6ad] mb-6">Your subscription is now active. A receipt has been emailed to you.</p>
            <Button onClick={() => navigate("/dashboard")} className="btn-primary rounded-none h-11 w-full" data-testid="go-dashboard-btn">
              Open dashboard <ArrowRight size={14} className="ml-2" />
            </Button>
          </>
        )}
        {status === "pending" && (
          <>
            <Warning size={56} weight="duotone" className="text-[#ffab00] mx-auto mb-4" />
            <h1 className="font-mono font-bold text-2xl mb-2">Still processing</h1>
            <p className="text-sm text-[#a0a6ad] mb-6">Payment is taking longer than usual. Check your dashboard in a minute.</p>
            <Button onClick={() => navigate("/dashboard")} className="btn-primary rounded-none h-11 w-full" data-testid="go-dashboard-btn">
              Go to dashboard
            </Button>
          </>
        )}
        {status === "error" && (
          <>
            <Warning size={56} weight="duotone" className="text-[#ff4757] mx-auto mb-4" />
            <h1 className="font-mono font-bold text-2xl mb-2">Couldn't verify</h1>
            <p className="text-sm text-[#a0a6ad] mb-6">We couldn't verify the payment. If you were charged, contact support.</p>
            <Link to="/dashboard"><Button variant="outline" className="rounded-none h-11 w-full border-white/15 hover:bg-white/5 hover:text-white">Back to dashboard</Button></Link>
          </>
        )}
      </div>
    </div>
  );
}
