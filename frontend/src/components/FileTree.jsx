import { useMemo, useState } from "react";
import {
  ChevronRight,
  ChevronDown,
  FileCode2,
  Folder,
  FolderOpen,
} from "lucide-react";
import { REPO } from "@/constants/testIds";

/**
 * Flatten the tree into a list of visible rows based on the open-set.
 * Iterative — avoids recursive JSX which some Babel plugins choke on.
 */
function flatten(root, openSet) {
  const rows = [];
  if (!root || !root.children) return rows;
  const stack = [];
  for (let i = root.children.length - 1; i >= 0; i--) {
    stack.push({ node: root.children[i], depth: 0 });
  }
  while (stack.length) {
    const { node, depth } = stack.pop();
    rows.push({ node, depth });
    if (node.type === "dir" && openSet.has(node.path) && node.children) {
      for (let i = node.children.length - 1; i >= 0; i--) {
        stack.push({ node: node.children[i], depth: depth + 1 });
      }
    }
  }
  return rows;
}

export default function FileTree({ node, onSelect, activePath }) {
  const [openSet, setOpenSet] = useState(() => {
    const s = new Set();
    if (node && node.children) {
      for (const c of node.children) if (c.type === "dir") s.add(c.path);
    }
    return s;
  });

  const rows = useMemo(() => flatten(node, openSet), [node, openSet]);

  const toggle = (path) => {
    setOpenSet((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  if (!node) return null;

  return (
    <div className="text-sm">
      {rows.map(({ node: n, depth }) => {
        const isDir = n.type === "dir";
        const isOpen = openSet.has(n.path);
        const active = activePath === n.path;
        const paddingLeft = `${depth * 12 + 8}px`;

        if (isDir) {
          return (
            <button
              key={n.path}
              onClick={() => toggle(n.path)}
              style={{ paddingLeft }}
              className="w-full flex items-center gap-1.5 py-1 hover:bg-secondary/40 text-left font-mono text-[13px]"
            >
              {isOpen ? (
                <ChevronDown className="w-3 h-3 text-muted-foreground" />
              ) : (
                <ChevronRight className="w-3 h-3 text-muted-foreground" />
              )}
              {isOpen ? (
                <FolderOpen className="w-3.5 h-3.5 text-primary/80" />
              ) : (
                <Folder className="w-3.5 h-3.5 text-primary/80" />
              )}
              <span className="truncate">{n.name}</span>
            </button>
          );
        }

        return (
          <button
            key={n.path}
            onClick={() => onSelect?.(n.path)}
            style={{ paddingLeft }}
            className={`w-full flex items-center gap-1.5 py-1 text-left font-mono text-[13px] transition-colors ${
              active
                ? "bg-primary/15 text-primary border-l border-primary"
                : "hover:bg-secondary/40"
            }`}
            data-testid={REPO.fileTreeNode}
          >
            <span className="w-3" />
            <FileCode2 className="w-3.5 h-3.5 text-muted-foreground" />
            <span className="truncate">{n.name}</span>
          </button>
        );
      })}
    </div>
  );
}
