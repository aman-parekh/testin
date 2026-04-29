"""
github_ops.py — GitHub API wrapper for the Claude Agent.
Handles branch creation, atomic multi-file commits, PR creation, and auto-merge.
"""

import requests
from github import Github, GithubException, InputGitTreeElement


class GitHubOps:
    def __init__(self, token: str, repo_name: str):
        self.token     = token
        self.repo_name = repo_name
        self.g         = Github(token)
        self.repo      = self.g.get_repo(repo_name)
        self._headers  = {
            "Authorization": f"Bearer {token}",
            "Accept":        "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    # ── Issue ─────────────────────────────────────────────────────────────────

    def get_issue(self, number: int):
        return self.repo.get_issue(number)

    def create_issue_comment(self, number: int, body: str):
        self.repo.get_issue(number).create_comment(body)

    def add_label(self, number: int, label: str):
        """Add a label, creating it first if it doesn't exist."""
        try:
            self.repo.get_label(label)
        except GithubException:
            self.repo.create_label(label, "0075ca")   # blue
        self.repo.get_issue(number).add_to_labels(label)

    # ── Branch ───────────────────────────────────────────────────────────────

    def get_default_branch_sha(self) -> str:
        ref = self.repo.get_git_ref(f"heads/{self.repo.default_branch}")
        return ref.object.sha

    def create_branch(self, branch_name: str) -> str:
        sha = self.get_default_branch_sha()
        try:
            self.repo.create_git_ref(f"refs/heads/{branch_name}", sha)
            print(f"   Branch '{branch_name}' created from {sha[:7]}")
        except GithubException as exc:
            if exc.status == 422:          # already exists — reuse it
                print(f"   Branch '{branch_name}' already exists, reusing")
            else:
                raise
        return branch_name

    # ── Atomic multi-file commit ──────────────────────────────────────────────

    def commit_files_batch(self, branch: str, files: list[dict], message: str):
        """
        Commit multiple files in a single Git commit via the Git Data API.
        files: [{"path": str, "content": str, "action": "create|modify|delete"}]
        """
        # Current HEAD of branch
        ref          = self.repo.get_git_ref(f"heads/{branch}")
        head_sha     = ref.object.sha
        head_commit  = self.repo.get_git_commit(head_sha)
        base_tree    = head_commit.tree

        tree_elements: list[InputGitTreeElement] = []

        for f in files:
            action  = f.get("action", "modify")
            path    = f["path"]

            if action == "delete":
                # Setting sha=None removes the path from the tree
                tree_elements.append(
                    InputGitTreeElement(path=path, mode="100644", type="blob", sha=None)
                )
            else:
                blob = self.repo.create_git_blob(f["content"], "utf-8")
                tree_elements.append(
                    InputGitTreeElement(path=path, mode="100644", type="blob", sha=blob.sha)
                )

        new_tree   = self.repo.create_git_tree(tree_elements, base_tree=base_tree)
        new_commit = self.repo.create_git_commit(
            message=message,
            tree=new_tree,
            parents=[head_commit],
        )
        ref.edit(new_commit.sha)
        print(f"   Committed {len(files)} file(s) → {new_commit.sha[:7]}")

    # ── Pull Request ──────────────────────────────────────────────────────────

    def create_pull_request(
        self, title: str, body: str, head: str, base: str = "main"
    ):
        return self.repo.create_pull(
            title=title,
            body=body,
            head=head,
            base=base,
            draft=False,
        )

    def enable_auto_merge(self, pr_number: int, method: str = "SQUASH") -> bool:
        """
        Enable auto-merge via GitHub GraphQL API.
        Requires the repository to have auto-merge enabled in Settings.
        method: SQUASH | MERGE | REBASE
        """
        # 1) Resolve PR node ID
        url  = f"https://api.github.com/repos/{self.repo_name}/pulls/{pr_number}"
        resp = requests.get(url, headers=self._headers, timeout=30)
        resp.raise_for_status()
        node_id = resp.json()["node_id"]

        # 2) GraphQL mutation
        mutation = """
        mutation EnableAutoMerge($pullRequestId: ID!, $mergeMethod: PullRequestMergeMethod!) {
            enablePullRequestAutoMerge(input: {
                pullRequestId: $pullRequestId,
                mergeMethod: $mergeMethod
            }) {
                pullRequest { number autoMergeRequest { enabledAt } }
            }
        }
        """
        gql_resp = requests.post(
            "https://api.github.com/graphql",
            headers=self._headers,
            json={"query": mutation, "variables": {"pullRequestId": node_id, "mergeMethod": method}},
            timeout=30,
        )

        if gql_resp.status_code == 200 and "errors" not in gql_resp.json():
            print(f"   Auto-merge (SQUASH) enabled for PR #{pr_number}")
            return True
        else:
            # Non-fatal — repo may not have auto-merge setting enabled
            print(f"   ⚠️  Auto-merge not available: {gql_resp.text[:200]}")
            print("      → Enable 'Allow auto-merge' in repo Settings to activate this feature.")
            return False

    def request_reviewers(self, pr_number: int, reviewers: list[str]):
        pr = self.repo.get_pull(pr_number)
        pr.create_review_request(reviewers=reviewers)
