import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../contexts/AuthContext";

export default function AuthCallback() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const hash = window.location.hash || "";
    const m = hash.match(/session_id=([^&]+)/);
    const session_id = m ? decodeURIComponent(m[1]) : null;

    (async () => {
      if (!session_id) {
        navigate("/login");
        return;
      }
      try {
        const { data } = await api.post("/auth/google/session", { session_id });
        setUser(data);
        // Clean up hash
        window.history.replaceState(null, "", window.location.pathname);
        navigate(data.role === "admin" ? "/admin" : "/dashboard", { replace: true, state: { user: data } });
      } catch {
        navigate("/login");
      }
    })();
  }, [navigate, setUser]);

  return (
    <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center" data-testid="auth-callback">
      <div className="font-mono text-sm text-[#a0a6ad]">
        <span className="cursor-blink">finalizing google session</span>
      </div>
    </div>
  );
}
