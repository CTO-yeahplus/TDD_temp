import os
import json
import subprocess
import textwrap
from pathlib import Path
import requests

GITHUB_API = "https://api.github.com"

def sh(cmd: str):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")

def gh_headers(token: str):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

def get_issue(owner, repo, issue_number, token):
    r = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}",
        headers=gh_headers(token),
        timeout=30,
    )
    r.raise_for_status()
    return r.json()

def create_branch(branch):
    sh("git config user.name 'agent-bot'")
    sh("git config user.email 'agent-bot@users.noreply.github.com'")
    sh(f"git checkout -b {branch}")

def commit_all(message):
    sh("git add -A")
    code, out = sh(f"git commit -m {json.dumps(message)}")
    if code != 0 and "nothing to commit" not in out:
        raise RuntimeError(out)

def push_branch(branch):
    code, out = sh(f"git push -u origin {branch}")
    if code != 0:
        raise RuntimeError(out)

def create_pr(owner, repo, token, head, base, title, body):
    payload = {"title": title, "head": head, "base": base, "body": body}
    r = requests.post(
        f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
        headers=gh_headers(token),
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("html_url", "")

def apply_demo_change(issue):
    text = (issue.get("title","") + "\n" + (issue.get("body") or "")).lower()

    if "add(" not in text and "add function" not in text:
        raise RuntimeError("Demo v0 supports only add(a,b) issues.")

    test_path = Path("tests/test_app.py")
    app_path = Path("src/app.py")

    test_append = '''
from src.app import add

def test_add_basic():
    assert add(1, 2) == 3

def test_add_negative():
    assert add(-1, 1) == 0
'''
    current = test_path.read_text()
    if "test_add_basic" not in current:
        test_path.write_text(current + "\n" + textwrap.dedent(test_append))

    sh("pytest -q")

    app_src = app_path.read_text()
    if "def add(" not in app_src:
        app_src += "\n\ndef add(a: int, b: int) -> int:\n    return a + b\n"
        app_path.write_text(app_src)

    code, out = sh("pytest -q")
    if code != 0:
        raise RuntimeError(out)

def main():
    token = os.environ["GITHUB_TOKEN"]
    owner = os.environ["GITHUB_OWNER"]
    repo = os.environ["GITHUB_REPO"]
    issue_number = int(os.environ["ISSUE_NUMBER"])
    base_branch = os.environ.get("BASE_BRANCH", "main")

    issue = get_issue(owner, repo, issue_number, token)
    branch = f"agent/issue-{issue_number}"
    create_branch(branch)

    apply_demo_change(issue)

    commit_all(f"Agent: resolve issue #{issue_number}")
    push_branch(branch)

    pr_url = create_pr(
        owner, repo, token,
        branch, base_branch,
        f"[Agent] {issue.get('title','Issue')}",
        f"Automated PR for issue #{issue_number}\n\nCloses #{issue_number}"
    )

    print("PR created:", pr_url)

if __name__ == "__main__":
    main()
