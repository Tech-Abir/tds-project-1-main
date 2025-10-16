# app/github_utils.py
import os
from github import Github, GithubException
import httpx
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
USERNAME = os.getenv("GITHUB_USERNAME")
g = Github(GITHUB_TOKEN)


# -----------------------------
# Repository creation / retrieval
# -----------------------------
def create_repo(repo_name: str, description: str = ""):
    """
    Create a public repository or return existing repo.
    """
    user = g.get_user()
    try:
        repo = user.get_repo(repo_name)
        print("Repo already exists:", repo.full_name)
        return repo
    except GithubException as e:
        if e.status != 404:
            raise

    repo = user.create_repo(
        name=repo_name,
        description=description,
        private=False,
        auto_init=False
    )
    print("Created repo:", repo.full_name)
    return repo


# -----------------------------
# File handling (text + binary)
# -----------------------------
def create_or_update_file(repo, path: str, content: str, message: str):
    """
    Create or update a text-based file (HTML, JSON, Markdown, etc.)
    """
    try:
        existing = repo.get_contents(path)
        repo.update_file(path, message, content, sha=existing.sha)
        print(f"Updated {path} in {repo.full_name}")
    except GithubException as e:
        if e.status == 404:
            repo.create_file(path, message, content)
            print(f"Created {path} in {repo.full_name}")
        else:
            raise


def create_or_update_binary_file(repo, path: str, binary_content: bytes, commit_message: str):
    """
    Create or update binary files (images, PDFs, etc.) using base64 encoding.
    Also create a backup .b64 file for repository tracking.
    """
    import base64
    b64_content = base64.b64encode(binary_content).decode("utf-8")

    # Write/update main binary file using GitHub's content API
    try:
        existing = repo.get_contents(path)
        repo.update_file(path, commit_message, binary_content, sha=existing.sha)
        print(f"Updated binary file {path} in {repo.full_name}")
    except GithubException as e:
        if e.status == 404:
            repo.create_file(path, commit_message, binary_content)
            print(f"Created binary file {path} in {repo.full_name}")
        else:
            raise

    # Also save a base64 backup
    backup_path = f"attachments/{os.path.basename(path)}.b64"
    try:
        existing_backup = repo.get_contents(backup_path)
        repo.update_file(backup_path, f"Backup {path}", b64_content, sha=existing_backup.sha)
    except GithubException as e:
        if e.status == 404:
            repo.create_file(backup_path, f"Backup {path}", b64_content)
    print(f"Saved base64 backup at {backup_path}")


# -----------------------------
# GitHub Pages handling
# -----------------------------
def enable_pages(repo_name: str, branch: str = "main"):
    """
    Enable GitHub Pages for the repository via REST API.
    Returns True if Pages enabled successfully or already building.
    """
    url = f"https://api.github.com/repos/{USERNAME}/{repo_name}/pages"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    data = {"source": {"branch": branch, "path": "/"}}
    try:
        r = httpx.post(url, headers=headers, json=data, timeout=30.0)
        if r.status_code in (201, 204, 202):
            print("✅ Pages enabled for", repo_name)
            return True
        else:
            print("⚠ Pages API returned:", r.status_code, r.text)
            return False
    except Exception as e:
        print("❌ Failed to call Pages API:", e)
        return False


# -----------------------------
# MIT License generator
# -----------------------------
def generate_mit_license(owner_name=None):
    year = datetime.utcnow().year
    owner = owner_name or USERNAME or "Owner"
    return f"""MIT License

Copyright (c) {year} {owner}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
