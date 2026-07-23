import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { motion } from "framer-motion";
import {
  Loader2,
  GitBranch,
  FileCode2,
  Search,
  MessageSquare,
  BookOpen,
  Layers,
  Zap,
  Boxes,
  ArrowLeft,
  ExternalLink,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import AppHeader from "@/components/AppHeader";
import FileTree from "@/components/FileTree";
import ChatPanel from "@/components/ChatPanel";
import { api } from "@/lib/api";
import { REPO } from "@/constants/testIds";

const STATUS_LABEL = {
  queued: "Queued",
  cloning: "Cloning repository",
  parsing: "Parsing source",
  indexing: "Indexing symbols",
  ready: "Ready",
  failed: "Failed",
};

export default function RepositoryDetail({ onOpenCommand }) {
  const { repoId } = useParams();
  const navigate = useNavigate();
  const [repo, setRepo] = useState(null);
  const [tab, setTab] = useState("overview");
  const [tree, setTree] = useState(null);
  const [selectedPath, setSelectedPath] = useState(null);
  const [fileContent, setFileContent] = useState(null);
  const [stats, setStats] = useState(null);
  const [docs, setDocs] = useState("");
  const [genDocsBusy, setGenDocsBusy] = useState(false);
  const [searchQ, setSearchQ] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searchBusy, setSearchBusy] = useState(false);

  const loadRepo = async () => {
    try {
      const { data } = await api.get(`/repositories/${repoId}`);
      setRepo(data);
    } catch {
      toast.error("Repository not found");
      navigate("/dashboard");
    }
  };

  useEffect(() => {
    loadRepo();
     
  }, [repoId]);

  // poll while not ready
  useEffect(() => {
    if (!repo) return;
    if (["ready", "failed"].includes(repo.status)) return;
    const t = setInterval(loadRepo, 3000);
    return () => clearInterval(t);
     
  }, [repo?.status]);

  // load tree + stats when ready
  useEffect(() => {
    if (repo?.status !== "ready") return;
    api.get(`/repositories/${repoId}/tree`).then((r) => setTree(r.data)).catch(() => {});
    api.get(`/repositories/${repoId}/stats`).then((r) => setStats(r.data)).catch(() => {});
     
  }, [repo?.status]);

  useEffect(() => {
    if (!selectedPath) return;
    setFileContent(null);
    api
      .get(`/repositories/${repoId}/file`, { params: { path: selectedPath } })
      .then((r) => setFileContent(r.data))
      .catch(() => toast.error("Failed to load file"));
  }, [selectedPath, repoId]);

  const doSearch = async (e) => {
    e?.preventDefault();
    if (!searchQ.trim()) return;
    setSearchBusy(true);
    try {
      const { data } = await api.post(`/repositories/${repoId}/search`, {
        query: searchQ.trim(),
        limit: 20,
      });
      setSearchResults(data.results || []);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Search failed");
    } finally {
      setSearchBusy(false);
    }
  };

  const generateDocs = async () => {
    setGenDocsBusy(true);
    try {
      const { data } = await api.post(`/repositories/${repoId}/docs`);
      setDocs(data.markdown || "");
      toast.success("Documentation generated");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Doc generation failed");
    } finally {
      setGenDocsBusy(false);
    }
  };

  const progressValue = useMemo(() => {
    if (!repo) return 0;
    const map = { queued: 10, cloning: 30, parsing: 60, indexing: 85, ready: 100, failed: 100 };
    return map[repo.status] || 0;
  }, [repo]);

  if (!repo) {
    return (
      <div className="min-h-screen grid place-items-center">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <AppHeader onOpenCommand={onOpenCommand} />

      <main className="mx-auto max-w-[1600px] px-6 py-8" data-testid={REPO.header}>
        <button
          onClick={() => navigate("/dashboard")}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
        >
          <ArrowLeft className="w-3 h-3" /> Back to workspace
        </button>

        <div className="mt-4 flex flex-wrap items-start gap-6 justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-primary" />
              <span className="tiny-label">
                {repo.source === "github" ? "github" : "zip"}
                {repo.framework ? ` · ${repo.framework}` : ""}
              </span>
            </div>
            <h1 className="mt-2 font-display font-black text-4xl tracking-tighter">
              {repo.name}
            </h1>
            {repo.github_url && (
              <a
                href={repo.github_url}
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary font-mono"
              >
                {repo.github_url}
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span
              className={`text-[10px] font-mono uppercase tracking-widest px-2 py-1 rounded-sm ${
                repo.status === "ready"
                  ? "bg-accent/15 text-accent"
                  : repo.status === "failed"
                    ? "bg-destructive/15 text-destructive"
                    : "bg-primary/15 text-primary animate-pulse"
              }`}
              data-testid={REPO.statusBadge}
            >
              {STATUS_LABEL[repo.status] || repo.status}
            </span>
            <Button variant="ghost" size="sm" onClick={loadRepo} className="h-8">
              <RefreshCw className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>

        {repo.status !== "ready" && (
          <div className="mt-8 border border-border/60 rounded-md p-6 bg-secondary/20">
            <div className="flex items-center gap-3">
              <Loader2 className="w-4 h-4 animate-spin text-primary" />
              <div className="tiny-label">{STATUS_LABEL[repo.status]}</div>
            </div>
            <Progress value={progressValue} className="mt-4 h-1.5 bg-secondary" />
            {repo.error && (
              <p className="mt-4 text-sm text-destructive font-mono">{repo.error}</p>
            )}
          </div>
        )}

        {repo.status === "ready" && (
          <>
            {/* stats row */}
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-8 grid grid-cols-2 md:grid-cols-5 gap-3"
            >
              <StatBig icon={FileCode2} label="Files" value={repo.file_count} />
              <StatBig icon={Boxes} label="Functions" value={repo.function_count} />
              <StatBig icon={Layers} label="Classes" value={repo.class_count} />
              <StatBig icon={Zap} label="Routes" value={repo.api_count} />
              <StatBig
                icon={GitBranch}
                label="Languages"
                value={Object.keys(repo.languages || {}).length}
              />
            </motion.div>

            <Tabs value={tab} onValueChange={setTab} className="mt-8">
              <TabsList className="bg-transparent border-b border-border rounded-none h-auto p-0 gap-1 w-full justify-start">
                <TriggerTab value="overview" testid={REPO.tabOverview} icon={Layers}>
                  Overview
                </TriggerTab>
                <TriggerTab value="files" testid={REPO.tabFiles} icon={FileCode2}>
                  Files
                </TriggerTab>
                <TriggerTab value="chat" testid={REPO.tabChat} icon={MessageSquare}>
                  Chat
                </TriggerTab>
                <TriggerTab value="search" testid={REPO.tabSearch} icon={Search}>
                  Search
                </TriggerTab>
                <TriggerTab value="docs" testid={REPO.tabDocs} icon={BookOpen}>
                  Docs
                </TriggerTab>
              </TabsList>

              {/* Overview */}
              <TabsContent value="overview" className="mt-6">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  <div className="border border-border/60 rounded-md p-5">
                    <div className="tiny-label">Languages</div>
                    <ul className="mt-4 space-y-2">
                      {Object.entries(repo.languages || {})
                        .sort((a, b) => b[1] - a[1])
                        .map(([lang, count]) => (
                          <li key={lang} className="flex items-center justify-between text-sm font-mono">
                            <span>{lang}</span>
                            <span className="text-muted-foreground">{count}</span>
                          </li>
                        ))}
                    </ul>
                  </div>
                  <div className="border border-border/60 rounded-md p-5">
                    <div className="tiny-label">Top modules</div>
                    <ul className="mt-4 space-y-2">
                      {(stats?.top_modules || []).map((m) => (
                        <li key={m.name} className="flex items-center justify-between text-sm font-mono">
                          <span className="truncate">{m.name}</span>
                          <span className="text-muted-foreground">{m.count}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="border border-border/60 rounded-md p-5 lg:col-span-1">
                    <div className="tiny-label">Metadata</div>
                    <dl className="mt-4 space-y-2 text-sm">
                      <Row k="Primary language" v={repo.primary_language || "—"} />
                      <Row k="Framework" v={repo.framework || "—"} />
                      <Row k="Packages" v={repo.package_manager || "—"} />
                      <Row
                        k="Total size"
                        v={`${(repo.total_bytes / 1024).toFixed(0)} KB`}
                      />
                    </dl>
                  </div>
                </div>

                <div className="mt-4 border border-border/60 rounded-md p-5">
                  <div className="tiny-label">API routes ({stats?.apis?.length || 0})</div>
                  {stats?.apis?.length ? (
                    <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-2 max-h-96 overflow-y-auto scrollbar-thin">
                      {stats.apis.map((a) => (
                        <div key={a.id} className="flex items-center gap-2 px-3 py-2 rounded-sm border border-border/60 bg-secondary/20 font-mono text-xs">
                          <span className="text-accent">{a.name}</span>
                          <span className="text-muted-foreground ml-auto truncate max-w-[50%]">
                            {a.file_path}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-muted-foreground">
                      No routes detected in this repository.
                    </p>
                  )}
                </div>
              </TabsContent>

              {/* Files */}
              <TabsContent value="files" className="mt-6">
                <div className="grid grid-cols-12 gap-4 min-h-[600px]">
                  <div className="col-span-4 lg:col-span-3 border border-border/60 rounded-md overflow-hidden">
                    <div className="px-3 py-2 border-b border-border/60 tiny-label">
                      File tree
                    </div>
                    <div className="max-h-[70vh] overflow-y-auto scrollbar-thin py-1">
                      <FileTree
                        node={tree}
                        onSelect={setSelectedPath}
                        activePath={selectedPath}
                      />
                    </div>
                  </div>
                  <div
                    className="col-span-8 lg:col-span-9 border border-border/60 rounded-md overflow-hidden bg-[#080808]"
                    data-testid={REPO.fileViewer}
                  >
                    {selectedPath ? (
                      <>
                        <div className="px-4 py-2 border-b border-border/60 flex items-center gap-2 sticky top-0 bg-[#080808]">
                          <FileCode2 className="w-3.5 h-3.5 text-primary" />
                          <span className="font-mono text-xs truncate">{selectedPath}</span>
                          {fileContent && (
                            <span className="ml-auto tiny-label !text-[9px]">
                              {fileContent.language || "text"}
                            </span>
                          )}
                        </div>
                        <pre className="p-4 text-[12px] font-mono leading-relaxed overflow-auto scrollbar-thin max-h-[70vh]">
                          {fileContent ? fileContent.content : (
                            <span className="text-muted-foreground">Loading…</span>
                          )}
                        </pre>
                      </>
                    ) : (
                      <div className="h-full grid place-items-center text-muted-foreground text-sm">
                        Select a file to preview
                      </div>
                    )}
                  </div>
                </div>
              </TabsContent>

              {/* Chat */}
              <TabsContent value="chat" className="mt-6">
                <div className="border border-border/60 rounded-md overflow-hidden h-[75vh]">
                  <ChatPanel repo={repo} />
                </div>
              </TabsContent>

              {/* Search */}
              <TabsContent value="search" className="mt-6">
                <form onSubmit={doSearch} className="flex gap-2">
                  <div className="flex-1 relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                      value={searchQ}
                      onChange={(e) => setSearchQ(e.target.value)}
                      placeholder="Try: 'JWT creation', 'database model', 'payment flow'…"
                      className="h-11 pl-10 bg-secondary/30 border-border font-mono text-sm"
                      data-testid={REPO.searchInput}
                    />
                  </div>
                  <Button
                    type="submit"
                    disabled={searchBusy || !searchQ.trim()}
                    className="h-11 px-5"
                    data-testid={REPO.searchSubmit}
                  >
                    {searchBusy ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : null}
                    Search
                  </Button>
                </form>

                <div className="mt-6 space-y-2">
                  {searchResults.length === 0 && !searchBusy && (
                    <div className="text-sm text-muted-foreground text-center py-16 border border-dashed border-border rounded-md">
                      Enter a query above to find relevant files, functions and routes.
                    </div>
                  )}
                  {searchResults.map((r, i) => (
                    <div
                      key={i}
                      className="border border-border/60 rounded-md p-4 hover:border-white/20 transition-colors"
                      data-testid={REPO.searchResult}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded-sm bg-primary/15 text-primary">
                          {r.kind}
                        </span>
                        <span className="font-mono text-sm text-accent">
                          {r.name || r.path}
                        </span>
                        <span className="ml-auto tiny-label !text-[9px]">
                          score {r.score}
                        </span>
                      </div>
                      <button
                        onClick={() => {
                          setSelectedPath(r.path);
                          setTab("files");
                        }}
                        className="mt-2 text-xs text-muted-foreground hover:text-primary font-mono truncate block w-full text-left"
                      >
                        {r.path}
                        {r.start_line ? `:${r.start_line}` : ""}
                      </button>
                      {r.snippet && (
                        <pre className="mt-3 text-[11px] font-mono bg-[#080808] border border-border/60 rounded-sm p-3 overflow-x-auto scrollbar-thin whitespace-pre-wrap">
                          {r.snippet}
                        </pre>
                      )}
                    </div>
                  ))}
                </div>
              </TabsContent>

              {/* Docs */}
              <TabsContent value="docs" className="mt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="tiny-label">generated documentation</div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Ask Claude Sonnet 4.5 to write a Markdown overview using
                      indexed code as context.
                    </p>
                  </div>
                  <Button
                    onClick={generateDocs}
                    disabled={genDocsBusy}
                    data-testid={REPO.generateDocs}
                  >
                    {genDocsBusy ? (
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <BookOpen className="w-4 h-4 mr-2" />
                    )}
                    Generate docs
                  </Button>
                </div>
                <div className="mt-6 border border-border/60 rounded-md bg-[#080808] p-6 min-h-[400px]">
                  {docs ? (
                    <pre className="text-sm font-mono whitespace-pre-wrap leading-relaxed">
                      {docs}
                    </pre>
                  ) : (
                    <div className="text-sm text-muted-foreground text-center py-20">
                      Click &quot;Generate docs&quot; to produce a README for this repo.
                    </div>
                  )}
                </div>
              </TabsContent>
            </Tabs>
          </>
        )}
      </main>
    </div>
  );
}

function StatBig({ icon: Icon, label, value }) {
  return (
    <div className="border border-border/60 rounded-md p-4 bg-secondary/20">
      <Icon className="w-4 h-4 text-primary" />
      <div className="mt-3 font-display font-black text-3xl tracking-tighter leading-none">
        {value ?? 0}
      </div>
      <div className="tiny-label mt-2">{label}</div>
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="text-muted-foreground text-xs">{k}</dt>
      <dd className="font-mono text-sm truncate">{v}</dd>
    </div>
  );
}

function TriggerTab({ value, testid, icon: Icon, children }) {
  return (
    <TabsTrigger
      value={value}
      data-testid={testid}
      className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-primary text-muted-foreground hover:text-foreground px-4 h-10 gap-2 font-mono text-xs uppercase tracking-widest"
    >
      <Icon className="w-3.5 h-3.5" />
      {children}
    </TabsTrigger>
  );
}
