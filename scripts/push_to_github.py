#!/usr/bin/env python3
"""Push the project to GitHub using gh CLI + token from env file."""
import os
import re
import subprocess
import sys
from pathlib import Path

# Read GITHUB_TOKEN from hermes .env
env_path = Path("/home/deploy/.hermes/profiles/zen/.env")
token = None
for line in env_path.read_text().splitlines():
    if line.startswith("GITHUB_TOKEN") and "=" in line:
        token = line.split("=", 1)[1].strip()
        break
if not token:
    print("ERROR: GITHUB_TOKEN not found in env file", file=sys.stderr)
    sys.exit(1)

os.environ["GH_TOKEN"] = token
project = Path("/home/deploy/workspace/ai-industry-watcher")

print("=== Step 1: Create GitHub repo + push ===")
r = subprocess.run(
    [
        "gh", "repo", "create", "igoingtodevx/industry-watcher",
        "--public",
        "--description", "Wochenliches KI-Intelligence-Briefing fuer deutsche Mittelstaendler. RSS-Scraper + LLM-Brief + Editorial-Frontend, deployed auf Vercel.",
        "--source=.", "--remote=origin", "--push",
    ],
    cwd=str(project),
    capture_output=True, text=True, timeout=60,
)
print("STDOUT:", r.stdout)
print("STDERR:", r.stderr)
print(f"EXIT: {r.returncode}")

if r.returncode != 0:
    sys.exit(1)

print()
print("=== Step 2: Verify remote + remote URL ===")
r2 = subprocess.run(["git", "remote", "-v"], cwd=str(project), capture_output=True, text=True)
print(r2.stdout)

print("=== Step 3: Verify on GitHub ===")
r3 = subprocess.run(
    ["gh", "repo", "view", "igoingtodevx/industry-watcher",
     "--json", "name,url,visibility,description,defaultBranchRef"],
    capture_output=True, text=True, timeout=20,
)
print(r3.stdout)
print(r3.stderr)
