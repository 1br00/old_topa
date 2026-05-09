import { useEffect, useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Prohibit, CheckCircle } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function AdminUsers() {
  const [users, setUsers] = useState([]);

  const load = () => api.get("/admin/users").then((r) => setUsers(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const toggle = async (u) => {
    try {
      await api.post(`/admin/users/${u.user_id}/ban`, { banned: !u.banned });
      toast.success(u.banned ? "User unbanned" : "User banned");
      load();
    } catch { toast.error("Action failed"); }
  };

  return (
    <DashboardLayout mode="admin">
      <div className="space-y-6 fade-up">
        <div>
          <span className="label-tech">/ admin / users</span>
          <h1 className="font-mono font-bold text-3xl mt-2">Users</h1>
        </div>
        <div className="card-tech overflow-x-auto">
          <table className="w-full text-xs font-mono min-w-[800px]" data-testid="users-table">
            <thead className="text-left text-[#737373] border-b border-white/10">
              <tr>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Plan</th>
                <th className="px-4 py-3">Provider</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.user_id} className="border-b border-white/5 hover:bg-white/[0.02]">
                  <td className="px-4 py-3 text-white">{u.email}</td>
                  <td className="px-4 py-3 text-[#a0a6ad]">{u.name}</td>
                  <td className="px-4 py-3">
                    <span className={u.role === "admin" ? "text-[#4da3ff]" : "text-[#a0a6ad]"}>{u.role}</span>
                  </td>
                  <td className="px-4 py-3 text-[#00d4aa]">{u.license?.plan?.toUpperCase() || "—"}</td>
                  <td className="px-4 py-3 text-[#737373]">{u.auth_provider}</td>
                  <td className="px-4 py-3 text-[#737373]">{u.created_at?.slice(0, 10)}</td>
                  <td className="px-4 py-3">
                    {u.banned ? <span className="text-[#ff4757]">BANNED</span> : <span className="text-[#00d4aa]">active</span>}
                  </td>
                  <td className="px-4 py-3">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => toggle(u)}
                      disabled={u.role === "admin"}
                      className={`rounded-none h-8 text-xs ${u.banned ? "border-[#00d4aa]/40 text-[#00d4aa] hover:bg-[#00d4aa]/10" : "border-[#ff4757]/40 text-[#ff4757] hover:bg-[#ff4757]/10"}`}
                      data-testid={`toggle-ban-${u.user_id}`}
                    >
                      {u.banned ? <><CheckCircle size={12} className="mr-1" /> Unban</> : <><Prohibit size={12} className="mr-1" /> Ban</>}
                    </Button>
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
