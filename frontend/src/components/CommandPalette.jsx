import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from "@/components/ui/command";
import { LayoutDashboard, GitBranch, Home, LogOut, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { clearAuth, isAuthenticated } from "@/lib/auth";
import { COMMAND } from "@/constants/testIds";

export default function CommandPalette({ open, setOpen }) {
  const navigate = useNavigate();
  const [repos, setRepos] = useState([]);

  useEffect(() => {
    if (!open || !isAuthenticated()) return;
    api
      .get("/repositories")
      .then((r) => setRepos(r.data || []))
      .catch(() => {});
  }, [open]);

  const go = (path) => {
    setOpen(false);
    navigate(path);
  };

  return (
    <CommandDialog
      open={open}
      onOpenChange={setOpen}
      data-testid={COMMAND.dialog}
    >
      <CommandInput placeholder="Search commands, repositories…" />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Navigate">
          <CommandItem onSelect={() => go("/")}>
            <Home className="w-4 h-4 mr-2" /> Home
          </CommandItem>
          <CommandItem onSelect={() => go("/dashboard")}>
            <LayoutDashboard className="w-4 h-4 mr-2" /> Dashboard
          </CommandItem>
          <CommandItem
            onSelect={() => {
              setOpen(false);
              window.dispatchEvent(new CustomEvent("codeganak:open-import"));
            }}
          >
            <Plus className="w-4 h-4 mr-2" /> Import repository
          </CommandItem>
        </CommandGroup>
        {repos.length > 0 && (
          <CommandGroup heading="Repositories">
            {repos.map((r) => (
              <CommandItem
                key={r.id}
                onSelect={() => go(`/repositories/${r.id}`)}
              >
                <GitBranch className="w-4 h-4 mr-2 text-primary" />
                <span className="truncate">{r.name}</span>
                <span className="ml-auto text-[10px] uppercase tracking-widest text-muted-foreground">
                  {r.status}
                </span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}
        <CommandGroup heading="Session">
          <CommandItem
            onSelect={() => {
              clearAuth();
              go("/login");
            }}
          >
            <LogOut className="w-4 h-4 mr-2" /> Sign out
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
