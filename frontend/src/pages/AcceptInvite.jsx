import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { toast } from "sonner";
import { Loader2, Users, ArrowRight, Terminal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { isAuthenticated } from "@/lib/auth";
import { useWorkspaces } from "@/lib/workspaces";

export default function AcceptInvite() {
  const { token } = useParams();
  const navigate = useNavigate();
  const { refresh, setCurrent } = useWorkspaces();
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    api
      .get(`/invites/${token}`)
      .then((r) => setPreview(r.data))
      .catch((e) =>
        setErr(e?.response?.data?.detail || "This invite is invalid or expired."),
      );
  }, [token]);

  const accept = async () => {
    if (!isAuthenticated()) {
      // Stash intent for after login
      try {
        localStorage.setItem("codeganak.pending_invite", token);
      } catch {
        // no-op
      }
      navigate("/login");
      return;
    }
    setBusy(true);
    try {
      const { data } = await api.post(`/invites/${token}/accept`);
      toast.success(`Joined ${data.workspace_name} as ${data.role}`);
      await refresh();
      setCurrent(data.workspace_id);
      navigate("/dashboard");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to accept invite");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid place-items-center px-6">
      <div className="w-full max-w-md border border-border/60 rounded-md p-8 bg-secondary/20">
        <Link to="/" className="flex items-center gap-2 w-fit">
          <div className="w-7 h-7 rounded-sm bg-primary/15 border border-primary/40 grid place-items-center">
            <Terminal className="w-4 h-4 text-primary" strokeWidth={2.4} />
          </div>
          <span className="font-display font-black text-[15px] tracking-tighter">
            CodeGanak
          </span>
        </Link>
        {err ? (
          <div className="mt-8 text-center">
            <h2 className="font-display font-bold text-2xl tracking-tight">
              Invite unavailable
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">{err}</p>
            <Button asChild className="mt-6" variant="outline">
              <Link to="/dashboard">Back to dashboard</Link>
            </Button>
          </div>
        ) : !preview ? (
          <div className="mt-10 flex items-center gap-2 justify-center text-muted-foreground text-sm">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading invite…
          </div>
        ) : (
          <div className="mt-8">
            <div className="tiny-label text-accent">workspace invite</div>
            <h2 className="mt-3 font-display font-bold text-2xl tracking-tight">
              Join {preview.workspace_name}
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {preview.owner_name} invited you to CodeGanak as{" "}
              <span className="font-mono text-foreground">{preview.role}</span>.
            </p>
            <Button
              onClick={accept}
              disabled={busy}
              className="w-full h-11 mt-8"
              data-testid="accept-invite-button"
            >
              {busy ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Users className="w-4 h-4 mr-2" />
              )}
              {isAuthenticated() ? "Accept invite" : "Sign in to accept"}
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
