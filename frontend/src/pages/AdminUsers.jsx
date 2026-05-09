import { useEffect, useState } from "react";
import DashboardLayout from "../components/DashboardLayout";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter,
} from "../components/ui/dialog";
import {
  Prohibit, CheckCircle, Trash, PencilSimple, Key, Crown, Eraser,
  EnvelopeSimple, Receipt, DotsThreeVertical,
} from "@phosphor-icons/react";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator,
} from "../components/ui/dropdown-menu";
import { toast } from "sonner";

const PLAN_OPTS = ["free", "basic", "pro", "diamond", "golden", "business"];

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [filter, setFilter] = useState("");
  const [openDialog, setOpenDialog] = useState(null); // {type, user}

  const load = () => api.get("/admin/users").then((r) => setUsers(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const toggleBan = async (u) => {
    try {
      await api.post(`/admin/users/${u.user_id}/ban`, { banned: !u.banned });
      toast.success(u.banned ? "User unbanned" : "User banned");
      load();
    } catch { toast.error("Action failed"); }
  };

  const handleDelete = async (u) => {
    if (!window.confirm(`Permanently delete ${u.email}? This cascades licenses, scans, activations.`)) return;
    try {
      await api.delete(`/admin/users/${u.user_id}`);
      toast.success("User deleted");
      load();
    } catch (err) { toast.error(err?.response?.data?.detail || "Delete failed"); }
  };

  const wipeLicense = async (u) => {
    if (!window.confirm(`Wipe license for ${u.email}? Plan reverts to free.`)) return;
    try {
      await api.post(`/admin/users/${u.user_id}/wipe-license`);
      toast.success("License wiped");
      load();
    } catch { toast.error("Wipe failed"); }
  };

  const filtered = users.filter((u) => {
    const q = filter.toLowerCase();
    return !q || u.email.toLowerCase().includes(q) || (u.name || "").toLowerCase().includes(q);
  });

  return (
    <DashboardLayout mode="admin">
      <div className="space-y-6 fade-up">
        <div className="flex items-end justify-between flex-wrap gap-4">
          <div>
            <span className="label-tech">/ admin / users</span>
            <h1 className="font-mono font-bold text-3xl mt-2">Users ({users.length})</h1>
          </div>
          <Input
            placeholder="Filter by email or name…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="rounded-none bg-[#0a0a0a] border-white/15 h-10 max-w-xs font-mono text-xs"
            data-testid="users-filter-input"
          />
        </div>
        <div className="card-tech overflow-x-auto">
          <table className="w-full text-xs font-mono min-w-[900px]" data-testid="users-table">
            <thead className="text-left text-[#737373] border-b border-white/10">
              <tr>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Plan</th>
                <th className="px-4 py-3">Provider</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((u) => (
                <tr key={u.user_id} className="border-b border-white/5 hover:bg-white/[0.02]">
                  <td className="px-4 py-3 text-white">{u.email}</td>
                  <td className="px-4 py-3 text-[#a0a6ad]">{u.name}</td>
                  <td className="px-4 py-3"><span className={u.role === "admin" ? "text-[#4da3ff]" : "text-[#a0a6ad]"}>{u.role}</span></td>
                  <td className="px-4 py-3 text-[#00d4aa]">{u.license?.plan?.toUpperCase() || "—"}</td>
                  <td className="px-4 py-3 text-[#737373]">{u.auth_provider}</td>
                  <td className="px-4 py-3">{u.banned ? <span className="text-[#ff4757]">BANNED</span> : <span className="text-[#00d4aa]">active</span>}</td>
                  <td className="px-4 py-3">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button size="sm" variant="ghost" className="rounded-none h-8 hover:bg-white/5" data-testid={`user-actions-${u.user_id}`}>
                          <DotsThreeVertical size={16} weight="bold" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent className="bg-[#121212] border-white/15 rounded-none font-mono text-xs">
                        <DropdownMenuItem onClick={() => setOpenDialog({ type: "edit", user: u })} data-testid={`edit-${u.user_id}`}>
                          <PencilSimple size={12} className="mr-2" /> Edit user
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setOpenDialog({ type: "plan", user: u })} data-testid={`plan-${u.user_id}`}>
                          <Crown size={12} className="mr-2" /> Assign plan
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setOpenDialog({ type: "password", user: u })} data-testid={`password-${u.user_id}`}>
                          <Key size={12} className="mr-2" /> Set password
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setOpenDialog({ type: "transactions", user: u })} data-testid={`txns-${u.user_id}`}>
                          <Receipt size={12} className="mr-2" /> View transactions
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setOpenDialog({ type: "contact", user: u })} data-testid={`contact-${u.user_id}`}>
                          <EnvelopeSimple size={12} className="mr-2" /> Contact via email
                        </DropdownMenuItem>
                        <DropdownMenuSeparator className="bg-white/10" />
                        <DropdownMenuItem onClick={() => wipeLicense(u)} className="text-[#ffab00] focus:text-[#ffab00]" data-testid={`wipe-${u.user_id}`}>
                          <Eraser size={12} className="mr-2" /> Wipe license
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => toggleBan(u)} disabled={u.role === "admin"} className="text-[#ff4757] focus:text-[#ff4757]" data-testid={`ban-${u.user_id}`}>
                          {u.banned ? <><CheckCircle size={12} className="mr-2" /> Unban</> : <><Prohibit size={12} className="mr-2" /> Ban</>}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleDelete(u)} disabled={u.role === "admin"} className="text-[#ff4757] focus:text-[#ff4757]" data-testid={`delete-${u.user_id}`}>
                          <Trash size={12} className="mr-2" /> Delete user
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {openDialog?.type === "edit" && <EditUserDialog user={openDialog.user} onClose={() => { setOpenDialog(null); load(); }} />}
      {openDialog?.type === "plan" && <AssignPlanDialog user={openDialog.user} onClose={() => { setOpenDialog(null); load(); }} />}
      {openDialog?.type === "password" && <SetPasswordDialog user={openDialog.user} onClose={() => setOpenDialog(null)} />}
      {openDialog?.type === "transactions" && <TransactionsDialog user={openDialog.user} onClose={() => setOpenDialog(null)} />}
      {openDialog?.type === "contact" && <ContactDialog user={openDialog.user} onClose={() => setOpenDialog(null)} />}
    </DashboardLayout>
  );
}

