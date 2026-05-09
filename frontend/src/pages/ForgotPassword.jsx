import { useState } from "react";
import { Link } from "react-router-dom";
import { AuthShell } from "./Login";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/auth/forgot-password", { email });
      setSent(true);
      toast.success("Check your inbox (or backend logs in dev)");
    } catch {
      toast.error("Could not request reset");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell title="Reset password" subtitle="We'll send you a reset link">
      {sent ? (
        <div className="card-tech p-6 text-center" data-testid="forgot-success">
          <p className="text-sm text-[#a0a6ad] leading-relaxed">
            If an account exists for <span className="font-mono text-white">{email}</span>, a reset link has been sent.
          </p>
          <Link to="/login" className="text-[#4da3ff] text-sm hover:underline mt-4 inline-block" data-testid="back-to-login">
            ← Back to login
          </Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4" data-testid="forgot-form">
          <div>
            <Label className="label-tech">Email</Label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="rounded-none bg-[#0a0a0a] border-white/15 mt-2 h-11 font-mono"
              data-testid="forgot-email-input"
            />
          </div>
          <Button type="submit" disabled={loading} className="w-full btn-primary rounded-none h-11" data-testid="forgot-submit-btn">
            {loading ? "Sending…" : "Send reset link"}
          </Button>
          <Link to="/login" className="block text-center text-sm text-[#a0a6ad] hover:text-white">← Back to login</Link>
        </form>
      )}
    </AuthShell>
  );
}
