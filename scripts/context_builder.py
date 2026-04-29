"""
context_builder.py — Assembles a rich, token-efficient codebase snapshot for Claude.

Strategy:
  1. Fetch full Git tree (all paths + sizes) in a single API call.
  2. Filter out non-source artefacts (build outputs, binaries, IDE files).
  3. Score each file by relevance to the issue title/body using keyword matching.
  4. Prioritise Kotlin/Compose source, then XML resources, then config.
  5. Fetch file contents (base64 → utf-8) and assemble into a structured context string.
  6. Hard-cap at MAX_TOTAL_CHARS to stay within Claude's context window.
"""

import base64
import re
import requests
from typing import Optional


# ── Limits ────────────────────────────────────────────────────────────────────
MAX_FILE_BYTES  = 60_000     # ~15k tokens per file
MAX_TOTAL_CHARS = 160_000    # ~130k tokens total (leaves room for system + response)
TREE_LINES_MAX  = 300        # lines in the ASCII tree shown to Claude

# ── Skip lists ───────────────────────────────────────────────────────────────
SKIP_EXTENSIONS = frozenset({
    ".class", ".dex", ".jar", ".aar", ".apk", ".so",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg",
    ".ttf", ".otf", ".woff", ".woff2",
    ".mp3", ".mp4", ".wav", ".ogg",
    ".pdf", ".zip", ".gz", ".tar", ".keystore",
    ".bin", ".dat",
})

SKIP_DIR_SEGMENTS = frozenset({
    "build", ".gradle", ".idea", ".git", "captures",
    "intermediates", "generated", "tmp", "__pycache__",
    "node_modules", ".DS_Store",
})

# ── Priority tiers (higher = fetched first) ──────────────────────────────────
TIER = [
    # Tier 5 — core Compose/Kotlin source
    (5, re.compile(r"app/src/main/java/.+\.kt$")),
    (5, re.compile(r"app/src/main/kotlin/.+\.kt$")),
    # Tier 4 — tests
    (4, re.compile(r"app/src/test/.+\.kt$")),
    (4, re.compile(r"app/src/androidTest/.+\.kt$")),
    # Tier 3 — resources & manifest
    (3, re.compile(r"app/src/main/AndroidManifest\.xml$")),
    (3, re.compile(r"app/src/main/res/.+\.xml$")),
    # Tier 2 — build config
    (2, re.compile(r"(app/)?build\.gradle(\.kts)?$")),
    (2, re.compile(r"settings\.gradle(\.kts)?$")),
    (2, re.compile(r"gradle\.properties$")),
    (2, re.compile(r"libs\.versions\.toml$")),
    # Tier 1 — everything else source-ish
    (1, re.compile(r"\.(kt|xml|json|yaml|yml|toml|properties)$")),
]


def _tier(path: str) -> int:
    for score, pattern in TIER:
        if pattern.search(path):
            return score
    return 0


def _relevance(path: str, keywords: list[str]) -> int:
    """Bonus score based on how many issue keywords appear in the file path."""
    path_lower = path.lower()
    return sum(1 for kw in keywords if kw in path_lower)


