# 🤖 Claude Code Agent — Setup Guide

**No API key needed.** Uses your Claude Code subscription via OAuth token.

---

## What's in this zip

```
CLAUDE.md                                ← Claude's permanent rules (gradients, architecture)
.github/
  workflows/
    claude-agent.yml                     ← main agent trigger
    android-ci.yml                       ← build + test + lint gate
    rollback.yml                         ← auto-reverts main if CI breaks
  ISSUE_TEMPLATE/
    bug_report.yml                       ← pre-labels with 'claude: fix'
    feature_request.yml                  ← pre-labels with 'claude: implement'
    config.yml
```

---

## One-time Setup (5 steps)

### 1. Generate your OAuth token
```bash
claude update          # must be v1.0.44 or later
claude setup-token     # prints your CLAUDE_CODE_OAUTH_TOKEN — copy it
```

### 2. Add secret to GitHub
**Repo → Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|------|-------|
| `CLAUDE_CODE_OAUTH_TOKEN` | the token from step 1 |

### 3. Install Claude GitHub App
👉 [github.com/apps/claude](https://github.com/apps/claude) — install it on your repo

### 4. Enable auto-merge
**Repo → Settings → General → Pull Requests → ✅ Allow auto-merge**

### 5. Set branch protection on `main`
**Repo → Settings → Branches → Add rule for `main`:**
- ✅ Require status checks: `Build Debug APK`, `Unit Tests`, `Lint Check`
- ✅ Require branches to be up to date before merging
- ✅ Require a pull request before merging

### 6. Create labels (run once)
```bash
gh label create "claude: fix"         --color "EF4444"
gh label create "claude: implement"   --color "6366F1"
gh label create "claude: implemented" --color "10B981"
gh label create "incident"            --color "DC2626"
```

---

## How to use

| Action | How |
|--------|-----|
| Report a bug | Issues → New Issue → 🐛 Bug Report (label auto-applied) |
| Request a feature | Issues → New Issue → ✨ Feature Request (label auto-applied) |
| Trigger manually | Add label `claude: fix` or `claude: implement` to any issue |
| Retry a failed run | Remove the label, then re-add it |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `invalid x-api-key` error | You have the old Python version — replace `claude-agent.yml` with the one in this zip |
| OAuth token invalid | Re-run `claude setup-token`, update the GitHub secret |
| Auto-merge not firing | Enable "Allow auto-merge" in repo Settings |
| CI not running on PRs | Confirm `android-ci.yml` is in `.github/workflows/` |
| `gradlew` permission denied | Run `git update-index --chmod=+x gradlew && git push` |
| Token expired | OAuth tokens last ~1 year — re-run `claude setup-token` to refresh |
