#!/usr/bin/env python3
"""Configure git remote with token and push."""
import re
import subprocess
import sys
from pathlib import Path

env_path = Path("/home/deploy/.hermes/profiles/zen/.env")
token = None
for line in env_path.read_text().splitlines():
    if line.startswith("GITHUB_TOKEN") and "=" in line:
        token = line.split("=", 1)[1].strip()
        break
if not token:
    print("no token", file=sys.stderr)
    sys.exit(1)

# Save token to a temp file we can read back
token_file = Path("/tmp/.gh_push_token")
token_file.write_text(token)
token_file.chmod(0o600)
print(f"Token saved ({len(token)} chars)")
print()

project = Path("/home/deploy/workspace/ai-industry-watcher")

# Set remote URL with token
new_url = f"https://x-access-token:{token}@github.com/igoingtodevx/industry-watcher.git"
r = subprocess.run(
    ["git", "remote", "set-url", "origin", new_url],
    cwd=str(project), capture_output=True, text=True,
)
print("Set remote:", r.returncode)

r = subprocess.run(["git", "remote", "-v"], cwd=str(project), capture_output=True, text=True)
print("Remote:", r.stdout)

# Push
print()
print("=== Pushing ===")
r = subprocess.run(
    ["git", "push", "-u", "origin", "master"],
    cwd=str(project), capture_output=True, text=True, timeout=60,
)
print("STDOUT:", r.stdout)
print("STDERR:", r.stderr)
print(f"EXIT: {r.returncode}")

# Verify on GitHub via API
print()
print("=== Verify on GitHub ===")
import os
os.environ["GH_TOKEN"] = token
r = subprocess.run(
    ["gh", "repo", "view", "igoingtodevx/industry-watcher",
     "--json", "name,url,visibility,defaultBranchRef,description"],
    capture_output=True, text=True, timeout=20,
)
print(r.stdout)
print(r.stderr)
