import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Terminal, ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { setAuth } from "@/lib/auth";
import { LOGIN } from "@/constants/testIds";

export default function Login() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post("/auth/login", form);
      setAuth(data.access_token, data.user);
      toast.success(`Welcome back, ${data.user.name}`);
      // handle pending invite (from /invite/:token deep-link)
      let pending = null;
      try {
        pending = localStorage.getItem("codeganak.pending_invite");
        if (pending) localStorage.removeItem("codeganak.pending_invite");
      } catch {
        // no-op
      }
      navigate(pending ? `/invite/${pending}` : "/dashboard");
    } catch (err) {
      const detail =
        err?.response?.data?.detail || err?.message || "Login failed";
      toast.error(detail);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      {/* left */}
      <div className="hidden lg:flex flex-col justify-between p-12 border-r border-border/60 relative overflow-hidden">
        <div className="absolute inset-0 grid-bg opacity-60 [mask-image:linear-gradient(to_bottom,black,transparent)]" />
        <Link
          to="/"
          className="relative flex items-center gap-2 w-fit"
        >
          <div className="w-7 h-7 rounded-sm bg-primary/15 border border-primary/40 grid place-items-center">
            <Terminal className="w-4 h-4 text-primary" strokeWidth={2.4} />
          </div>
          <span className="font-display font-black text-[15px] tracking-tighter">
            CodeGanak
          </span>
        </Link>
        <div className="relative">
          <div className="tiny-label text-accent">welcome back</div>
          <h1 className="mt-3 font-display font-black text-4xl leading-[1.05] tracking-tighter">
            Sign back in and
            <br />
            keep exploring.
          </h1>
          <p className="mt-4 text-sm text-muted-foreground max-w-md leading-relaxed">
            Your indexed repositories are one click away.
          </p>
        </div>
        <div className="relative tiny-label !text-[9px] text-muted-foreground/70">
          understand · visualize · engineer
        </div>
      </div>

      {/* right */}
      <div className="flex items-center justify-center p-6 sm:p-12">
        <form
          onSubmit={onSubmit}
          className="w-full max-w-sm space-y-6"
        >
          <div>
            <h2 className="font-display font-bold text-2xl tracking-tight">
              Sign in
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              Enter your credentials to continue.
            </p>
          </div>
          <div className="space-y-3">
            <div>
              <Label htmlFor="email" className="tiny-label">
                Email
              </Label>
              <Input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={form.email}
                onChange={(e) =>
                  setForm({ ...form, email: e.target.value })
                }
                className="mt-2 h-11 bg-secondary/30 border-border font-mono text-sm"
                data-testid={LOGIN.emailInput}
              />
            </div>
            <div>
              <Label htmlFor="password" className="tiny-label">
                Password
              </Label>
              <Input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                value={form.password}
                onChange={(e) =>
                  setForm({ ...form, password: e.target.value })
                }
                className="mt-2 h-11 bg-secondary/30 border-border font-mono text-sm"
                data-testid={LOGIN.passwordInput}
              />
            </div>
          </div>
          <Button
            type="submit"
            disabled={busy}
            className="w-full h-11"
            data-testid={LOGIN.submitButton}
          >
            {busy ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <ArrowRight className="w-4 h-4 mr-2" />
            )}
            Sign in
          </Button>
          <div className="text-sm text-muted-foreground text-center">
            Don&apos;t have an account?{" "}
            <Link
              to="/register"
              className="text-primary hover:text-accent transition-colors font-medium"
              data-testid={LOGIN.registerLink}
            >
              Create one
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
