import { useEffect, useState, useRef } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { ArrowsClockwise, CheckCircle, XCircle, Clock, CreditCard } from "@phosphor-icons/react";

const PayPalLogo = ({ size = 12 }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill="currentColor" aria-hidden>
    <path d="M7.076 21.337H2.47a.641.641 0 0 1-.633-.74L4.944 1.59A.641.641 0 0 1 5.578 1h7.45c2.57 0 4.578.543 5.69 1.81 1.01 1.15 1.302 2.42.997 4.298l-.018.111v.812l.633.359c.533.283.957.59 1.282.94.541.586.89 1.328 1.04 2.205.156.91.105 1.99-.146 3.21-.288 1.408-.756 2.633-1.391 3.643-.582.93-1.327 1.704-2.211 2.298-.844.566-1.84.992-2.961 1.265-1.097.27-2.34.405-3.689.405h-.86c-.621 0-1.155.451-1.252 1.066l-.043.275-.711 4.508-.033.165c-.024.108-.057.139-.107.16a.435.435 0 0 1-.157.025z"/>
  </svg>
);

function StatusBadge({ status }) {
  const ok = status === "paid" || status === "active";
  const failed = status === "failed" || status === "denied";
  if (ok) return <span className="text-[#00d4aa] flex items-center gap-1"><CheckCircle size={12} weight="fill" /> {status}</span>;
  if (failed) return <span className="text-[#ff4757] flex items-center gap-1"><XCircle size={12} weight="fill" /> {status}</span>;
  return <span className="text-[#ffab00] flex items-center gap-1"><Clock size={12} /> {status || "pending"}</span>;
}

function timeAgo(iso) {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return "just now";
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}h ago`;
  return `${Math.floor(diff / 86400_000)}d ago`;
}

export default function AdminPayments() {
  const [txns, setTxns] = useState([]);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const ref = useRef();

  const load = async () => {
    try {
      const r = await api.get("/admin/payments/recent?limit=20");
      setTxns(r.data);
      setLastUpdated(new Date());
    } catch {}
  };

  useEffect(() => {
    load();
    if (!autoRefresh) return;
    ref.current = setInterval(load, 5000);
    return () => clearInterval(ref.current);
  }, [autoRefresh]);

  return (
    <DashboardLayout mode="admin">
      <div className="space-y-6 fade-up">
        <div className="flex items-end justify-between flex-wrap gap-4">
          <div>
            <span className="label-tech">/ admin / payments</span>
            <h1 className="font-mono font-bold text-3xl mt-2">Recent payments</h1>
            <p className="text-[#a0a6ad] text-xs font-mono mt-1">
              Last 20 transactions · {autoRefresh ? "auto-refreshing every 5s" : "paused"} · updated {timeAgo(lastUpdated?.toISOString())}
            </p>
          </div>
          <div className="flex gap-2">
            <Button onClick={load} variant="outline" className="rounded-none border-white/15 hover:bg-white/5 hover:text-white h-10" data-testid="refresh-btn">
              <ArrowsClockwise size={14} className="mr-2" /> Refresh
            </Button>
            <Button onClick={() => setAutoRefresh((v) => !v)} className={`rounded-none h-10 ${autoRefresh ? "btn-primary" : "bg-white/5 hover:bg-white/10 border border-white/15"}`} data-testid="autorefresh-toggle">
              {autoRefresh ? "● Auto-refresh ON" : "○ Auto-refresh OFF"}
            </Button>
          </div>
        </div>

        <div className="card-tech overflow-x-auto">
          <table className="w-full text-xs font-mono min-w-[900px]" data-testid="payments-table">
            <thead className="text-left text-[#737373] border-b border-white/10">
              <tr>
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Plan</th>
                <th className="px-4 py-3">Amount</th>
                <th className="px-4 py-3">Provider</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Detail</th>
              </tr>
            </thead>
            <tbody>
              {txns.length === 0 && <tr><td colSpan="7" className="text-center py-12 text-[#737373]">No transactions yet.</td></tr>}
              {txns.map((t, i) => (
                <tr key={t.session_id || t.subscription_id || i} className="border-b border-white/5 hover:bg-white/[0.02]">
                  <td className="px-4 py-3 text-[#737373]">{timeAgo(t.created_at)}</td>
                  <td className="px-4 py-3">
                    <div className="text-white">{t.user_name || "—"}</div>
                    <div className="text-[#737373] text-[10px]">{t.email}</div>
                  </td>
                  <td className="px-4 py-3 uppercase text-[#4da3ff]">{t.plan || "—"}</td>
                  <td className="px-4 py-3">
                    <span className="text-[#00d4aa]">${((t.amount_cents || 0) / 100).toFixed(2)}</span>
                    {t.coupon_code && <div className="text-[10px] text-[#ffab00]">{t.coupon_code}</div>}
                  </td>
                  <td className="px-4 py-3">
                    <span className="flex items-center gap-1.5 text-[#a0a6ad]">
                      {t.provider === "paypal" ? <PayPalLogo size={11} /> : <CreditCard size={11} />}
                      {t.provider || "stripe"}
                    </span>
                  </td>
                  <td className="px-4 py-3"><StatusBadge status={t.payment_status} /></td>
                  <td className="px-4 py-3 text-[#737373] truncate max-w-[180px]">
                    {t.failure_reason || t.session_id?.slice(0, 14) || t.subscription_id?.slice(0, 14) || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </DashboardLayout>
  );
}
