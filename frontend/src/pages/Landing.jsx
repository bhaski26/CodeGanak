import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowRight,
  GitBranch,
  MessageSquare,
  Search,
  FileCode2,
  Boxes,
  BookOpen,
  Sparkles,
  Terminal,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { LANDING } from "@/constants/testIds";

const features = [
  {
    icon: MessageSquare,
    title: "Repo-aware chat",
    body: "Ask questions and get answers grounded in your actual files, with precise citations.",
  },
  {
    icon: Search,
    title: "Semantic search",
    body: "Search by intent (\u201cwhere is JWT created?\u201d) — not just filenames.",
  },
  {
    icon: FileCode2,
    title: "Symbolic parsing",
    body: "Extract classes, functions, routes and models across many languages.",
  },
  {
    icon: Boxes,
    title: "Architecture insight",
    body: "Detect frameworks, packages and dominant modules the moment your repo lands.",
  },
  {
    icon: BookOpen,
    title: "Docs generation",
    body: "Turn a raw codebase into a clean README with a single click.",
  },
  {
    icon: Sparkles,
    title: "Zero setup",
    body: "Drop a ZIP or paste a GitHub URL. Ready in seconds.",
  },
];

export default function Landing() {
  return (
    <div className="relative min-h-screen">
      {/* nav */}
      <nav className="sticky top-0 z-40 glass border-b border-border/50">
        <div className="mx-auto max-w-7xl h-14 px-6 flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-sm bg-primary/15 border border-primary/40 grid place-items-center">
              <Terminal className="w-4 h-4 text-primary" strokeWidth={2.4} />
            </div>
            <span className="font-display font-black text-[15px] tracking-tighter">
              CodeGanak
            </span>
          </div>
          <div className="flex-1" />
          <Link to="/login">
            <Button
              variant="ghost"
              size="sm"
              className="h-8"
              data-testid={LANDING.ctaLogin}
            >
              Sign in
            </Button>
          </Link>
          <Link to="/register">
            <Button size="sm" className="h-8">
              Start free <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          </Link>
        </div>
      </nav>

      {/* hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 grid-bg opacity-70 [mask-image:radial-gradient(ellipse_at_center,black,transparent_70%)]" />
        <div className="relative mx-auto max-w-7xl px-6 pt-24 pb-32">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            className="max-w-3xl"
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-secondary/40 px-3 py-1 text-xs font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
              <span className="tracking-widest uppercase text-muted-foreground text-[10px]">
                v0.1 · early access
              </span>
            </div>
            <h1
              data-testid={LANDING.heroTitle}
              className="mt-6 font-display font-black text-5xl sm:text-6xl lg:text-7xl tracking-tighter leading-[1.02]"
            >
              Pair with an engineer
              <br />
              <span className="text-primary">who read your entire repo.</span>
            </h1>
            <p className="mt-6 text-lg text-muted-foreground max-w-2xl leading-relaxed">
              CodeGanak ingests your repository, builds a semantic index of
              every file, function and route, then lets you chat, search and
              document it — like onboarding to a codebase in minutes, not
              weeks.
            </p>
            <div className="mt-10 flex flex-wrap gap-3">
              <Link to="/register">
                <Button
                  size="lg"
                  className="h-11 px-6"
                  data-testid={LANDING.ctaGetStarted}
                >
                  Get started
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
              <Link to="/login">
                <Button
                  size="lg"
                  variant="outline"
                  className="h-11 px-6 border-border bg-secondary/30 hover:bg-secondary"
                >
                  I have an account
                </Button>
              </Link>
            </div>

            <div className="mt-14 grid grid-cols-3 max-w-lg gap-6">
              {[
                ["23", "languages parsed"],
                ["4.5", "Claude Sonnet model"],
                ["0", "seconds of setup"],
              ].map(([v, l]) => (
                <div key={l}>
                  <div className="font-display text-3xl font-black tracking-tighter">
                    {v}
                  </div>
                  <div className="tiny-label mt-1">{l}</div>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* features */}
      <section className="relative border-t border-border/60">
        <div className="mx-auto max-w-7xl px-6 py-24">
          <div className="max-w-2xl">
            <div className="tiny-label text-accent">what you get</div>
            <h2 className="mt-3 font-display font-bold text-3xl sm:text-4xl tracking-tight">
              Six ways to understand a codebase, fast.
            </h2>
          </div>
          <div className="mt-12 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-border/70 border border-border/70 rounded-md overflow-hidden">
            {features.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 8 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="bg-background p-8 hover:bg-secondary/30 transition-colors relative"
              >
                <f.icon className="w-5 h-5 text-primary" />
                <h3 className="mt-6 font-display font-bold text-lg tracking-tight">
                  {f.title}
                </h3>
                <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                  {f.body}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* preview */}
      <section className="relative border-t border-border/60">
        <div className="mx-auto max-w-7xl px-6 py-24">
          <div className="grid lg:grid-cols-5 gap-8 items-center">
            <div className="lg:col-span-2">
              <div className="tiny-label text-accent">under the hood</div>
              <h2 className="mt-3 font-display font-bold text-3xl sm:text-4xl tracking-tight">
                Grounded in your code. Nothing invented.
              </h2>
              <p className="mt-4 text-muted-foreground leading-relaxed">
                Every answer streams from Claude Sonnet 4.5, but only after
                retrieving the exact functions, classes and routes matched by
                a BM25 relevance index. You always see which files the answer
                came from.
              </p>
              <ul className="mt-6 space-y-2 text-sm">
                {[
                  "JWT + bcrypt authentication",
                  "In-memory BM25 semantic retrieval",
                  "Python AST + multi-language regex parser",
                  "SSE streaming for zero-latency answers",
                ].map((t) => (
                  <li key={t} className="flex items-center gap-2">
                    <GitBranch className="w-3.5 h-3.5 text-accent" />
                    <span>{t}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="lg:col-span-3">
              <div className="relative rounded-md border border-border/60 bg-[#080808] overflow-hidden">
                <div className="flex items-center gap-2 px-4 py-2 border-b border-border/60">
                  <div className="flex gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-destructive/70" />
                    <span className="w-2.5 h-2.5 rounded-full bg-yellow-500/70" />
                    <span className="w-2.5 h-2.5 rounded-full bg-accent/70" />
                  </div>
                  <span className="ml-3 tiny-label !text-[9px]">
                    codeganak › chat
                  </span>
                </div>
                <pre className="p-6 text-[13px] font-mono leading-relaxed overflow-x-auto scrollbar-thin">
{`> where is JWT created?

I found the token-creation logic in \`backend/auth.py\`:

\`\`\`python
def create_access_token(user_id, email):
    expire = datetime.now(timezone.utc) + timedelta(...)
    payload = {"sub": user_id, "email": email, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
\`\`\`

It is called from the /auth/login and /auth/register
endpoints in \`backend/server.py\`.`}
                </pre>
              </div>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-border/60">
        <div className="mx-auto max-w-7xl px-6 py-8 flex flex-wrap gap-4 items-center text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded-sm bg-primary/15 border border-primary/40 grid place-items-center">
              <Terminal className="w-3 h-3 text-primary" strokeWidth={2.4} />
            </div>
            <span className="font-display font-bold">CodeGanak</span>
          </div>
          <span className="tiny-label !text-[9px]">
            understand · visualize · engineer
          </span>
          <div className="flex-1" />
          <span className="text-xs">
            © {new Date().getFullYear()} CodeGanak
          </span>
        </div>
      </footer>
    </div>
  );
}
