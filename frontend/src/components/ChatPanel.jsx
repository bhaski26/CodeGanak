import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Send, Loader2, MessageSquare, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, streamChat } from "@/lib/api";
import { REPO } from "@/constants/testIds";

const SUGGESTIONS = [
  "Explain the authentication flow",
  "Where is JWT created?",
  "List all API endpoints",
  "What is the project architecture?",
  "Which files interact with the database?",
];

export default function ChatPanel({ repo }) {
  const [messages, setMessages] = useState([]);
  const [pending, setPending] = useState(null); // { content, citations }
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    api
      .get(`/repositories/${repo.id}/chat/history`)
      .then((r) => setMessages(r.data || []))
      .catch(() => {});
  }, [repo.id]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, pending]);

  const send = async (text) => {
    const trimmed = (text ?? input).trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setInput("");
    const userMsg = { role: "user", content: trimmed, created_at: new Date().toISOString() };
    setMessages((m) => [...m, userMsg]);
    setPending({ content: "", citations: [] });

    try {
      let buf = "";
      let citations = [];
      for await (const ev of streamChat(repo.id, trimmed)) {
        if (ev.type === "citations") {
          citations = ev.data || [];
          setPending((p) => ({ ...(p || {}), citations }));
        } else if (ev.type === "delta") {
          buf += typeof ev.data === "string" ? ev.data : "";
          setPending((p) => ({ ...(p || {}), content: buf }));
        } else if (ev.type === "error") {
          throw new Error(typeof ev.data === "string" ? ev.data : "stream error");
        } else if (ev.type === "done") {
          break;
        }
      }
      const finalMsg = {
        role: "assistant",
        content: buf,
        citations,
        created_at: new Date().toISOString(),
      };
      setMessages((m) => [...m, finalMsg]);
      setPending(null);
    } catch (err) {
      toast.error(err?.message || "Chat failed");
      setPending(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto scrollbar-thin px-6 py-6 space-y-6"
      >
        {messages.length === 0 && !pending && (
          <div className="max-w-2xl mx-auto text-center py-16">
            <div className="w-12 h-12 mx-auto rounded-md bg-primary/10 border border-primary/30 grid place-items-center">
              <MessageSquare className="w-5 h-5 text-primary" />
            </div>
            <h3 className="mt-6 font-display font-bold text-2xl tracking-tight">
              Ask about {repo.name}
            </h3>
            <p className="mt-2 text-sm text-muted-foreground">
              CodeGanak indexed this repo. Answers cite real files.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="px-3 py-1.5 rounded-full text-xs border border-border bg-secondary/30 hover:bg-secondary hover:border-primary/40 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <MessageBubble key={i} msg={m} />
        ))}
        {pending && (
          <MessageBubble
            msg={{ role: "assistant", content: pending.content, citations: pending.citations }}
            streaming
          />
        )}
      </div>

      <div className="border-t border-border/60 px-6 py-4 glass">
        <div className="flex items-center gap-2 max-w-4xl mx-auto">
          <div className="flex-1 relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder="Ask about this repository…"
              rows={1}
              className="w-full resize-none rounded-md border border-border bg-secondary/30 px-4 py-3 pr-12 text-sm outline-none focus:border-primary/60 focus:ring-2 focus:ring-primary/20 transition-colors"
              data-testid={REPO.chatInput}
            />
            <Sparkles className="absolute right-3 top-3.5 w-4 h-4 text-muted-foreground/50" />
          </div>
          <Button
            onClick={() => send()}
            disabled={busy || !input.trim()}
            className="h-11 w-11 p-0"
            data-testid={REPO.chatSend}
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </Button>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ msg, streaming }) {
  const isUser = msg.role === "user";
  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
      data-testid={REPO.chatMessage}
    >
      <div
        className={`max-w-[80%] rounded-md px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-secondary/40 border border-border/60 border-l-2 border-l-accent"
        }`}
      >
        {msg.content ? (
          <div className="prose-invert whitespace-pre-wrap">
            {renderMarkdownLite(msg.content)}
          </div>
        ) : streaming ? (
          <div className="flex items-center gap-2 text-muted-foreground text-xs">
            <Loader2 className="w-3 h-3 animate-spin" /> Thinking…
          </div>
        ) : null}

        {!isUser && msg.citations?.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border/60">
            <div className="tiny-label !text-[9px] mb-2">Cited files</div>
            <div className="flex flex-wrap gap-1.5">
              {msg.citations.map((c, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-sm bg-background/60 border border-border"
                  title={`${c.path}:${c.start_line}-${c.end_line}`}
                >
                  {c.path}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/** Extremely small markdown renderer: code fences + inline code. */
function renderMarkdownLite(text) {
  const parts = [];
  const codeFence = /```(\w+)?\n([\s\S]*?)```/g;
  let last = 0;
  let m;
  let idx = 0;
  while ((m = codeFence.exec(text)) !== null) {
    if (m.index > last) {
      parts.push(renderInline(text.slice(last, m.index), `t-${idx++}`));
    }
    parts.push(
      <pre
        key={`c-${idx++}`}
        className="my-2 bg-[#080808] border border-border/60 rounded-sm p-3 text-[12px] font-mono overflow-x-auto scrollbar-thin"
      >
        <code>{m[2]}</code>
      </pre>,
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) {
    parts.push(renderInline(text.slice(last), `t-${idx++}`));
  }
  return parts;
}

function renderInline(text, key) {
  const nodes = [];
  const inline = /`([^`]+)`/g;
  let last = 0;
  let m;
  let i = 0;
  while ((m = inline.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    nodes.push(
      <code
        key={`${key}-i-${i++}`}
        className="px-1 py-0.5 bg-background/60 border border-border/60 rounded-sm font-mono text-[12px] text-accent"
      >
        {m[1]}
      </code>,
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return <span key={key}>{nodes}</span>;
}
