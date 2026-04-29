"""
Claude AI Agent — GitHub Issue Implementer
Triggered by GitHub Actions on 'claude: fix' or 'claude: implement' labels.
Reads the full codebase, calls Claude, commits changes, creates PR, enables auto-merge.
"""

import os
import sys
import json
import traceback
import anthropic
from github_ops import GitHubOps
from context_builder import ContextBuilder

# ─── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN      = os.environ["GITHUB_TOKEN"]
REPO_NAME         = os.environ["REPO_NAME"]
ISSUE_NUMBER      = int(os.environ["ISSUE_NUMBER"])
ISSUE_LABEL       = os.environ.get("ISSUE_LABEL", "")
MODEL             = os.environ.get("CLAUDE_MODEL", "claude-opus-4-6")
MAX_TOKENS        = int(os.environ.get("CLAUDE_MAX_TOKENS", "8192"))

ACTION_TYPE = "bug_fix" if "fix" in ISSUE_LABEL else "feature"


# ─── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are an elite Android engineer and autonomous coding agent specialising in
Kotlin + Jetpack Compose. You are called by a GitHub Actions pipeline to implement
features and bug fixes directly into a production Android codebase.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GRADIENT DESIGN SYSTEM  ← MANDATORY — NEVER OMIT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Every composable you create or modify MUST use Brush gradients. This is a
hard product requirement enforced in CI.

Token          | Gradient                                   | Usage
─────────────────────────────────────────────────────────────────────────────
Primary        | #6366F1 → #8B5CF6 (indigo → violet)        | Main CTAs, headers
Accent         | #06B6D4 → #3B82F6 (cyan → blue)            | Secondary actions
Success        | #10B981 → #059669 (emerald → green)         | Confirmations
Warning        | #F59E0B → #D97706 (amber → orange)          | Alerts
Error          | #EF4444 → #DC2626 (red → crimson)           | Destructive actions
Surface        | Primary at 0.08–0.12 alpha                  | Cards, bottom sheets
─────────────────────────────────────────────────────────────────────────────

Rules:
- Buttons  → Modifier.background(brush=Brush.linearGradient(...), shape=RoundedCornerShape(12.dp))
- Screens  → Box(Modifier.fillMaxSize().background(Brush.verticalGradient([0xFF0F0C29, 0xFF302B63, 0xFF24243E].map(::Color))))
- Cards    → Surface with gradient border OR translucent gradient background
- Text on gradient → always Color.White or Color.White.copy(alpha=0.87f)
- Icons on gradient → use tint = Color.White
- Use animateColorAsState / animateFloatAsState for state-driven gradient transitions

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ARCHITECTURE & CODE STANDARDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- MVVM strict: ViewModel ← UiState (sealed class) ← StateFlow
- Repositories are the single source of truth; never call data layer from UI
- Compose: stateless leaf composables, state hoisted to screen-level composables
- Use remember / derivedStateOf / LaunchedEffect correctly
- Coroutines: viewModelScope for VM, lifecycleScope forbidden in Compose
- Dependency injection: Hilt (@HiltViewModel, @Inject, @Module)
- Always add unit tests for ViewModel and Repository logic
- Compose previews (@Preview with @PreviewParameter) for all new screens
- Accessibility: contentDescription on every Icon, Image, and interactive element
- Material3 as foundation — customise with gradients, never fight the system

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT  ← CRITICAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Respond ONLY with a single valid JSON object — no markdown fences, no explanation
outside the JSON. Any text outside the JSON will cause a parse failure.

{
  "branch_name": "claude/fix-issue-{N}-kebab-case-description",
  "pr_title":    "fix: short imperative description (#N)",
  "pr_body":     "## Summary\\n...\\n## Changes\\n- `path` — reason\\n## Testing\\n...",
  "commit_message": "fix: description (#N)",
  "confidence":  "high | medium | low",
  "risk_level":  "low | medium | high",
  "files": [
    {
      "path":    "app/src/main/java/com/example/Feature.kt",
      "content": "<FULL file content — never a diff>",
      "action":  "create | modify | delete"
    }
  ],
  "test_files": [
    {
      "path":    "app/src/test/java/com/example/FeatureTest.kt",
      "content": "<FULL test file content>",
      "action":  "create | modify"
    }
  ]
}

PR title prefix conventions:
  feat:     new feature
  fix:      bug fix
  refactor: refactoring without behaviour change
  style:    gradient / UI-only changes
  test:     test-only changes
  chore:    build, deps, config
"""


def build_user_prompt(issue_title: str, issue_body: str, context: str) -> str:
    action_desc = (
        "Fix the bug described in the issue. Identify the root cause from the codebase "
        "and implement a clean, minimal fix."
        if ACTION_TYPE == "bug_fix"
        else
        "Implement the feature described in the issue. Follow the existing architectural "
        "patterns found in the codebase."
    )
    return f"""
## GitHub Issue #{ISSUE_NUMBER}: {issue_title}
**Label:** {ISSUE_LABEL}

### Description
{issue_body or "_(No description provided)_"}

---

## Current Codebase
{context}

---

## Your Task
{action_desc}

