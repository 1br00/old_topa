import { useEffect, useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { api } from "../lib/api";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import {
  CurrencyDollar, TrendUp, ChartBar, Receipt, Warning, CreditCard,
} from "@phosphor-icons/react";

const PROVIDER_COLORS = { stripe: "#635bff", paypal: "#0070ba", manual_admin: "#10b981", unknown: "#737373" };
const PLAN_COLORS = { basic: "#737373", pro: "#2b6cf2", diamond: "#7c5cff", golden: "#f5a623", business: "#10b981", free: "#404040" };

function $(cents) { return `$${((cents || 0) / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`; }

export default function AdminSales() {
  const [data, setData] = useState(null);
  const [failed, setFailed] = useState([]);

  useEffect(() => {
    api.get("/admin/sales/summary").then((r) => setData(r.data)).catch(() => {});
    api.get("/admin/payments/failed?limit=20").then((r) => setFailed(r.data)).catch(() => {});
  }, []);

  if (!data) {
    return (
      <DashboardLayout mode="admin">
        <div className="font-mono text-sm text-[#a0a6ad]"><span className="cursor-blink">loading sales</span></div>
      </DashboardLayout>
    );
  }

  const stats = [
    { label: "Total revenue (all time)", value: `$${data.total_revenue_usd.toLocaleString()}`, icon: CurrencyDollar, color: "#00d4aa" },
    { label: "Last 24h", value: $(data.revenue_24h_cents), icon: TrendUp, color: "#4da3ff" },
    { label: "Last 7 days", value: $(data.revenue_7d_cents), icon: TrendUp, color: "#4da3ff" },
    { label: "Last 30 days", value: $(data.revenue_30d_cents), icon: ChartBar, color: "#4da3ff" },
    { label: "Last 365 days", value: $(data.revenue_365d_cents), icon: ChartBar, color: "#4da3ff" },
    { label: "Paid transactions", value: data.total_paid_count, icon: Receipt, color: "#00d4aa" },
    { label: "Failed transactions", value: data.failed_count, icon: Warning, color: "#ff4757" },
  ];

  const seriesData = (data.series_daily_30d || []).map((d) => ({
    date: d.date.slice(5), // MM-DD
    revenue: d.revenue_cents / 100,
    count: d.count,
  }));

  const providerData = (data.by_provider || []).map((p) => ({
    name: p.provider, value: p.revenue_cents / 100, count: p.count,
  }));
  const planData = (data.by_plan || []).map((p) => ({
    name: p.plan, value: p.revenue_cents / 100, count: p.count,
  }));

  return (
    <DashboardLayout mode="admin">
      <div className="space-y-6 fade-up">
        <div>
          <span className="label-tech">/ admin / sales</span>
          <h1 className="font-mono font-bold text-3xl mt-2">Sales & revenue</h1>
        </div>

        {/* KPI cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-px bg-white/10" data-testid="sales-kpis">
          {stats.map((s, i) => (
            <div key={i} className="bg-[#0a0a0a] p-5 hover:bg-[#121212] transition-colors">
              <s.icon size={18} weight="duotone" style={{ color: s.color }} className="mb-2" />
              <div className="label-tech text-[10px]">{s.label}</div>
              <div className="font-mono text-xl font-bold mt-1" style={{ color: s.color }}>{s.value}</div>
            </div>
          ))}
        </div>

        {/* Revenue chart */}
        <div className="card-tech p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <span className="label-tech">/ revenue · last 30 days</span>
              <h3 className="font-mono font-semibold mt-1">Daily revenue</h3>
            </div>
          </div>
          <div style={{ width: "100%", height: 280 }}>
            <ResponsiveContainer>
              <BarChart data={seriesData} margin={{ top: 10, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="date" stroke="#737373" fontSize={10} fontFamily="monospace" />
                <YAxis stroke="#737373" fontSize={10} fontFamily="monospace" tickFormatter={(v) => `$${v}`} />
                <Tooltip
                  contentStyle={{ background: "#121212", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 0, fontFamily: "monospace", fontSize: 11 }}
                  formatter={(v) => [`$${v.toFixed(2)}`, "Revenue"]}
                />
                <Bar dataKey="revenue" fill="#4da3ff" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* By provider */}
          <div className="card-tech p-6">
            <span className="label-tech">/ split by provider</span>
            <h3 className="font-mono font-semibold mt-1 mb-4">Stripe vs PayPal</h3>
            {providerData.length === 0 ? (
              <p className="text-xs text-[#737373] py-12 text-center">No paid transactions yet.</p>
            ) : (
              <>
                <div style={{ width: "100%", height: 220 }}>
                  <ResponsiveContainer>
                    <PieChart>
                      <Pie data={providerData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} innerRadius={40}>
                        {providerData.map((entry, i) => (
                          <Cell key={i} fill={PROVIDER_COLORS[entry.name] || "#737373"} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ background: "#121212", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 0, fontFamily: "monospace", fontSize: 11 }}
                        formatter={(v, n) => [`$${v.toFixed(2)}`, n]}
                      />
                      <Legend wrapperStyle={{ fontFamily: "monospace", fontSize: 11 }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="grid grid-cols-2 gap-2 mt-4 text-xs font-mono">
                  {providerData.map((p) => (
                    <div key={p.name} className="border border-white/10 p-3">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full" style={{ background: PROVIDER_COLORS[p.name] }} />
                        <span className="uppercase">{p.name}</span>
                      </div>
                      <div className="text-lg font-bold text-white mt-1">${p.value.toFixed(2)}</div>
                      <div className="text-[10px] text-[#737373]">{p.count} txns</div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* By plan */}
          <div className="card-tech p-6">
            <span className="label-tech">/ split by plan</span>
            <h3 className="font-mono font-semibold mt-1 mb-4">Revenue by plan</h3>
            {planData.length === 0 ? (
              <p className="text-xs text-[#737373] py-12 text-center">No paid transactions yet.</p>
            ) : (
              <>
                <div style={{ width: "100%", height: 220 }}>
                  <ResponsiveContainer>
                    <BarChart data={planData}>
                      <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
                      <XAxis dataKey="name" stroke="#737373" fontSize={10} fontFamily="monospace" />
                      <YAxis stroke="#737373" fontSize={10} fontFamily="monospace" tickFormatter={(v) => `$${v}`} />
                      <Tooltip
                        contentStyle={{ background: "#121212", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 0, fontFamily: "monospace", fontSize: 11 }}
                        formatter={(v) => [`$${v.toFixed(2)}`, "Revenue"]}
                      />
                      <Bar dataKey="value">
                        {planData.map((entry, i) => (
                          <Cell key={i} fill={PLAN_COLORS[entry.name] || "#737373"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Failed transactions */}
        <div className="card-tech p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <span className="label-tech">/ failed transactions</span>
              <h3 className="font-mono font-semibold mt-1 flex items-center gap-2">
                <Warning size={16} weight="duotone" className="text-[#ff4757]" />
                Recent failures ({failed.length})
              </h3>
            </div>
          </div>
          {failed.length === 0 ? (
            <p className="text-xs text-[#737373] py-6 text-center">No failed transactions — clean record.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono" data-testid="failed-table">
                <thead className="text-left text-[#737373] border-b border-white/10">
                  <tr>
                    <th className="px-3 py-2">Date</th>
                    <th className="px-3 py-2">User</th>
                    <th className="px-3 py-2">Plan</th>
                    <th className="px-3 py-2">Amount</th>
                    <th className="px-3 py-2">Provider</th>
                    <th className="px-3 py-2">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {failed.map((t, i) => (
                    <tr key={i} className="border-b border-white/5">
                      <td className="px-3 py-2 text-[#737373]">{t.created_at?.slice(0, 16).replace("T", " ")}</td>
                      <td className="px-3 py-2">{t.email}</td>
                      <td className="px-3 py-2 uppercase">{t.plan || "—"}</td>
                      <td className="px-3 py-2 text-[#ff4757]">${((t.amount_cents || 0) / 100).toFixed(2)}</td>
                      <td className="px-3 py-2 text-[#a0a6ad]">{t.provider}</td>
                      <td className="px-3 py-2 text-[#ff4757]">{t.failure_reason || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
