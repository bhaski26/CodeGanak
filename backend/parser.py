"""Lightweight multi-language code parser.

Instead of shipping heavy tree-sitter binaries, we use language-aware
regex patterns plus Python's built-in `ast` to extract symbols reliably
from the most common source languages. Additional languages can be
plugged in by adding an entry to LANG_PATTERNS.
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple

EXT_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".kt": "kotlin",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".m": "objectivec",
    ".scala": "scala",
    ".sh": "shell",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".vue": "vue",
    ".svelte": "svelte",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".json": "json",
    ".md": "markdown",
    ".toml": "toml",
}

# Directories & files we deliberately skip during indexing.
SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", ".next", "out",
    "__pycache__", ".venv", "venv", "env", ".idea", ".vscode",
    "coverage", ".cache", ".turbo", ".yarn", "vendor", "target",
    ".mypy_cache", ".pytest_cache", ".gradle", "bin", "obj",
}

SKIP_FILE_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".pdf", ".zip", ".gz", ".tar", ".7z", ".rar", ".woff", ".woff2",
    ".ttf", ".otf", ".mp4", ".mp3", ".mov", ".class", ".pyc",
    ".so", ".dll", ".exe", ".bin", ".lock",
}

MAX_FILE_BYTES = 400_000  # skip anything bigger than 400KB


def detect_language(path: str) -> Optional[str]:
    ext = os.path.splitext(path)[1].lower()
    return EXT_LANG.get(ext)


def is_binary_bytes(sample: bytes) -> bool:
    if b"\0" in sample:
        return True
    # Very rough heuristic: if too many non-printable bytes, treat as binary.
    text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
    return bool(sample.translate(None, text_chars))


# ------------------ Symbol extraction ------------------

_PY_ROUTE_DECORATORS = re.compile(
    r"@(?:app|router|api_router|blueprint|bp|api)\.(get|post|put|delete|patch|route)\s*\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


def extract_python_symbols(source: str, file_path: str) -> List[Dict]:
    symbols: List[Dict] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return symbols

    lines = source.splitlines()

    def snippet(start: int, end: int) -> str:
        s = max(0, start - 1)
        e = min(len(lines), end)
        return "\n".join(lines[s:e])[:1200]

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            symbols.append({
                "kind": "function",
                "name": node.name,
                "signature": f"def {node.name}(...)",
                "start_line": node.lineno,
                "end_line": end,
                "snippet": snippet(node.lineno, end),
            })
            # Route detection via decorators
            for dec in node.decorator_list:
                try:
                    dec_src = ast.unparse(dec) if hasattr(ast, "unparse") else ""
                except Exception:
                    dec_src = ""
                m = _PY_ROUTE_DECORATORS.search("@" + dec_src)
                if m:
                    symbols.append({
                        "kind": "route",
                        "name": f"{m.group(1).upper()} {m.group(2)}",
                        "signature": f"{m.group(1).upper()} {m.group(2)} -> {node.name}",
                        "start_line": node.lineno,
                        "end_line": end,
                        "snippet": snippet(node.lineno, end),
                    })
        elif isinstance(node, ast.ClassDef):
            end = getattr(node, "end_lineno", node.lineno)
            symbols.append({
                "kind": "class",
                "name": node.name,
                "signature": f"class {node.name}",
                "start_line": node.lineno,
                "end_line": end,
                "snippet": snippet(node.lineno, end),
            })
    return symbols


# Regex-based extractors ----------------------------------------------------

_JS_FUNC_RE = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(",
    re.MULTILINE,
)
_JS_ARROW_RE = re.compile(
    r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(?[^=]*=>",
    re.MULTILINE,
)
_JS_CLASS_RE = re.compile(
    r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)", re.MULTILINE
)
_JS_INTERFACE_RE = re.compile(
    r"^\s*(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)", re.MULTILINE
)
_JS_ROUTE_RE = re.compile(
    r"(?:app|router|api|route)\.(get|post|put|delete|patch)\s*\(\s*['\"`]([^'\"`]+)['\"`]",
    re.IGNORECASE,
)

_JAVA_METHOD_RE = re.compile(
    r"^\s*(?:public|private|protected|static|final|synchronized|abstract|\s)+[\w<>\[\]]+\s+([A-Za-z_][\w]*)\s*\([^)]*\)\s*(?:throws[^{]+)?\{",
    re.MULTILINE,
)
_JAVA_CLASS_RE = re.compile(
    r"^\s*(?:public|private|protected|final|abstract|static|\s)*(?:class|interface|enum)\s+([A-Za-z_][\w]*)",
    re.MULTILINE,
)

_GO_FUNC_RE = re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_][\w]*)\s*\(", re.MULTILINE)
_GO_TYPE_RE = re.compile(r"^\s*type\s+([A-Za-z_][\w]*)\s+(?:struct|interface)", re.MULTILINE)

_RB_METHOD_RE = re.compile(r"^\s*def\s+([A-Za-z_][\w!?]*)", re.MULTILINE)
_RB_CLASS_RE = re.compile(r"^\s*class\s+([A-Za-z_][\w:]*)", re.MULTILINE)


def _line_of(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _snippet_around(source: str, line: int, window: int = 20) -> str:
    lines = source.splitlines()
    s = max(0, line - 1)
    e = min(len(lines), line - 1 + window)
    return "\n".join(lines[s:e])[:1200]


def _extract_regex_symbols(source: str, patterns: List[Tuple[str, re.Pattern]]) -> List[Dict]:
    out: List[Dict] = []
    for kind, pattern in patterns:
        for m in pattern.finditer(source):
            name = m.group(1) if kind != "route" else f"{m.group(1).upper()} {m.group(2)}"
            line = _line_of(source, m.start())
            out.append({
                "kind": kind,
                "name": name,
                "signature": name,
                "start_line": line,
                "end_line": line,
                "snippet": _snippet_around(source, line),
            })
    return out


def extract_symbols(source: str, language: str, file_path: str) -> List[Dict]:
    if language == "python":
        return extract_python_symbols(source, file_path)
    if language in ("javascript", "typescript"):
        patterns = [
            ("function", _JS_FUNC_RE),
            ("function", _JS_ARROW_RE),
            ("class", _JS_CLASS_RE),
            ("interface", _JS_INTERFACE_RE),
            ("route", _JS_ROUTE_RE),
        ]
        return _extract_regex_symbols(source, patterns)
    if language == "java" or language == "kotlin":
        patterns = [("class", _JAVA_CLASS_RE), ("method", _JAVA_METHOD_RE)]
        return _extract_regex_symbols(source, patterns)
    if language == "go":
        patterns = [("function", _GO_FUNC_RE), ("class", _GO_TYPE_RE)]
        return _extract_regex_symbols(source, patterns)
    if language == "ruby":
        patterns = [("class", _RB_CLASS_RE), ("method", _RB_METHOD_RE)]
        return _extract_regex_symbols(source, patterns)
    return []


# ------------------ Repo walker ------------------

def walk_repository(root: Path) -> List[Path]:
    """Yield all files worth indexing under `root`."""
    result: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # in-place filter to skip heavy dirs
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            if ext in SKIP_FILE_EXT:
                continue
            fp = Path(dirpath) / f
            try:
                if fp.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            result.append(fp)
    return result


def read_text(path: Path) -> Optional[str]:
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        if is_binary_bytes(data[:2048]):
            return None
        return data.decode("utf-8", errors="ignore")
    except OSError:
        return None


# ------------------ Framework detection ------------------

def detect_framework(root: Path, languages: Dict[str, int]) -> Tuple[Optional[str], Optional[str]]:
    """Return (framework, package_manager)."""
    framework = None
    pm = None
    files = {p.name for p in root.iterdir() if p.is_file()}
    if "package.json" in files:
        pm = "npm/yarn"
        try:
            import json
            pkg = json.loads((root / "package.json").read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "next" in deps:
                framework = "Next.js"
            elif "react" in deps:
                framework = "React"
            elif "vue" in deps:
                framework = "Vue"
            elif "@angular/core" in deps:
                framework = "Angular"
            elif "svelte" in deps:
                framework = "Svelte"
            elif "express" in deps:
                framework = "Express"
            elif "@nestjs/core" in deps:
                framework = "NestJS"
        except Exception:
            pass
    if "requirements.txt" in files or "pyproject.toml" in files or "Pipfile" in files:
        pm = pm or "pip"
        try:
            text = ""
            for cand in ("requirements.txt", "pyproject.toml", "Pipfile"):
                p = root / cand
                if p.exists():
                    text += p.read_text(errors="ignore").lower()
            if "fastapi" in text:
                framework = framework or "FastAPI"
            elif "django" in text:
                framework = framework or "Django"
            elif "flask" in text:
                framework = framework or "Flask"
        except Exception:
            pass
    if "go.mod" in files:
        pm = pm or "go modules"
        framework = framework or "Go"
    if "Cargo.toml" in files:
        pm = pm or "cargo"
        framework = framework or "Rust"
    if "Gemfile" in files:
        pm = pm or "bundler"
        framework = framework or "Ruby"
    if "pom.xml" in files or "build.gradle" in files:
        pm = pm or "maven/gradle"
        framework = framework or "Java"

    # fall back to primary language when nothing matched
    if not framework and languages:
        top = max(languages.items(), key=lambda kv: kv[1])[0]
        framework = top.capitalize()
    return framework, pm


# ------------------ Import extraction ------------------

_PY_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([\w\.]+)\s+import\s+.+|import\s+([\w\.]+))",
    re.MULTILINE,
)
_JS_IMPORT_RE = re.compile(
    r"""(?:^|\s)import\s+(?:[^'"]*from\s+)?['"]([^'"]+)['"]""",
    re.MULTILINE,
)
_JS_REQUIRE_RE = re.compile(
    r"""require\(\s*['"]([^'"]+)['"]\s*\)""",
    re.MULTILINE,
)
_JAVA_IMPORT_RE = re.compile(r"^\s*import\s+([\w\.\*]+)\s*;", re.MULTILINE)
_GO_IMPORT_RE = re.compile(r"""import\s+(?:\(\s*([\s\S]*?)\s*\)|"([^"]+)")""", re.MULTILINE)
_RB_REQUIRE_RE = re.compile(r"""^\s*require(?:_relative)?\s+['"]([^'"]+)['"]""", re.MULTILINE)


