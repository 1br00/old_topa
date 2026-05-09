import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { CheckCircle, Warning, EnvelopeSimple } from "@phosphor-icons/react";
import { Button } from "../components/ui/button";

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState("checking"); // checking | ok | error

  useEffect(() => {
    if (!token) { setState("error"); return; }
    api.post("/auth/verify-email", { token })
      .then(() => setState("ok"))
      .catch(() => setState("error"));
  }, [token]);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-[#f0f2f5] flex items-center justify-center px-6">
      <div className="card-tech p-10 max-w-md w-full text-center fade-up" data-testid="verify-email-page">
        {state === "checking" && (
          <>
            <EnvelopeSimple size={48} weight="duotone" className="text-[#4da3ff] mx-auto mb-4" />
            <p className="font-mono text-sm text-[#a0a6ad]"><span className="cursor-blink">verifying email</span></p>
          </>
        )}
        {state === "ok" && (
          <>
            <CheckCircle size={56} weight="duotone" className="text-[#00d4aa] mx-auto mb-4" />
            <h1 className="font-mono font-bold text-2xl mb-2">Email verified</h1>
            <p className="text-sm text-[#a0a6ad] mb-6">Your account is fully activated.</p>
            <Link to="/dashboard"><Button className="btn-primary rounded-none h-11 w-full" data-testid="continue-btn">Continue to dashboard</Button></Link>
          </>
        )}
        {state === "error" && (
          <>
            <Warning size={56} weight="duotone" className="text-[#ff4757] mx-auto mb-4" />
            <h1 className="font-mono font-bold text-2xl mb-2">Invalid or expired link</h1>
            <p className="text-sm text-[#a0a6ad] mb-6">This verification link is no longer valid. Request a new one from your dashboard.</p>
            <Link to="/dashboard"><Button variant="outline" className="rounded-none h-11 w-full border-white/15 hover:bg-white/5 hover:text-white">Go to dashboard</Button></Link>
          </>
        )}
      </div>
    </div>
  );
}