function BaseDialog({ title, children, onClose, footer }) {
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-[#0a0a0a] border-white/15 rounded-none max-w-lg font-mono">
        <DialogHeader><DialogTitle className="font-mono tracking-tight">{title}</DialogTitle></DialogHeader>
        <div className="py-2">{children}</div>
        {footer && <DialogFooter>{footer}</DialogFooter>}
      </DialogContent>
    </Dialog>
  );
}

function EditUserDialog({ user, onClose }) {
  const [name, setName] = useState(user.name || "");
  const [email, setEmail] = useState(user.email);
  const [role, setRole] = useState(user.role);
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      await api.patch(`/admin/users/${user.user_id}`, { name, email, role });
      toast.success("User updated"); onClose();
    } catch (err) { toast.error(err?.response?.data?.detail || "Update failed"); setSaving(false); }
  };
  return (
    <BaseDialog title={`Edit ${user.email}`} onClose={onClose} footer={
      <Button onClick={save} disabled={saving} className="btn-primary rounded-none" data-testid="edit-save-btn">{saving ? "Saving…" : "Save"}</Button>
    }>
      <div className="space-y-3">
        <div><Label className="label-tech">Name</Label><Input value={name} onChange={(e) => setName(e.target.value)} className="rounded-none bg-[#0a0a0a] border-white/15 mt-1 h-10" data-testid="edit-name" /></div>
        <div><Label className="label-tech">Email</Label><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="rounded-none bg-[#0a0a0a] border-white/15 mt-1 h-10" data-testid="edit-email" /></div>
        <div><Label className="label-tech">Role</Label>
          <Select value={role} onValueChange={setRole}>
            <SelectTrigger className="rounded-none bg-[#0a0a0a] border-white/15 mt-1 h-10" data-testid="edit-role"><SelectValue /></SelectTrigger>
            <SelectContent className="rounded-none bg-[#121212] border-white/15"><SelectItem value="user">user</SelectItem><SelectItem value="admin">admin</SelectItem></SelectContent>
          </Select>
        </div>
      </div>
    </BaseDialog>
  );
}

function AssignPlanDialog({ user, onClose }) {
  const [plan, setPlan] = useState("pro");
  const [days, setDays] = useState("");
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      const body = { plan }; if (days) body.duration_days = Number(days);
      await api.post(`/admin/users/${user.user_id}/assign-plan`, body);
      toast.success(`Assigned ${plan.toUpperCase()} to ${user.email}`); onClose();
    } catch (err) { toast.error(err?.response?.data?.detail || "Assign failed"); setSaving(false); }
  };
  return (
    <BaseDialog title={`Assign plan — ${user.email}`} onClose={onClose} footer={
      <Button onClick={save} disabled={saving} className="btn-primary rounded-none" data-testid="assign-save-btn">{saving ? "Saving…" : "Assign"}</Button>
    }>
      <div className="space-y-3">
        <div><Label className="label-tech">Plan</Label>
          <Select value={plan} onValueChange={setPlan}>
            <SelectTrigger className="rounded-none bg-[#0a0a0a] border-white/15 mt-1 h-10" data-testid="assign-plan-select"><SelectValue /></SelectTrigger>
            <SelectContent className="rounded-none bg-[#121212] border-white/15">{PLAN_OPTS.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div><Label className="label-tech">Duration days (optional — uses plan default)</Label>
          <Input type="number" value={days} onChange={(e) => setDays(e.target.value)} placeholder="e.g. 30" className="rounded-none bg-[#0a0a0a] border-white/15 mt-1 h-10" data-testid="assign-days" />
        </div>
        <p className="text-xs text-[#737373]">Skips payment — sets license active for the chosen duration.</p>
      </div>
    </BaseDialog>
  );
}