def extract_imports(source: str, language: str) -> List[str]:
    """Return raw module strings referenced by import statements."""
    out: List[str] = []
    if not source:
        return out
    if language == "python":
        for m in _PY_IMPORT_RE.finditer(source):
            mod = m.group(1) or m.group(2)
            if mod:
                out.append(mod)
    elif language in ("javascript", "typescript"):
        for m in _JS_IMPORT_RE.finditer(source):
            out.append(m.group(1))
        for m in _JS_REQUIRE_RE.finditer(source):
            out.append(m.group(1))
    elif language in ("java", "kotlin"):
        for m in _JAVA_IMPORT_RE.finditer(source):
            out.append(m.group(1))
    elif language == "go":
        for m in _GO_IMPORT_RE.finditer(source):
            block = m.group(1)
            single = m.group(2)
            if single:
                out.append(single)
            elif block:
                for line in block.splitlines():
                    line = line.strip().strip('"')
                    if line and not line.startswith("//"):
                        out.append(line.split()[-1].strip('"'))
    elif language == "ruby":
        for m in _RB_REQUIRE_RE.finditer(source):
            out.append(m.group(1))
    # dedupe preserving order
    seen = set()
    result = []
    for m in out:
        if m and m not in seen:
            seen.add(m)
            result.append(m)
    return result


