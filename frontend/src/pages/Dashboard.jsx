import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { motion } from "framer-motion";
import {
  Plus,
  Upload,
  Github,
  GitBranch,
  Loader2,
  Trash2,
  FileCode2,
  Boxes,
  Zap,
  Clock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import AppHeader from "@/components/AppHeader";
import { api } from "@/lib/api";
import { DASHBOARD, IMPORT } from "@/constants/testIds";

const STATUS_META = {
  queued: { label: "Queued", tone: "bg-secondary text-muted-foreground" },
  cloning: { label: "Cloning", tone: "bg-primary/15 text-primary animate-pulse" },
  parsing: { label: "Parsing", tone: "bg-primary/15 text-primary animate-pulse" },
  indexing: { label: "Indexing", tone: "bg-primary/15 text-primary animate-pulse" },
  ready: { label: "Ready", tone: "bg-accent/15 text-accent" },
  failed: { label: "Failed", tone: "bg-destructive/15 text-destructive" },
};

export default function Dashboard({ onOpenCommand }) {
  const [repos, setRepos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [importOpen, setImportOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [githubUrl, setGithubUrl] = useState("");
  const [file, setFile] = useState(null);

  const fetchRepos = useCallback(async () => {
    try {
      const { data } = await api.get("/repositories");
      setRepos(data || []);
    } catch (e) {
      toast.error("Failed to load repositories");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRepos();
    const openHandler = () => setImportOpen(true);
    window.addEventListener("codeganak:open-import", openHandler);
    const interval = setInterval(() => {
      // Poll to reflect background indexing
      api.get("/repositories").then((r) => setRepos(r.data || [])).catch(() => {});
    }, 4000);
    return () => {
      window.removeEventListener("codeganak:open-import", openHandler);
      clearInterval(interval);
    };
  }, [fetchRepos]);

  const importGithub = async () => {
    if (!githubUrl.trim()) return;
    setBusy(true);
    try {
      const { data } = await api.post("/repositories/import-github", {
        github_url: githubUrl.trim(),
      });
      toast.success(`Import queued: ${data.name}`);
      setGithubUrl("");
      setImportOpen(false);
      fetchRepos();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Import failed");
    } finally {
      setBusy(false);
    }
  };

  const uploadZip = async () => {
    if (!file) return;
    setBusy(true);
    const form = new FormData();
    form.append("file", file);
    try {
      const { data } = await api.post("/repositories/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`Uploaded: ${data.name}`);
      setFile(null);
      setImportOpen(false);
      fetchRepos();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const deleteRepo = async (id, name) => {
    if (!confirm(`Delete repository "${name}"?`)) return;
    try {
      await api.delete(`/repositories/${id}`);
      toast.success("Repository deleted");
      fetchRepos();
    } catch {
      toast.error("Delete failed");
    }
  };

  return (
    <div className="min-h-screen">
      <AppHeader onOpenCommand={onOpenCommand} />

      <main
        className="mx-auto max-w-[1600px] px-6 py-10"
        data-testid={DASHBOARD.container}
      >
        <div className="flex flex-wrap items-end gap-6 justify-between mb-10">
          <div>
            <div className="tiny-label text-accent">workspace</div>
            <h1 className="mt-2 font-display font-black text-4xl tracking-tighter">
              Your repositories
            </h1>
            <p className="mt-2 text-sm text-muted-foreground max-w-lg">
              Import a repository to index its architecture, symbols and APIs.
            </p>
          </div>
          <Dialog open={importOpen} onOpenChange={setImportOpen}>
            <DialogTrigger asChild>
              <Button className="h-10" data-testid={DASHBOARD.importGithubButton}>
                <Plus className="w-4 h-4 mr-2" /> Import repository
              </Button>
            </DialogTrigger>
            <DialogContent
              className="bg-popover border-border max-w-lg"
              data-testid={IMPORT.dialog}
            >
              <DialogHeader>
                <DialogTitle className="font-display tracking-tight">
                  Import a repository
                </DialogTitle>
                <DialogDescription>
                  Paste a public GitHub URL, or upload a ZIP archive.
                </DialogDescription>
              </DialogHeader>
              <Tabs defaultValue="github" className="mt-2">
                <TabsList className="bg-secondary/40 border border-border">
                  <TabsTrigger value="github">
                    <Github className="w-3.5 h-3.5 mr-1.5" /> GitHub
                  </TabsTrigger>
                  <TabsTrigger value="zip">
                    <Upload className="w-3.5 h-3.5 mr-1.5" /> ZIP upload
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="github" className="pt-4 space-y-3">
                  <Label className="tiny-label">Repository URL</Label>
                  <Input
                    placeholder="https://github.com/owner/repo"
                    value={githubUrl}
                    onChange={(e) => setGithubUrl(e.target.value)}
                    className="h-11 font-mono text-sm bg-secondary/30 border-border"
                    data-testid={IMPORT.githubUrlInput}
                  />
                  <Button
                    onClick={importGithub}
                    disabled={busy || !githubUrl}
                    className="w-full h-10"
                    data-testid={IMPORT.githubSubmit}
                  >
                    {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Github className="w-4 h-4 mr-2" />}
                    Clone & index
                  </Button>
                  <p className="text-xs text-muted-foreground">
                    Only public repositories are supported for now. Cloned
                    shallowly (depth=1).
                  </p>
                </TabsContent>
                <TabsContent value="zip" className="pt-4 space-y-3">
                  <Label className="tiny-label">ZIP file (max 200 MB)</Label>
                  <Input
                    type="file"
                    accept=".zip"
                    onChange={(e) => setFile(e.target.files?.[0] || null)}
                    className="h-11 file:mr-3 file:bg-secondary file:border-0 file:text-xs file:px-3 file:py-2 file:rounded-sm bg-secondary/30 border-border cursor-pointer"
                    data-testid={IMPORT.zipFileInput}
                  />
                  <Button
                    onClick={uploadZip}
                    disabled={busy || !file}
                    className="w-full h-10"
                    data-testid={IMPORT.zipSubmit}
                  >
                    {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Upload className="w-4 h-4 mr-2" />}
                    Upload & index
                  </Button>
                </TabsContent>
              </Tabs>
            </DialogContent>
          </Dialog>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-40 rounded-md border border-border/60 bg-secondary/20 animate-pulse" />
            ))}
          </div>
        ) : repos.length === 0 ? (
          <div
            className="border border-dashed border-border rounded-md p-16 text-center"
            data-testid={DASHBOARD.emptyState}
          >
            <div className="mx-auto w-12 h-12 rounded-md bg-primary/10 border border-primary/30 grid place-items-center">
              <GitBranch className="w-5 h-5 text-primary" />
            </div>
            <h3 className="mt-6 font-display font-bold text-xl tracking-tight">
              No repositories yet
            </h3>
            <p className="mt-2 text-sm text-muted-foreground max-w-md mx-auto">
              Import your first repository from GitHub or upload a ZIP to
              start exploring.
            </p>
            <Button
              onClick={() => setImportOpen(true)}
              className="mt-6"
              data-testid={DASHBOARD.importZipButton}
            >
              <Plus className="w-4 h-4 mr-2" /> Import repository
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {repos.map((r, i) => {
              const meta = STATUS_META[r.status] || STATUS_META.queued;
              return (
                <motion.div
                  key={r.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.03 }}
                >
                  <Link
                    to={`/repositories/${r.id}`}
                    className="group block border border-border/70 rounded-md p-5 hover:border-white/20 hover:-translate-y-[1px] transition-colors relative overflow-hidden"
                    data-testid={DASHBOARD.repoCard}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <GitBranch className="w-3.5 h-3.5 text-muted-foreground" />
                          <span className="tiny-label !text-[9px] truncate">
                            {r.source === "github" ? "github" : "zip upload"}
                          </span>
                        </div>
                        <h3 className="mt-2 font-display font-bold text-lg tracking-tight truncate">
                          {r.name}
                        </h3>
                        {r.framework && (
                          <div className="mt-1 text-xs text-muted-foreground font-mono">
                            {r.framework}
                            {r.primary_language ? ` · ${r.primary_language}` : ""}
                          </div>
                        )}
                      </div>
                      <button
                        onClick={(e) => {
                          e.preventDefault();
                          deleteRepo(r.id, r.name);
                        }}
                        className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                        data-testid={`repo-delete-${r.id}`}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    <div className="mt-6 grid grid-cols-3 gap-3">
                      <Stat icon={FileCode2} value={r.file_count} label="files" />
                      <Stat icon={Boxes} value={r.function_count} label="fns" />
                      <Stat icon={Zap} value={r.api_count} label="routes" />
                    </div>

                    <div className="mt-5 flex items-center justify-between">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm text-[10px] font-mono uppercase tracking-widest ${meta.tone}`}
                        data-testid="repo-status-badge"
                      >
                        <span className="w-1 h-1 rounded-full bg-current" />
                        {meta.label}
                      </span>
                      <span className="tiny-label !text-[9px]">
                        <Clock className="w-3 h-3 inline mr-1" />
                        {new Date(r.updated_at).toLocaleDateString()}
                      </span>
                    </div>
                    {r.error && (
                      <p className="mt-3 text-[11px] text-destructive/90 font-mono line-clamp-2">
                        {r.error}
                      </p>
                    )}
                  </Link>
                </motion.div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}

function Stat({ icon: Icon, value, label }) {
  return (
    <div className="border border-border/60 rounded-sm p-2 bg-secondary/20">
      <Icon className="w-3.5 h-3.5 text-primary" />
      <div className="font-display font-bold text-xl leading-none mt-2 tracking-tight">
        {value ?? 0}
      </div>
      <div className="tiny-label !text-[8px] mt-1">{label}</div>
    </div>
  );
}
