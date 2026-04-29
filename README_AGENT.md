# 🤖 Claude AI Agent — Setup Guide

An autonomous GitHub agent that reads Issues, implements Kotlin + Jetpack Compose
code (with a mandatory gradient design system), and auto-merges after CI passes.

```
Issue labelled  →  GitHub Actions triggers  →  Claude reads codebase
→  Implements changes  →  Creates PR  →  CI passes  →  Auto-merges ✅
```

---

## Prerequisites

| Requirement | Detail |
|---|---|
| Anthropic API key | [console.anthropic.com](https://console.anthropic.com) |
| GitHub repo | Admin access required for branch protection + auto-merge settings |
| Android project | Kotlin + Jetpack Compose with `./gradlew test` passing |

---

## 1. Copy Files into Your Repo

```bash
cp -r android-claude-agent/.github          your-repo/
cp -r android-claude-agent/scripts          your-repo/
cp    android-claude-agent/CLAUDE_RULES.md  your-repo/
```

---

## 2. Add Repository Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (`sk-ant-...`) |

> `GITHUB_TOKEN` is provided automatically by GitHub Actions — no setup needed.

---

## 3. Enable Auto-Merge on the Repository

**Settings → General → Pull Requests → ✅ Allow auto-merge**

This is required for the agent to auto-merge PRs after CI passes.

---

## 4. Configure Branch Protection for `main`

**Settings → Branches → Add branch protection rule** for `main`:

| Setting | Value |
|---|---|
| Require status checks | ✅ Enabled |
| Required checks | `Build Debug APK`, `Unit Tests`, `Lint Check` |
| Require branches to be up to date | ✅ Enabled |
| Require pull request before merging | ✅ Enabled |
| Allow auto-merge to bypass | ✅ (or use a PAT — see §6) |

---

## 5. Create the Issue Labels

Run this once to create the two trigger labels:

```bash
gh label create "claude: fix"       --color "EF4444" --description "Claude will auto-fix this bug"
gh label create "claude: implement" --color "6366F1" --description "Claude will implement this feature"
gh label create "claude: implemented" --color "10B981" --description "Implementation PR created"
gh label create "incident"          --color "DC2626" --description "Auto-rollback triggered"
```

---

## 6. (Optional) Use a Personal Access Token for Auto-Merge

If your branch protection rules block `GITHUB_TOKEN` from merging, create a PAT:

1. **Settings → Developer settings → Personal access tokens (classic)**
2. Scopes: `repo`, `workflow`
3. Add as secret: `PAT_TOKEN`
4. Replace `${{ secrets.GITHUB_TOKEN }}` with `${{ secrets.PAT_TOKEN }}` in
   `.github/workflows/claude-agent.yml`

---

## 7. Optional: Tune the Model

Add a **Repository variable** (`Settings → Variables`):

| Variable | Default | Options |
|---|---|---|
| `CLAUDE_MODEL` | `claude-opus-4-6` | `claude-sonnet-4-6`, `claude-opus-4-6` |
| `CLAUDE_MAX_TOKENS` | `8192` | Up to `32768` for complex features |

---

## How to Use

### Report a Bug
1. Open a new Issue → **🐛 Bug Report** template
2. Fill in all fields (stack trace especially helpful)
3. Submit — the `claude: fix` label is added automatically
4. Watch the Actions tab — Claude will comment, create a branch, open a PR, and it will auto-merge

### Request a Feature
1. Open a new Issue → **✨ Feature Request** template
2. Describe the UI in detail (Claude enforces gradients automatically)
3. Submit — the `claude: implement` label is added automatically
4. Same flow as above

### Manual Trigger
Add the label `claude: fix` or `claude: implement` to any existing issue.

### Retry a Failed Run
Remove the label, then re-add it. The agent will run again from scratch.

---

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Issue                             │
│  Label: 'claude: fix' or 'claude: implement'                   │
└────────────────────────────┬────────────────────────────────────┘
                             │ triggers
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              claude-agent.yml (GitHub Actions)                  │
│                                                                 │
│  1. Comment "🤖 Agent activated" on issue                      │
│  2. ContextBuilder fetches full repo (filtered, prioritised)   │
│  3. Calls claude-opus-4-6 with system prompt + codebase        │
│  4. Parses JSON response → file changes                        │
│  5. Creates branch, atomic commit (Git Data API)               │
│  6. Creates PR with auto-merge enabled                         │
│  7. Comments PR link on issue                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ PR created
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              android-ci.yml (GitHub Actions)                    │
│                                                                 │
│  Job 1: ./gradlew assembleDebug                                │
│  Job 2: ./gradlew test                                         │
│  Job 3: ./gradlew lint                                         │
└────────────────────────────┬────────────────────────────────────┘
                      ┌──────┴──────┐
                   pass             fail
                      │             │
                      ▼             ▼
              Auto-merge        PR blocked
              to main           (human fixes)
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│              rollback.yml (GitHub Actions)                      │
│                                                                 │
│  Runs ./gradlew assembleDebug test on main after merge         │
│  If failure → git revert + open incident issue                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Agent runs but nothing happens | Check `ANTHROPIC_API_KEY` secret is set correctly |
| Auto-merge not firing | Enable "Allow auto-merge" in repo Settings → General |
| PR created but CI not running | Check `android-ci.yml` is in `.github/workflows/` |
| `./gradlew test` fails in CI | Ensure your project has unit tests and they pass locally |
| Auto-merge blocked by branch protection | Use a PAT with `repo` scope — see §6 |
| Claude produces invalid JSON | Upgrade to `claude-opus-4-6` via the `CLAUDE_MODEL` variable |
