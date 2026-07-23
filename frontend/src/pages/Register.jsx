import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Terminal, ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { setAuth } from "@/lib/auth";
import { REGISTER } from "@/constants/testIds";

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    confirm: "",
  });
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    if (form.password !== form.confirm) {
      toast.error("Passwords do not match");
      return;
    }
    setBusy(true);
    try {
      const { data } = await api.post("/auth/register", {
        name: form.name,
        email: form.email,
        password: form.password,
      });
      setAuth(data.access_token, data.user);
      toast.success(`Welcome, ${data.user.name}`);
      navigate("/dashboard");
    } catch (err) {
      const detail =
        err?.response?.data?.detail || err?.message || "Registration failed";
      toast.error(detail);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between p-12 border-r border-border/60 relative overflow-hidden">
        <div className="absolute inset-0 grid-bg opacity-60 [mask-image:linear-gradient(to_bottom,black,transparent)]" />
        <Link to="/" className="relative flex items-center gap-2 w-fit">
          <div className="w-7 h-7 rounded-sm bg-primary/15 border border-primary/40 grid place-items-center">
            <Terminal className="w-4 h-4 text-primary" strokeWidth={2.4} />
          </div>
          <span className="font-display font-black text-[15px] tracking-tighter">
            CodeGanak
          </span>
        </Link>
        <div className="relative">
          <div className="tiny-label text-accent">start free</div>
          <h1 className="mt-3 font-display font-black text-4xl leading-[1.05] tracking-tighter">
            Turn a repo into
            <br />
            a conversation.
          </h1>
          <p className="mt-4 text-sm text-muted-foreground max-w-md leading-relaxed">
            No card required. Index your first repository in under a minute.
          </p>
        </div>
        <div className="relative tiny-label !text-[9px] text-muted-foreground/70">
          understand · visualize · engineer
        </div>
      </div>

      <div className="flex items-center justify-center p-6 sm:p-12">
        <form onSubmit={onSubmit} className="w-full max-w-sm space-y-6">
          <div>
            <h2 className="font-display font-bold text-2xl tracking-tight">
              Create your account
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              We only need an email and a password.
            </p>
          </div>
          <div className="space-y-3">
            <div>
              <Label htmlFor="name" className="tiny-label">Name</Label>
              <Input
                id="name" required autoComplete="name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="mt-2 h-11 bg-secondary/30 border-border text-sm"
                data-testid={REGISTER.nameInput}
              />
            </div>
            <div>
              <Label htmlFor="email" className="tiny-label">Email</Label>
              <Input
                id="email" type="email" required autoComplete="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="mt-2 h-11 bg-secondary/30 border-border font-mono text-sm"
                data-testid={REGISTER.emailInput}
              />
            </div>
            <div>
              <Label htmlFor="password" className="tiny-label">Password</Label>
              <Input
                id="password" type="password" required autoComplete="new-password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                className="mt-2 h-11 bg-secondary/30 border-border font-mono text-sm"
                data-testid={REGISTER.passwordInput}
              />
            </div>
            <div>
              <Label htmlFor="confirm" className="tiny-label">
                Confirm password
              </Label>
              <Input
                id="confirm" type="password" required autoComplete="new-password"
                value={form.confirm}
                onChange={(e) => setForm({ ...form, confirm: e.target.value })}
                className="mt-2 h-11 bg-secondary/30 border-border font-mono text-sm"
                data-testid={REGISTER.passwordConfirmInput}
              />
            </div>
          </div>
          <Button
            type="submit"
            disabled={busy}
            className="w-full h-11"
            data-testid={REGISTER.submitButton}
          >
            {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ArrowRight className="w-4 h-4 mr-2" />}
            Create account
          </Button>
          <div className="text-sm text-muted-foreground text-center">
            Already have an account?{" "}
            <Link
              to="/login"
              className="text-primary hover:text-accent transition-colors font-medium"
              data-testid={REGISTER.loginLink}
            >
              Sign in
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