function SetPasswordDialog({ user, onClose }) {
  const [pw, setPw] = useState("");
  const [saving, setSaving] = useState(false);
  const save = async () => {
    if (pw.length < 6) { toast.error("Min 6 chars"); return; }
    setSaving(true);
    try {
      await api.post(`/admin/users/${user.user_id}/set-password`, { new_password: pw });
      toast.success("Password updated"); onClose();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); setSaving(false); }
  };
  return (
    <BaseDialog title={`Set password — ${user.email}`} onClose={onClose} footer={
      <Button onClick={save} disabled={saving} className="btn-primary rounded-none" data-testid="setpw-save-btn">{saving ? "Saving…" : "Update"}</Button>
    }>
      <div><Label className="label-tech">New password (min 6)</Label>
        <Input type="text" value={pw} onChange={(e) => setPw(e.target.value)} className="rounded-none bg-[#0a0a0a] border-white/15 mt-1 h-10" data-testid="setpw-input" />
        <p className="text-xs text-[#737373] mt-2">User keeps existing access; on next login they use this new password.</p>
      </div>
    </BaseDialog>
  );
}

function TransactionsDialog({ user, onClose }) {
  const [data, setData] = useState(null);
  useEffect(() => { api.get(`/admin/users/${user.user_id}/transactions`).then((r) => setData(r.data)).catch(() => {}); }, [user.user_id]);
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="bg-[#0a0a0a] border-white/15 rounded-none max-w-3xl font-mono">
        <DialogHeader><DialogTitle className="font-mono">Transactions — {user.email}</DialogTitle></DialogHeader>
        <div className="py-2">
          {!data ? <p className="text-xs text-[#737373]">Loading…</p> : (
            <>
              <div className="grid grid-cols-3 gap-3 mb-4 text-xs">
                <div className="border border-white/10 p-3"><span className="label-tech">Total spent</span><div className="text-2xl font-bold text-[#00d4aa] mt-1">${data.total_spent_usd}</div></div>
                <div className="border border-white/10 p-3"><span className="label-tech">Transactions</span><div className="text-2xl font-bold mt-1">{data.count}</div></div>
                <div className="border border-white/10 p-3"><span className="label-tech">Last</span><div className="text-xs text-[#a0a6ad] mt-1 truncate">{data.transactions[0]?.created_at?.slice(0,10) || "—"}</div></div>
              </div>
              <div className="max-h-80 overflow-y-auto border border-white/10">
                <table className="w-full text-xs" data-testid="user-txns-table">
                  <thead className="bg-white/[0.03] text-[#737373] sticky top-0">
                    <tr><th className="px-3 py-2 text-left">Date</th><th className="px-3 py-2 text-left">Plan</th><th className="px-3 py-2 text-left">Amount</th><th className="px-3 py-2 text-left">Provider</th><th className="px-3 py-2 text-left">Status</th></tr>
                  </thead>
                  <tbody>
                    {data.transactions.length === 0 && <tr><td colSpan="5" className="text-center py-6 text-[#737373]">No transactions.</td></tr>}
                    {data.transactions.map((t, i) => (
                      <tr key={i} className="border-t border-white/5">
                        <td className="px-3 py-2 text-[#737373]">{t.created_at?.slice(0,10)}</td>
                        <td className="px-3 py-2 uppercase">{t.plan}</td>
                        <td className="px-3 py-2 text-[#00d4aa]">${(t.amount_cents/100).toFixed(2)}</td>
                        <td className="px-3 py-2 text-[#a0a6ad]">{t.provider}</td>
                        <td className="px-3 py-2">
                          <span className={t.payment_status === "paid" || t.payment_status === "active" ? "text-[#00d4aa]" : t.payment_status === "failed" ? "text-[#ff4757]" : "text-[#ffab00]"}>
                            {t.payment_status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ContactDialog({ user, onClose }) {
  const [subject, setSubject] = useState("Message from xss0r support");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const send = async () => {
    if (!subject.trim() || !message.trim()) { toast.error("Subject and message required"); return; }
    setSending(true);
    try {
      await api.post(`/admin/users/${user.user_id}/contact`, { subject, message });
      toast.success(`Email sent to ${user.email}`); onClose();
    } catch (err) { toast.error(err?.response?.data?.detail || "Send failed"); setSending(false); }
  };
  return (
    <BaseDialog title={`Email — ${user.email}`} onClose={onClose} footer={
      <Button onClick={send} disabled={sending} className="btn-primary rounded-none" data-testid="contact-send-btn">{sending ? "Sending…" : "Send"}</Button>
    }>
      <div className="space-y-3">
        <div><Label className="label-tech">Subject</Label><Input value={subject} onChange={(e) => setSubject(e.target.value)} className="rounded-none bg-[#0a0a0a] border-white/15 mt-1 h-10" data-testid="contact-subject" /></div>
        <div><Label className="label-tech">Message</Label><Textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={6} className="rounded-none bg-[#0a0a0a] border-white/15 mt-1 font-mono text-xs" data-testid="contact-message" /></div>
        <p className="text-xs text-[#737373]">Sent via Resend (currently DRY-RUN — logged to backend).</p>
      </div>
    </BaseDialog>
  );
}
