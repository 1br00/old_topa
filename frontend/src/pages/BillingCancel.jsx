import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { XCircle } from "@phosphor-icons/react";

export default function BillingCancel() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-[#f0f2f5] flex items-center justify-center px-6">
      <div className="card-tech p-10 max-w-md w-full text-center fade-up" data-testid="billing-cancel">
        <XCircle size={56} weight="duotone" className="text-[#737373] mx-auto mb-4" />
        <h1 className="font-mono font-bold text-2xl mb-2">Checkout canceled</h1>
        <p className="text-sm text-[#a0a6ad] mb-6">No charges were made. You can subscribe anytime.</p>
        <Link to="/dashboard">
          <Button className="btn-primary rounded-none h-11 w-full" data-testid="back-dashboard-btn">Back to dashboard</Button>
        </Link>
      </div>
    </div>
  );
}
