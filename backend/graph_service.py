"""Build architecture / dependency graphs from indexed imports.

Two granularities:
  * `module` graph: nodes are top-level directories (backend/, src/frontend/…)
  * `file`   graph: nodes are individual files

Edges are import relationships. Circular dependencies are flagged
using Tarjan's strongly-connected-components algorithm.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple


def _tarjan_scc(nodes: List[str], edges: Dict[str, Set[str]]) -> List[List[str]]:
    """Return SCCs as list of node lists. Only components of size >= 2 or self-loops matter."""
    index_counter = [0]
    stack: List[str] = []
    on_stack: Set[str] = set()
    indices: Dict[str, int] = {}
    lowlink: Dict[str, int] = {}
    result: List[List[str]] = []

    def _strong(v: str):
        indices[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in edges.get(v, ()):
            if w not in indices:
                _strong(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], indices[w])
        if lowlink[v] == indices[v]:
            scc: List[str] = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                scc.append(w)
                if w == v:
                    break
            result.append(scc)

    import sys
    limit = sys.getrecursionlimit()
    if len(nodes) > limit - 100:
        sys.setrecursionlimit(len(nodes) + 500)

    for v in nodes:
        if v not in indices:
            _strong(v)
    return result


def _module_of(path: str) -> str:
    return path.split("/")[0] if path else path


async def build_graph(repo_id: str, db, granularity: str = "module") -> Dict:
    """Return {nodes, edges, cycles, granularity, stats}."""
    files_cur = db.files.find({"repo_id": repo_id, "is_binary": False}, {"_id": 0})
    files = await files_cur.to_list(20000)
    files_by_path = {f["path"]: f for f in files}

    imports_cur = db.imports.find({"repo_id": repo_id}, {"_id": 0})
    imports = await imports_cur.to_list(50000)

    # Aggregate weights per (source_module -> target_module)
    edges_w: Dict[Tuple[str, str], int] = defaultdict(int)
    node_files: Dict[str, int] = defaultdict(int)
    external_hits: Dict[str, int] = defaultdict(int)

    for f in files:
        node_files[_module_of(f["path"]) if granularity == "module" else f["path"]] += 1

    for imp in imports:
        source = imp["source_path"]
        target = imp.get("target_path")
        if not target:
            # bucket external imports by module string for later
            if imp.get("target_module"):
                external_hits[imp["target_module"]] += 1
            continue
        if granularity == "module":
            src = _module_of(source)
            tgt = _module_of(target)
        else:
            src, tgt = source, target
        if src == tgt:
            continue
        edges_w[(src, tgt)] += 1

    nodes_set: Set[str] = set(node_files.keys())
    for (a, b) in edges_w.keys():
        nodes_set.add(a)
        nodes_set.add(b)

    adjacency: Dict[str, Set[str]] = defaultdict(set)
    for (a, b) in edges_w:
        adjacency[a].add(b)

    sccs = _tarjan_scc(sorted(nodes_set), adjacency)
    cycles = [scc for scc in sccs if len(scc) > 1]
    cycle_nodes = {n for scc in cycles for n in scc}

    # emit
    nodes = [
        {
            "id": n,
            "label": n,
            "file_count": node_files.get(n, 0),
            "in_cycle": n in cycle_nodes,
        }
        for n in sorted(nodes_set)
    ]
    edges = [
        {
            "id": f"{a}->{b}",
            "source": a,
            "target": b,
            "weight": w,
            "in_cycle": a in cycle_nodes and b in cycle_nodes,
        }
        for (a, b), w in edges_w.items()
    ]
    # top external packages (limit)
    top_external = sorted(external_hits.items(), key=lambda kv: kv[1], reverse=True)[:12]

    return {
        "granularity": granularity,
        "nodes": nodes,
        "edges": edges,
        "cycles": cycles,
        "external": [{"name": k, "count": v} for k, v in top_external],
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "cycle_count": len(cycles),
        },
    }
