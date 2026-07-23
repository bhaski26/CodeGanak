import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  ChevronsUpDown,
  Check,
  Plus,
  Settings2,
  Users,
  Sparkles,
} from "lucide-react";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { useWorkspaces } from "@/lib/workspaces";

export default function WorkspaceSwitcher() {
  const navigate = useNavigate();
  const { workspaces, currentId, setCurrent, refresh } = useWorkspaces();
  const [open, setOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (workspaces.length === 0) refresh().catch(() => {});
  }, [refresh, workspaces.length]);

  const current = workspaces.find((w) => w.id === currentId);

  const onCreate = async () => {
    if (!newName.trim()) return;
    setBusy(true);
    try {
      const { data } = await api.post("/workspaces", { name: newName.trim() });
      toast.success(`Workspace "${data.name}" created`);
      await refresh();
      setCurrent(data.id);
      setCreateOpen(false);
      setNewName("");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to create workspace");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            className="flex items-center gap-2 px-3 h-8 rounded-md border border-border bg-secondary/40 hover:bg-secondary hover:border-primary/40 transition-colors text-sm min-w-[190px]"
            data-testid="workspace-switcher-trigger"
          >
            <Users className="w-3.5 h-3.5 text-primary" />
            <span className="truncate flex-1 text-left font-medium">
              {current?.name || "Workspace"}
            </span>
            <span className="tiny-label !text-[9px]">{current?.role || ""}</span>
            <ChevronsUpDown className="w-3 h-3 text-muted-foreground" />
          </button>
        </PopoverTrigger>
        <PopoverContent
          align="start"
          className="w-72 p-1 bg-popover border-border"
        >
          <div className="tiny-label px-3 pt-3 pb-2">workspaces</div>
          <div className="max-h-[300px] overflow-y-auto scrollbar-thin">
            {workspaces.map((w) => (
              <button
                key={w.id}
                onClick={() => {
                  setCurrent(w.id);
                  setOpen(false);
                }}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-sm hover:bg-secondary/60 text-left"
                data-testid={`workspace-option-${w.id}`}
              >
                {w.is_personal ? (
                  <Sparkles className="w-3.5 h-3.5 text-accent shrink-0" />
                ) : (
                  <Users className="w-3.5 h-3.5 text-primary shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <div className="text-sm truncate">{w.name}</div>
                  <div className="tiny-label !text-[9px]">
                    {w.role} · {w.repo_count} repo{w.repo_count === 1 ? "" : "s"} ·{" "}
                    {w.member_count} member{w.member_count === 1 ? "" : "s"}
                  </div>
                </div>
                {w.id === currentId && (
                  <Check className="w-4 h-4 text-primary" />
                )}
              </button>
            ))}
          </div>
          <div className="border-t border-border mt-1 pt-1 flex gap-1 px-1 pb-1">
            <Button
              variant="ghost"
              size="sm"
              className="flex-1 h-8 justify-start"
              onClick={() => {
                setOpen(false);
                setCreateOpen(true);
              }}
              data-testid="workspace-create-button"
            >
              <Plus className="w-3.5 h-3.5 mr-2" /> New workspace
            </Button>
            {current && (
              <Button
                variant="ghost"
                size="sm"
                className="h-8"
                onClick={() => {
                  setOpen(false);
                  navigate(`/workspaces/${current.id}/settings`);
                }}
                data-testid="workspace-settings-button"
              >
                <Settings2 className="w-3.5 h-3.5" />
              </Button>
            )}
          </div>
        </PopoverContent>
      </Popover>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="bg-popover border-border max-w-md">
          <DialogHeader>
            <DialogTitle className="font-display tracking-tight">
              New workspace
            </DialogTitle>
            <DialogDescription>
              Workspaces group repositories and let you invite teammates.
            </DialogDescription>
          </DialogHeader>
          <Input
            placeholder="Workspace name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onCreate()}
            className="h-11 bg-secondary/30 border-border"
            data-testid="workspace-name-input"
          />
          <Button
            onClick={onCreate}
            disabled={busy || !newName.trim()}
            className="w-full h-10"
            data-testid="workspace-create-submit"
          >
            Create
          </Button>
        </DialogContent>
      </Dialog>
    </>
  );
}
