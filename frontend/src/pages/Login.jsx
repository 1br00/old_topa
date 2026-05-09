import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { ShieldCheck, GoogleLogo } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const u = await login(email, password);
      toast.success("Welcome back");
      navigate(u.role === "admin" ? "/admin" : (location.state?.from?.pathname || "/dashboard"));
    } catch (err) {
      const detail = err?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  const googleLogin = () => {
    const redirectUrl = window.location.origin + "/auth/callback";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <AuthShell title="Sign in" subtitle="Access your xss0r dashboard">
      <form onSubmit={submit} className="space-y-5" data-testid="login-form">
        <div>
          <Label className="label-tech">Email</Label>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            required
            className="rounded-none bg-[#0a0a0a] border-white/15 mt-2 h-11 font-mono"
            data-testid="login-email-input"
          />
        </div>
        <div>
          <div className="flex justify-between items-center">
            <Label className="label-tech">Password</Label>
            <Link to="/forgot-password" className="text-xs text-[#4da3ff] hover:underline" data-testid="forgot-link">Forgot?</Link>
          </div>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="rounded-none bg-[#0a0a0a] border-white/15 mt-2 h-11 font-mono"
            data-testid="login-password-input"
          />
        </div>
        <Button
          type="submit"
          disabled={loading}
          className="w-full btn-primary rounded-none h-11"
          data-testid="login-submit-btn"
        >
          {loading ? "Authenticating…" : "Sign in"}
        </Button>
      </form>

      <div className="my-6 flex items-center gap-3 text-xs label-tech text-[#737373]">
        <div className="h-px flex-1 bg-white/10" />
        OR
        <div className="h-px flex-1 bg-white/10" />
      </div>

      <Button
        onClick={googleLogin}
        variant="outline"
        className="w-full rounded-none h-11 border-white/15 bg-[#0a0a0a] hover:bg-white/5 hover:text-white"
        data-testid="google-login-btn"
      >
        <GoogleLogo size={18} weight="bold" className="mr-2" />
        Continue with Google
      </Button>

      <p className="text-sm text-[#a0a6ad] mt-8 text-center">
        New here? <Link to="/register" className="text-[#4da3ff] hover:underline" data-testid="register-link">Create account</Link>
      </p>
    </AuthShell>
  );
}

export function AuthShell({ title, subtitle, children }) {
  return (
    <div className="min-h-screen bg-[#0a0a0a] flex">
      <div className="hidden lg:flex lg:w-1/2 bg-[#0a0a0a] border-r border-white/10 relative items-center justify-center p-16 overflow-hidden">
        <div className="absolute inset-0 bg-grid opacity-30" aria-hidden />
        <div className="relative z-10 max-w-md fade-up">
          <Link to="/" className="flex items-center gap-2 mb-12" data-testid="auth-logo">
            <ShieldCheck size={28} weight="duotone" className="text-[#4da3ff]" />
            <span className="font-mono font-bold text-xl">xss0r</span>
          </Link>
          <h2 className="font-mono font-bold text-3xl tracking-tight leading-tight mb-4">
            Precision scanner.<br />
            License-locked.<br />
            <span className="text-[#4da3ff]">Built for hunters.</span>
          </h2>
          <p className="text-[#a0a6ad] leading-relaxed mb-10">
            Manage your license, activations, downloads and scan history from a single dashboard.
          </p>
          <div className="space-y-3 font-mono text-xs text-[#a0a6ad]">
            <div className="flex justify-between border-b border-white/10 pb-2">
              <span className="text-[#737373]">Active scans this month</span>
              <span className="text-[#00d4aa]">12,847</span>
            </div>
            <div className="flex justify-between border-b border-white/10 pb-2">
              <span className="text-[#737373]">XSS findings reported</span>
              <span className="text-[#00d4aa]">3,219</span>
            </div>
            <div className="flex justify-between border-b border-white/10 pb-2">
              <span className="text-[#737373]">Avg. license uptime</span>
              <span className="text-[#00d4aa]">99.98%</span>
            </div>
          </div>
        </div>
      </div>
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-md fade-up">
          <div className="lg:hidden mb-8">
            <Link to="/" className="flex items-center gap-2" data-testid="auth-logo-mobile">
              <ShieldCheck size={24} weight="duotone" className="text-[#4da3ff]" />
              <span className="font-mono font-bold text-lg">xss0r</span>
            </Link>
          </div>
          <h1 className="font-mono font-bold text-3xl tracking-tight">{title}</h1>
          {subtitle && <p className="text-[#a0a6ad] mt-2 mb-8">{subtitle}</p>}
          {children}
        </div>
      </div>
    </div>
  );
}
