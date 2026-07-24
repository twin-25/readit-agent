"""
Deterministic logic the LLM never calls directly.

Every function here is a fixed rule, not a judgment call — branch
creation, commit/push, PR open-or-update, and persisting the agent's
own memory (last_commit_id + summaries) to disk. Compare with
decision_tools.py, where every function is something the agent decides
to call based on its own reasoning.

Call order (enforced by graph.py, not by this file):
  is_safe_to_proceed()
  create_branch()
  write_readme(...)          # decision_tools.py
  save_summaries(...)        # writes .readit-agent/summaries.json to disk
  commit_and_push()          # stages README.md AND summaries.json together
  open_or_update_pr()

save_summaries must run BEFORE commit_and_push, since commit_and_push
stages .readit-agent/summaries.json by name — if that file doesn't
exist yet (first run) or still holds last run's content, the commit
either fails outright or ships stale data.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from github import Github

logger = logging.getLogger(__name__)

GIT_TIMEOUT = 30  # seconds — prevents a hung git process from blocking a run forever

# Fixed identity the agent commits under. Used by commit_and_push (to set
# it) and is_safe_to_proceed (to check it) — defined once here so both
# stay in sync if it's ever changed.
AGENT_GIT_NAME = "readit-agent-bot"
AGENT_GIT_EMAIL = "bot@readit-agent.dev"


def is_safe_to_proceed():
  """The safety-gate check. Called first, before create_branch, on
  every run. Fetches origin/readit-agent/update (not the local
  branch — the local copy can be stale if a human pushed directly to
  the remote since the agent's last fetch) and inspects its last
  commit's author.

  Returns True if: the remote branch doesn't exist yet (first run),
  or its last commit was authored by the agent itself.
  Returns False if: a human's name shows up as the last author, or
  an unexpected git error occurs (fail closed, not open)."""

  try:
      
    fetch_result = subprocess.run(
        ["git", "fetch", "origin", "readit-agent/update"],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT,
    )
  
 

    if fetch_result.returncode != 0:
      if "couldn't find remote ref" in fetch_result.stderr:
          # Branch genuinely doesn't exist on the remote yet — first run.
          return True
      # Any other fetch failure (network, auth, etc.) — fail closed.
      logger.error("git fetch failed unexpectedly: %s", fetch_result.stderr)
      return False
  

    result = subprocess.run(
        ["git", "log", "-1", "--format=%an", "origin/readit-agent/update"],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT,
    )

    if result.returncode != 0:
      logger.error("git log failed unexpectedly: %s", result.stderr)
      return False

    author = result.stdout.strip()

    if author == AGENT_GIT_NAME:
        return True

    # Empty author after a successful fetch is unexpected — fail closed
    # rather than assume it's safe.
    return False
  
  except subprocess.TimeoutExpired:
      logger.error("git process timed out after %s seconds", GIT_TIMEOUT)
      return False

  except OSError:
      logger.error("Failed to run git (is it installed ?)")
      return False


def create_branch():
  """Create the agent's stable branch (readit-agent/update), always
  based explicitly on origin/main — not whatever happens to be
  checked out locally, which could be stale or a different branch
  entirely. Fetches origin/main first, then branches from that exact
  commit, so this function is deterministic regardless of local state.
  Returns True on success, False on failure (including if git itself
  fails to run, e.g. not installed) — never raises."""
  try:
      fetch_result = subprocess.run(
          ["git", "fetch", "origin", "main"],
          capture_output=True,
          text=True,
          timeout=GIT_TIMEOUT,
      )
      if fetch_result.returncode != 0:
          logger.error("git fetch origin main failed: %s", fetch_result.stderr)
          return False

      result = subprocess.run(
          ["git", "checkout", "-B", "readit-agent/update", "origin/main"],
          capture_output=True,
          text=True,
          timeout=GIT_TIMEOUT,
      )
      if result.returncode == 0:
          return True
      logger.error("git checkout -B failed: %s", result.stderr)
      return False

  except OSError:
      logger.exception("Failed to run git (is it installed?)")
      return False
  
  except subprocess.TimeoutExpired:
      logger.error("git fetch timed out after %s seconds", GIT_TIMEOUT)
      return False


def commit_and_push():
  """Stage README.md and .readit-agent/summaries.json, commit if
  there's anything new, and ALWAYS attempt a push — even when nothing
  new was committed this run. This matters: if a previous run
  committed successfully but the push itself failed (e.g. network
  blip), that commit is still sitting locally, unpushed. Only
  attempting to push "when there's something new to commit" would
  silently strand that old commit forever. Must be called after
  create_branch, since it pushes to that specific branch by name.

  Returns one of three strings:
    "no_changes" — nothing new to commit, but push was still attempted
    (and succeeded, or there was nothing to push either)
    "success"    — committed and pushed successfully
    "error"      — a real failure at some step"""


  try:
    stage_result = subprocess.run(
        ["git", "add", "README.md", ".readit-agent/summaries.json"],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT,
    )
    if stage_result.returncode != 0:
        logger.error("git add failed: %s", stage_result.stderr)
        return "error"

    stage_check = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT,
    )
    if stage_check.returncode == 0:
        no_changes = True
    elif stage_check.returncode == 1:
        no_changes = False
    else:
        logger.error("git diff --cached failed unexpectedly: %s", stage_check.stderr)
        return "error"

    if not no_changes:
        config_name = subprocess.run(
            ["git", "config", "--local", "user.name", AGENT_GIT_NAME],
            capture_output=True, text=True, timeout=GIT_TIMEOUT,
        )
        config_email = subprocess.run(
            ["git", "config", "--local", "user.email", AGENT_GIT_EMAIL],
            capture_output=True, text=True, timeout=GIT_TIMEOUT,
        )
        if config_name.returncode != 0 or config_email.returncode != 0:
            logger.error("git config failed — refusing to commit under the wrong identity")
            return "error"

        commit_result = subprocess.run(
            ["git", "commit", "-m", "Updated README and summaries by readit-agent"],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
        if commit_result.returncode != 0:
            logger.error("git commit failed: %s", commit_result.stderr)
            return "error"

    # Always attempt the push, whether or not a new commit was just made,
    # so a previously-failed push gets retried instead of stranded.
    # --force-with-lease (not plain --force): rejects the push if the
    # remote moved since our last fetch, protecting against a human
    # pushing between our safety check and this push.
    push_result = subprocess.run(
        ["git", "push", "--force-with-lease", "origin", "HEAD:readit-agent/update"],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT,
    )
    if push_result.returncode != 0:
        logger.error("git push failed: %s", push_result.stderr)
        return "error"

    return "no_changes" if no_changes else "success"
  
  
  except OSError:
      logger.exception("Failed to run git (is it installed?)")
      return "error"
  
  except subprocess.TimeoutExpired:
      logger.error("git fetch timed out after %s seconds", GIT_TIMEOUT)
      return "error"


def save_summaries(summaries: dict, last_commit_id: str):
  """Persist the agent's memory (summaries + last_commit_id) to
  .readit-agent/summaries.json. Must be called BEFORE commit_and_push
  — commit_and_push stages this exact file by name, so it needs to
  already contain this run's data, not the previous run's."""
  Path(".readit-agent").mkdir(exist_ok=True)

  data = {"last_commit_id": last_commit_id, "summaries": summaries}

  with open(".readit-agent/summaries.json", "w") as f:
      json.dump(data, f)


def get_owner_repo():

  """Extract (owner, repo) from the git remote URL, for use with
  PyGithub's API calls. HTTPS github.com remotes only. Uses
  urllib.parse for real validation rather than naive string
  splitting, so malformed URLs, non-GitHub remotes, and trailing
  slashes are rejected cleanly instead of silently producing a wrong
  owner/repo pair. SSH remotes (git@github.com:owner/repo.git) are
  intentionally unsupported in v1 and explicitly rejected.
  Returns (None, None) if the URL can't be parsed as expected."""

  try:
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT,
    )
    if result.returncode != 0:
        return (None, None)

    url = result.stdout.strip()

    if url.startswith("git@"):
        # SSH scp-like syntax — not a real URL, urlparse won't handle
        # it correctly. Reject explicitly rather than returning garbage.
        return (None, None)

    parsed = urlparse(url)
    if parsed.hostname != "github.com":
        return (None, None)

    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) < 2:
        return (None, None)

    owner = path_parts[-2]
    repo = path_parts[-1].removesuffix(".git")
    return (owner, repo)

  except OSError:
      logger.exception("Failed to run git (is it installed?)")
      return (None, None)
  
  except subprocess.TimeoutExpired:
      logger.error("git fetch timed out after %s seconds", GIT_TIMEOUT)
      return (None, None)
  


def open_or_update_pr():
  """Open a PR from readit-agent/update into main, unless one is
  already open — in which case do nothing, since commit_and_push's
  push already updated its contents automatically.
  Returns "no_remote_configured", "no_token", "success", or "error"."""
  owner, repo_name = get_owner_repo()

  if owner is None or repo_name is None:
      return "no_remote_configured"

  token = os.environ.get("GITHUB_TOKEN")
  if not token:
      return "no_token"

  gh = Github(token)

  try:
    repo = gh.get_repo(f"{owner}/{repo_name}")

    existing = repo.get_pulls(
        state="open",
        head=f"{owner}:readit-agent/update",
        base="main",
    )

    if existing.totalCount == 0:
        repo.create_pull(
            base="main",
            head=f"{owner}:readit-agent/update",
            title="readit-agent: update README",
        )

    return "success"

  except Exception:
    logger.exception("Failed to create or locate pull request")
    return "error"