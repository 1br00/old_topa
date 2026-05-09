import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { AuthShell } from "./Login";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { GoogleLogo } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await register({ name, email, password });
      toast.success("Account created — 14-day Pro trial activated");
      navigate("/dashboard");
    } catch (err) {
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  const googleSignup = () => {
    const redirectUrl = window.location.origin + "/auth/callback";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <AuthShell title="Create account" subtitle="14 days Pro · no card required">
      <form onSubmit={submit} className="space-y-4" data-testid="register-form">
        <div>
          <Label className="label-tech">Full name</Label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="rounded-none bg-[#0a0a0a] border-white/15 mt-2 h-11 font-mono"
            data-testid="register-name-input"
          />
        </div>
        <div>
          <Label className="label-tech">Email</Label>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="rounded-none bg-[#0a0a0a] border-white/15 mt-2 h-11 font-mono"
            data-testid="register-email-input"
          />
        </div>
        <div>
          <Label className="label-tech">Password</Label>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
            className="rounded-none bg-[#0a0a0a] border-white/15 mt-2 h-11 font-mono"
            data-testid="register-password-input"
          />
          <p className="text-xs text-[#737373] mt-1.5 font-mono">min. 6 characters</p>
        </div>
        <Button type="submit" disabled={loading} className="w-full btn-primary rounded-none h-11" data-testid="register-submit-btn">
          {loading ? "Creating…" : "Create account"}
        </Button>
      </form>

      <div className="my-6 flex items-center gap-3 text-xs label-tech text-[#737373]">
        <div className="h-px flex-1 bg-white/10" /> OR <div className="h-px flex-1 bg-white/10" />
      </div>

      <Button
        onClick={googleSignup}
        variant="outline"
        className="w-full rounded-none h-11 border-white/15 bg-[#0a0a0a] hover:bg-white/5 hover:text-white"
        data-testid="google-register-btn"
      >
        <GoogleLogo size={18} weight="bold" className="mr-2" />
        Continue with Google
      </Button>

      <p className="text-sm text-[#a0a6ad] mt-6 text-center">
        Already have an account? <Link to="/login" className="text-[#4da3ff] hover:underline" data-testid="login-link">Sign in</Link>
      </p>
    </AuthShell>
  );
}
