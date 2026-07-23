import { useEffect, useMemo, useState, useCallback } from "react";
import { toast } from "sonner";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import dagre from "dagre";
import {
  Boxes,
  Loader2,
  AlertTriangle,
  Package,
  ChevronsUpDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";

const NODE_W = 200;
const NODE_H = 60;

function layout(nodes, edges, direction = "LR") {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, nodesep: 40, ranksep: 80 });
  nodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  return nodes.map((n) => {
    const pos = g.node(n.id);
    return {
      ...n,
      position: { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 },
    };
  });
}

function ModuleNode({ data }) {
  const inCycle = data.inCycle;
  return (
    <div
      className={`px-3 py-2 rounded-md border font-mono text-xs min-w-[160px] transition-colors ${
        inCycle
          ? "border-destructive bg-destructive/10 text-destructive"
          : "border-border/80 bg-secondary/60 hover:border-primary/60"
      }`}
    >
      <Handle
        type="target"
        position={Position.Left}
        style={{ background: "hsl(217 91% 60%)", width: 6, height: 6 }}
      />
      <div className="flex items-center gap-1.5">
        {inCycle ? (
          <AlertTriangle className="w-3 h-3 shrink-0" />
        ) : (
          <Package className="w-3 h-3 shrink-0 text-primary" />
        )}
        <span className="truncate">{data.label}</span>
      </div>
      <div className="mt-1 text-[9px] uppercase tracking-widest text-muted-foreground">
        {data.file_count} files
      </div>
      <Handle
        type="source"
        position={Position.Right}
        style={{ background: "hsl(184 100% 50%)", width: 6, height: 6 }}
      />
    </div>
  );
}

const nodeTypes = { module: ModuleNode };

export default function GraphView({ repo }) {
  const [granularity, setGranularity] = useState("module");
  const [graph, setGraph] = useState(null);
  const [busy, setBusy] = useState(true);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const { data } = await api.get(
        `/repositories/${repo.id}/graph?granularity=${granularity}`,
      );
      setGraph(data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to load graph");
    } finally {
      setBusy(false);
    }
  }, [repo.id, granularity]);

  useEffect(() => {
    load();
  }, [load]);

  const { nodes, edges } = useMemo(() => {
    if (!graph) return { nodes: [], edges: [] };
    const rawNodes = graph.nodes.map((n) => ({
      id: n.id,
      type: "module",
      data: {
        label: n.label || n.id,
        file_count: n.file_count,
        inCycle: n.in_cycle,
      },
      position: { x: 0, y: 0 },
    }));
    const rawEdges = graph.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      animated: e.in_cycle,
      style: {
        stroke: e.in_cycle ? "hsl(0 84% 60%)" : "hsl(217 91% 60% / 0.6)",
        strokeWidth: Math.min(4, 0.5 + e.weight * 0.4),
      },
      label: e.weight > 1 ? `×${e.weight}` : "",
      labelStyle: {
        fill: "hsl(0 0% 64%)",
        fontFamily: "IBM Plex Mono, monospace",
        fontSize: 10,
      },
    }));
    return { nodes: layout(rawNodes, rawEdges), edges: rawEdges };
  }, [graph]);

  if (busy && !graph) {
    return (
      <div className="h-[70vh] grid place-items-center border border-border/60 rounded-md">
        <div className="flex items-center gap-2 text-muted-foreground text-sm">
          <Loader2 className="w-4 h-4 animate-spin" /> Building graph…
        </div>
      </div>
    );
  }

  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="h-[60vh] grid place-items-center border border-dashed border-border rounded-md text-center">
        <div>
          <Boxes className="w-6 h-6 mx-auto text-muted-foreground" />
          <p className="mt-4 text-sm text-muted-foreground">
            Not enough structural information to draw a graph.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="border border-border/60 rounded-md overflow-hidden bg-[#080808]">
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border/60">
        <div className="tiny-label">architecture graph</div>
        <div className="flex-1" />
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground">Granularity</span>
          <Select value={granularity} onValueChange={setGranularity}>
            <SelectTrigger
              className="h-7 w-28 bg-secondary/40 border-border text-xs"
              data-testid="graph-granularity-select"
            >
              <SelectValue />
              <ChevronsUpDown className="w-3 h-3" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="module">Modules</SelectItem>
              <SelectItem value="file">Files</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="ghost" size="sm" onClick={load} className="h-7">
            Refresh
          </Button>
        </div>
      </div>
      <div className="flex items-center gap-4 px-4 py-2 border-b border-border/60 text-xs text-muted-foreground font-mono">
        <span>{graph.stats.node_count} nodes</span>
        <span>{graph.stats.edge_count} edges</span>
        <span
          className={
            graph.stats.cycle_count > 0
              ? "text-destructive"
              : "text-muted-foreground"
          }
        >
          {graph.stats.cycle_count} cycles
        </span>
      </div>
      <div className="h-[68vh]" data-testid="graph-canvas">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.2}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="rgba(255,255,255,0.06)" gap={24} />
          <Controls
            style={{
              background: "rgba(15,15,15,0.9)",
              border: "1px solid hsl(0 0% 15%)",
            }}
          />
          <MiniMap
            pannable
            zoomable
            maskColor="rgba(0,0,0,0.7)"
            style={{ background: "#0b0b0b", border: "1px solid hsl(0 0% 15%)" }}
            nodeColor={(n) => (n.data?.inCycle ? "#ef4444" : "#3b82f6")}
          />
        </ReactFlow>
      </div>
      {graph.external?.length > 0 && (
        <div className="border-t border-border/60 px-4 py-3">
          <div className="tiny-label mb-2">External packages</div>
          <div className="flex flex-wrap gap-1.5">
            {graph.external.map((e) => (
              <span
                key={e.name}
                className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-background/70 border border-border"
              >
                {e.name} <span className="text-muted-foreground">×{e.count}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