def _extract_keywords(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    stop = {"with", "that", "this", "from", "have", "will", "when", "what",
            "should", "would", "could", "also", "than", "then", "into", "some"}
    seen, out = set(), []
    for w in words:
        if w not in stop and w not in seen:
            seen.add(w)
            out.append(w)
    return out[:40]


def _lang_fence(path: str) -> str:
    ext_map = {".kt": "kotlin", ".xml": "xml", ".gradle": "groovy",
               ".kts": "kotlin", ".toml": "toml", ".json": "json",
               ".yaml": "yaml", ".yml": "yaml", ".properties": "properties"}
    ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
    return ext_map.get(ext, "")


class ContextBuilder:
    def __init__(self, token: str, repo_name: str):
        self.repo_name = repo_name
        self._headers  = {
            "Authorization": f"Bearer {token}",
            "Accept":        "application/vnd.github+json",
        }

    # ── Public API ────────────────────────────────────────────────────────────

    def build_context(self, issue_title: str, issue_body: str) -> str:
        keywords = _extract_keywords(f"{issue_title} {issue_body}")
        print(f"   Keywords extracted: {keywords[:10]}")

        all_blobs = self._fetch_tree()
        print(f"   Total blobs in repo: {len(all_blobs)}")

        candidates = self._filter_and_rank(all_blobs, keywords)
        print(f"   Candidates after filter+rank: {len(candidates)}")

        tree_str  = self._build_ascii_tree(all_blobs)
        sections  = [f"# Repository File Tree\n```\n{tree_str}\n```\n\n# Source Files\n"]
        total     = sum(len(s) for s in sections)

        fetched, skipped = 0, 0
        for blob in candidates:
            if total >= MAX_TOTAL_CHARS:
                sections.append(f"\n> ⚠️  Context limit reached. {len(candidates)-fetched} files omitted.\n")
                break
            content = self._fetch_content(blob["path"])
            if content is None:
                skipped += 1
                continue
            lang    = _lang_fence(blob["path"])
            section = f"\n## `{blob['path']}`\n```{lang}\n{content}\n```\n"
            total  += len(section)
            sections.append(section)
            fetched += 1

        print(f"   Files included: {fetched} | Skipped: {skipped} | Context size: {total:,} chars")
        return "".join(sections)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _fetch_tree(self) -> list[dict]:
        url  = f"https://api.github.com/repos/{self.repo_name}/git/trees/HEAD?recursive=1"
        resp = requests.get(url, headers=self._headers, timeout=60)
        resp.raise_for_status()
        return [b for b in resp.json().get("tree", []) if b["type"] == "blob"]

    def _filter_and_rank(self, blobs: list[dict], keywords: list[str]) -> list[dict]:
        out = []
        for b in blobs:
            path = b["path"]
            # Skip by directory segment
            parts = path.replace("\\", "/").split("/")
            if any(seg in SKIP_DIR_SEGMENTS for seg in parts):
                continue
            # Skip by extension
            ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
            if ext in SKIP_EXTENSIONS:
                continue
            # Skip oversize files
            if b.get("size", 0) > MAX_FILE_BYTES:
                continue
            # Compute sort key
            tier  = _tier(path)
            if tier == 0:
                continue      # not a recognised source file
            bonus = _relevance(path, keywords)
            b["_sort"] = (tier + bonus, bonus, path)
            out.append(b)

        out.sort(key=lambda x: x["_sort"], reverse=True)
        return out

    def _fetch_content(self, path: str) -> Optional[str]:
        url = f"https://api.github.com/repos/{self.repo_name}/contents/{path}"
        try:
            resp = requests.get(url, headers=self._headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                raw  = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
                # Truncate if a single file is still too large
                if len(raw) > MAX_FILE_BYTES:
                    raw = raw[:MAX_FILE_BYTES] + "\n// ... [file truncated] ...\n"
                return raw
        except Exception as exc:
            print(f"      ⚠️  Could not fetch {path}: {exc}")
        return None

    def _build_ascii_tree(self, blobs: list[dict]) -> str:
        paths  = sorted(b["path"] for b in blobs)
        lines  = []
        seen   = set()

        for path in paths:
            parts = path.split("/")
            for depth, part in enumerate(parts):
                key = "/".join(parts[: depth + 1])
                if key in seen:
                    continue
                seen.add(key)
                indent = "  " * depth
                is_file = depth == len(parts) - 1
                prefix  = "└─ " if depth > 0 else ""
                lines.append(f"{indent}{prefix}{part}{'/' if not is_file else ''}")

            if len(lines) > TREE_LINES_MAX:
                lines.append("  ... (truncated)")
                break

        return "\n".join(lines)