Reminders:
1. Apply the gradient design system to ALL UI changes — never use flat colours for backgrounds/buttons
2. Write complete file contents, never partial diffs
3. Include ViewModel/Repository unit tests for any new business logic
4. Return ONLY the JSON object described in your system instructions
5. Verify all import paths match the existing package structure in the codebase
"""


def parse_response(text: str) -> dict:
    text = text.strip()
    # Strip markdown fences if model adds them despite instructions
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


def main():
    print(f"\n{'━'*60}")
    print(f"  🤖 Claude Agent | Issue #{ISSUE_NUMBER} | {ACTION_TYPE.replace('_',' ').title()}")
    print(f"{'━'*60}\n")

    gh      = GitHubOps(GITHUB_TOKEN, REPO_NAME)
    issue   = gh.get_issue(ISSUE_NUMBER)
    client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # ── 1. Signal start ──────────────────────────────────────────────────────
    gh.create_issue_comment(ISSUE_NUMBER, (
        "## 🤖 Claude Agent Activated\n\n"
        f"I'm analysing **Issue #{ISSUE_NUMBER}** and will implement the changes shortly.\n\n"
        "| Step | Status |\n|------|--------|\n"
        "| Read codebase | ⏳ In progress |\n"
        "| Implement changes | ⏳ Pending |\n"
        "| Create PR | ⏳ Pending |\n"
        "| Auto-merge (after CI) | ⏳ Pending |"
    ))

    # ── 2. Build codebase context ────────────────────────────────────────────
    print("📁 Building codebase context…")
    builder = ContextBuilder(GITHUB_TOKEN, REPO_NAME)
    context = builder.build_context(issue.title, issue.body or "")
    print(f"   Context: {len(context):,} chars")

    # ── 3. Call Claude ───────────────────────────────────────────────────────
    print(f"🧠 Calling {MODEL}…")
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": build_user_prompt(issue.title, issue.body or "", context)
        }]
    )

    raw = response.content[0].text
    print(f"   Response: {len(raw):,} chars | stop_reason: {response.stop_reason}")

    # ── 4. Parse ─────────────────────────────────────────────────────────────
    result = parse_response(raw)
    all_files = result.get("files", []) + result.get("test_files", [])
    print(f"   Files to change: {len(all_files)} | Confidence: {result.get('confidence','?')} | Risk: {result.get('risk_level','?')}")

    # ── 5. Create branch & commit (single atomic commit) ────────────────────
    branch = result["branch_name"]
    print(f"🌿 Creating branch: {branch}")
    gh.create_branch(branch)

    print(f"📝 Committing {len(all_files)} file(s) atomically…")
    for f in all_files:
        print(f"   {f['action']:8} {f['path']}")
    gh.commit_files_batch(branch, all_files, result["commit_message"])

    # ── 6. Create PR ─────────────────────────────────────────────────────────
    print("🔀 Creating Pull Request…")
    pr_body = (
        result["pr_body"]
        + f"\n\n---\n_🤖 Implemented autonomously by Claude ({MODEL}) "
        f"in response to Issue #{ISSUE_NUMBER}._\n"
        f"_Confidence: **{result.get('confidence','?')}** | Risk: **{result.get('risk_level','?')}**_"
    )
    pr = gh.create_pull_request(
        title=result["pr_title"],
        body=pr_body,
        head=branch,
        base="main"
    )
    print(f"   PR #{pr.number} created: {pr.html_url}")

    # ── 7. Enable auto-merge ─────────────────────────────────────────────────
    print("⚡ Enabling auto-merge (squash)…")
    gh.enable_auto_merge(pr.number)

    # ── 8. Link PR to issue ──────────────────────────────────────────────────
    file_table = "\n".join(
        f"| `{f['path']}` | {f['action'].capitalize()} |"
        for f in all_files
    )
    gh.create_issue_comment(ISSUE_NUMBER, (
        f"## ✅ Implementation Complete\n\n"
        f"Created **PR #{pr.number}**: [{result['pr_title']}]({pr.html_url})\n\n"
        f"### Changed Files\n| File | Action |\n|------|--------|\n{file_table}\n\n"
        f"### Confidence\n"
        f"- Model confidence: **{result.get('confidence','?')}**\n"
        f"- Risk level: **{result.get('risk_level','?')}**\n\n"
        f"The PR will **automatically merge** once all CI checks pass. 🚀\n\n"
        f"> This issue will be closed automatically when the PR merges."
    ))

    # ── 9. Add PR-closes link to issue ───────────────────────────────────────
    gh.add_label(ISSUE_NUMBER, "claude: implemented")
    print(f"\n✅ Done! PR #{pr.number} created with auto-merge enabled.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        traceback.print_exc()
        # Try to post failure comment
        try:
            gh = GitHubOps(GITHUB_TOKEN, REPO_NAME)
            gh.create_issue_comment(ISSUE_NUMBER, (
                "## ❌ Claude Agent Failed\n\n"
                f"```\n{traceback.format_exc()}\n```\n\n"
                "Please check the [Actions log]("
                f"https://github.com/{REPO_NAME}/actions) for details.\n"
                "You can retry by removing and re-adding the label."
            ))
        except Exception:
            pass
        sys.exit(1)
