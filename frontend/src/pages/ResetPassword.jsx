import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AuthShell } from "./Login";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { toast } from "sonner";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/auth/reset-password", { token, password });
      toast.success("Password updated — please sign in");
      navigate("/login");
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Reset failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell title="Set new password" subtitle="Enter a new password for your account">
      <form onSubmit={submit} className="space-y-4" data-testid="reset-form">
        <div>
          <Label className="label-tech">New password</Label>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
            className="rounded-none bg-[#0a0a0a] border-white/15 mt-2 h-11 font-mono"
            data-testid="reset-password-input"
          />
        </div>
        <Button type="submit" disabled={loading || !token} className="w-full btn-primary rounded-none h-11" data-testid="reset-submit-btn">
          {loading ? "Updating…" : "Update password"}
        </Button>
        {!token && <p className="text-xs text-[#ff4757] font-mono">Missing token in URL.</p>}
        <Link to="/login" className="block text-center text-sm text-[#a0a6ad] hover:text-white">← Back to login</Link>
      </form>
    </AuthShell>
  );
}