def resolve_import(source_rel_path: str, module: str, language: str, all_paths: set) -> Optional[str]:
    """Best-effort mapping of a module string to a file path inside the repo."""
    if not module:
        return None
    src_dir = os.path.dirname(source_rel_path)

    def _try(candidate: str) -> Optional[str]:
        candidate = candidate.replace("\\", "/").lstrip("./")
        # normalize
        if candidate in all_paths:
            return candidate
        # with extensions
        for ext in (".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
            p = candidate + ext
            if p in all_paths:
                return p
            p = f"{candidate}/index{ext}"
            if p in all_paths:
                return p
        return None

    if language in ("javascript", "typescript"):
        # relative imports only resolve to repo paths
        if module.startswith("."):
            rel = os.path.normpath(os.path.join(src_dir, module))
            return _try(rel.replace(os.sep, "/"))
        return None

    if language == "python":
        # relative "from . import x" -> src_dir; else map dots to slashes
        if module.startswith("."):
            depth = len(module) - len(module.lstrip("."))
            base = src_dir
            for _ in range(depth - 1):
                base = os.path.dirname(base)
            rest = module.lstrip(".").replace(".", "/")
            rel = os.path.join(base, rest) if rest else base
            return _try(rel.replace(os.sep, "/"))
        rel = module.replace(".", "/")
        return _try(rel)

    if language in ("java", "kotlin"):
        rel = module.replace(".", "/").rstrip("*/")
        return _try(rel + ".java") or _try(rel + ".kt") or _try(rel)

    return None
