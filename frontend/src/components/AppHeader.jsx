import { Link, useNavigate } from "react-router-dom";
import { Terminal, Command, LogOut, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getUser, clearAuth } from "@/lib/auth";
import WorkspaceSwitcher from "@/components/WorkspaceSwitcher";

export default function AppHeader({ onOpenCommand, right = null, showWorkspace = true }) {
  const navigate = useNavigate();
  const user = getUser();

  const handleLogout = () => {
    clearAuth();
    navigate("/login");
  };

  return (
    <header className="sticky top-0 z-40 border-b border-border/60 glass">
      <div className="mx-auto max-w-[1600px] px-6 h-14 flex items-center gap-6">
        <Link to="/dashboard" className="flex items-center gap-2 group">
          <div className="relative w-7 h-7 rounded-sm bg-primary/15 border border-primary/40 grid place-items-center overflow-hidden">
            <Terminal className="w-4 h-4 text-primary" strokeWidth={2.4} />
            <span className="absolute inset-0 grain" />
          </div>
          <div className="flex flex-col leading-none">
            <span className="font-display font-black text-[15px] tracking-tighter">
              CodeGanak
            </span>
            <span className="tiny-label !text-[8px] text-muted-foreground/70">
              understand · visualize · engineer
            </span>
          </div>
        </Link>

        <div className="flex-1" />

        {showWorkspace && user && <WorkspaceSwitcher />}

        <button
          onClick={onOpenCommand}
          className="hidden md:flex items-center gap-2 px-3 h-8 rounded-md border border-border bg-secondary/40 text-muted-foreground text-sm hover:bg-secondary hover:text-foreground transition-colors"
          data-testid="command-palette-trigger"
        >
          <Search className="w-3.5 h-3.5" />
          <span>Jump to…</span>
          <kbd className="ml-2 flex items-center gap-1 text-[10px] font-mono border border-border rounded px-1.5 py-0.5">
            <Command className="w-3 h-3" />K
          </kbd>
        </button>

        {right}

        {user && (
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex flex-col items-end leading-tight">
              <span className="text-xs font-medium">{user.name}</span>
              <span className="text-[10px] text-muted-foreground">
                {user.email}
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              className="h-8"
              data-testid="logout-button"
            >
              <LogOut className="w-3.5 h-3.5 mr-1.5" />
              Sign out
            </Button>
          </div>
        )}
      </div>
    </header>
  );
}
