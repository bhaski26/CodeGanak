import { useEffect, useState, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  Users,
  Link as LinkIcon,
  Copy,
  Trash2,
  Loader2,
  Crown,
  Shield,
  User as UserIcon,
  ArrowLeft,
  X,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import AppHeader from "@/components/AppHeader";
import { api } from "@/lib/api";
import { getUser } from "@/lib/auth";
import { useWorkspaces } from "@/lib/workspaces";

const ROLE_META = {
  owner: { icon: Crown, tone: "text-accent" },
  admin: { icon: Shield, tone: "text-primary" },
  member: { icon: UserIcon, tone: "text-muted-foreground" },
};

export default function WorkspaceSettings({ onOpenCommand }) {
  const navigate = useNavigate();
  const me = getUser();
  const { workspaceId } = useParams();
  const { workspaces, refresh } = useWorkspaces();
  const [members, setMembers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [name, setName] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const ws = useMemo(
    () => workspaces.find((w) => w.id === workspaceId),
    [workspaces, workspaceId],
  );
  const myRole = ws?.role || "member";
  const canManage = myRole === "owner" || myRole === "admin";

  const loadAll = async () => {
    setLoading(true);
    try {
      await refresh();
      const [{ data: m }, { data: i }] = await Promise.all([
        api.get(`/workspaces/${workspaceId}/members`),
        canManage
          ? api.get(`/workspaces/${workspaceId}/invites`)
          : Promise.resolve({ data: [] }),
      ]);
      setMembers(m || []);
      setInvites(i || []);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to load workspace");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
     
  }, [workspaceId]);

  useEffect(() => {
    if (ws) setName(ws.name);
  }, [ws]);

  const rename = async () => {
    if (!name.trim() || name === ws?.name) return;
    setBusy(true);
    try {
      await api.patch(`/workspaces/${workspaceId}`, { name: name.trim() });
      toast.success("Workspace renamed");
      await refresh();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Rename failed");
    } finally {
      setBusy(false);
    }
  };

  const createInvite = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(
        `/workspaces/${workspaceId}/invites`,
        { role: inviteRole },
      );
      const url = `${window.location.origin}/invite/${data.token}`;
      await navigator.clipboard.writeText(url).catch(() => {});
      toast.success("Invite link copied to clipboard");
      loadAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to create invite");
    } finally {
      setBusy(false);
    }
  };

  const revokeInvite = async (id) => {
    await api.delete(`/workspaces/${workspaceId}/invites/${id}`);
    toast.success("Invite revoked");
    loadAll();
  };

  const copyInvite = (token) => {
    const url = `${window.location.origin}/invite/${token}`;
    navigator.clipboard.writeText(url).catch(() => {});
    toast.success("Copied");
  };

  const changeRole = async (userId, role) => {
    try {
      await api.patch(`/workspaces/${workspaceId}/members/${userId}`, { role });
      toast.success("Role updated");
      loadAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Update failed");
    }
  };

  const removeMember = async (userId, isSelf) => {
    if (!confirm(isSelf ? "Leave this workspace?" : "Remove this member?")) return;
    try {
      await api.delete(`/workspaces/${workspaceId}/members/${userId}`);
      toast.success(isSelf ? "Left workspace" : "Member removed");
      if (isSelf) {
        await refresh();
        navigate("/dashboard");
      } else {
        loadAll();
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  const deleteWorkspace = async () => {
    if (!confirm(`Delete "${ws?.name}" and all its repositories? This cannot be undone.`)) return;
    try {
      await api.delete(`/workspaces/${workspaceId}`);
      toast.success("Workspace deleted");
      await refresh();
      navigate("/dashboard");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Delete failed");
    }
  };

  return (
    <div className="min-h-screen">
      <AppHeader onOpenCommand={onOpenCommand} />
      <main className="mx-auto max-w-4xl px-6 py-10">
        <button
          onClick={() => navigate("/dashboard")}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
        >
          <ArrowLeft className="w-3 h-3" /> Back to workspace
        </button>

        <div className="mt-4 flex items-center gap-2">
          <Users className="w-4 h-4 text-primary" />
          <span className="tiny-label">workspace settings</span>
        </div>
        <h1 className="mt-2 font-display font-black text-4xl tracking-tighter">
          {ws?.name || "…"}
        </h1>

        {loading ? (
          <div className="mt-10 flex items-center gap-2 text-muted-foreground text-sm">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading…
          </div>
        ) : (
          <>
            {/* Rename */}
            {canManage && !ws?.is_personal && (
              <section className="mt-10 border border-border/60 rounded-md p-5">
                <div className="tiny-label">workspace name</div>
                <div className="mt-3 flex gap-2">
                  <Input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="h-10 bg-secondary/30 border-border"
                    data-testid="workspace-rename-input"
                  />
                  <Button
                    onClick={rename}
                    disabled={busy || name === ws?.name || !name.trim()}
                    data-testid="workspace-rename-submit"
                  >
                    Rename
                  </Button>
                </div>
              </section>
            )}

            {/* Invites */}
            {canManage && (
              <section className="mt-6 border border-border/60 rounded-md p-5">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="tiny-label">invite teammates</div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Generate a share link. Anyone signed in who visits it joins your workspace.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Select value={inviteRole} onValueChange={setInviteRole}>
                      <SelectTrigger
                        className="h-9 w-28 bg-secondary/30 border-border text-xs"
                        data-testid="invite-role-select"
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="member">Member</SelectItem>
                        <SelectItem value="admin">Admin</SelectItem>
                      </SelectContent>
                    </Select>
                    <Button
                      onClick={createInvite}
                      disabled={busy}
                      data-testid="create-invite-button"
                    >
                      <LinkIcon className="w-3.5 h-3.5 mr-1.5" />
                      Create link
                    </Button>
                  </div>
                </div>
                {invites.length > 0 && (
                  <div className="mt-5 space-y-2">
                    {invites.map((inv) => {
                      const url = `${window.location.origin}/invite/${inv.token}`;
                      return (
                        <div
                          key={inv.id}
                          className="flex items-center gap-2 px-3 py-2 rounded-sm bg-secondary/30 border border-border/60"
                        >
                          <LinkIcon className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                          <span className="text-xs font-mono truncate flex-1">{url}</span>
                          <span className="tiny-label !text-[9px]">{inv.role}</span>
                          <button
                            onClick={() => copyInvite(inv.token)}
                            className="text-muted-foreground hover:text-primary transition-colors"
                            aria-label="Copy link"
                          >
                            <Copy className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => revokeInvite(inv.id)}
                            className="text-muted-foreground hover:text-destructive transition-colors"
                            aria-label="Revoke"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>
            )}

            {/* Members */}
            <section className="mt-6 border border-border/60 rounded-md">
              <div className="flex items-center justify-between px-5 py-4 border-b border-border/60">
                <div className="tiny-label">members ({members.length})</div>
                <Button variant="ghost" size="sm" onClick={loadAll} className="h-7">
                  <RefreshCw className="w-3.5 h-3.5" />
                </Button>
              </div>
              <Table>
                <TableHeader>
                  <TableRow className="border-border/60 hover:bg-transparent">
                    <TableHead className="text-[10px] font-mono uppercase tracking-widest">Name</TableHead>
                    <TableHead className="text-[10px] font-mono uppercase tracking-widest">Email</TableHead>
                    <TableHead className="text-[10px] font-mono uppercase tracking-widest">Role</TableHead>
                    <TableHead className="text-right text-[10px] font-mono uppercase tracking-widest">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {members.map((m) => {
                    const meta = ROLE_META[m.role] || ROLE_META.member;
                    const Icon = meta.icon;
                    const isMe = me && m.user_id === me.id;
                    const isOwnerRow = m.role === "owner";
                    return (
                      <TableRow key={m.user_id} className="border-border/60 hover:bg-secondary/20">
                        <TableCell className="text-sm">
                          {m.name}
                          {isMe && (
                            <span className="tiny-label !text-[9px] ml-2">you</span>
                          )}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground font-mono">
                          {m.email}
                        </TableCell>
                        <TableCell>
                          <span className={`inline-flex items-center gap-1 text-xs font-mono ${meta.tone}`}>
                            <Icon className="w-3 h-3" /> {m.role}
                          </span>
                        </TableCell>
                        <TableCell className="text-right">
                          {canManage && !isOwnerRow && (
                            <Select
                              value={m.role}
                              onValueChange={(v) => changeRole(m.user_id, v)}
                            >
                              <SelectTrigger className="h-7 w-24 bg-secondary/30 border-border text-xs inline-flex">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="member">Member</SelectItem>
                                <SelectItem value="admin">Admin</SelectItem>
                                {myRole === "owner" && (
                                  <SelectItem value="owner">Owner</SelectItem>
                                )}
                              </SelectContent>
                            </Select>
                          )}
                          {((canManage && !isOwnerRow) || isMe) && !ws?.is_personal && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => removeMember(m.user_id, isMe)}
                              className="h-7 ml-2 text-muted-foreground hover:text-destructive"
                            >
                              <Trash2 className="w-3 h-3" />
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </section>

            {/* Danger zone */}
            {myRole === "owner" && !ws?.is_personal && (
              <section className="mt-6 border border-destructive/40 rounded-md p-5">
                <div className="tiny-label text-destructive">danger zone</div>
                <p className="mt-2 text-sm text-muted-foreground">
                  Deleting this workspace removes all indexed repositories and memberships. This cannot be undone.
                </p>
                <Button
                  variant="destructive"
                  onClick={deleteWorkspace}
                  className="mt-4"
                  data-testid="workspace-delete-button"
                >
                  <Trash2 className="w-3.5 h-3.5 mr-2" /> Delete workspace
                </Button>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
