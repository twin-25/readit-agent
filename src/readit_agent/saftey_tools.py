"""
Deterministic logic the LLM never calls directly.
 
Every function here is a fixed rule, not a judgment call — branch
creation, commit/push, PR open-or-update, and persisting the agent's
own memory (last_commit_id + summaries) to disk. Compare with
decision_tools.py, where every function is something the agent decides
to call based on its own reasoning.
"""


import json
import subprocess
from pathlib import Path

AGENT_GIT_NAME = "readit-agent-bot"
AGENT_GIT_EMAIL = "bot@readit-agent.dev"


def save_summaries(summaries: dict, last_commit_id: str):
  """Persist the agent's memory (summaries + last_commit_id) to
    .readit-agent/summaries.json. Called once, at the very end of a
    successful run after write_readme, commit_and_push, and
    open_or_update_pr have all succeeded. Never called mid-run, so a
    crash partway through leaves last_commit_id untouched and the next scheduled run simply retries the same diff automatically."""
   
  Path(".readit-agent").mkdir(exist_ok=True)

  data = {"last_commit_id":last_commit_id, "summaries":summaries}

  with open(".readit-agent/summaries.json", "w") as f:
    json.dump(data, f)


def create_branch():
  """Create or switch to the agent's stable branch (readit-agent/update).
    Uses -B, meaning the branch pointer moves to the current commit even
    if it already existed. This is only safe to call after a separate
    safety check confirms no human commit is sitting on that branch,
    since -B would otherwise silently abandon it.
    Returns True on success, False on failure — never raises.
  """

  result = subprocess.run(
    ["git", "checkout", "-B", "readit-agent/update"],
    capture_output=True,
    text=True,
  )

  if result.returncode == 0:
    return True
  return False


def commit_and_push():
    
    """Stage README.md and .readit-agent/summaries.json, commit, and push
    to the readit-agent/update branch. Must be called after create_branch,
    since it pushes to that specific branch by name.
    Returns one of three strings:
      "no_changes" — nothing differed from the last commit, not an error
      "success"    — committed and pushed successfully
      "error"      — a real failure at some step"""
     

    stage_result = subprocess.run(
        ["git", "add", "README.md", ".readit-agent/summaries.json"],
        capture_output=True,
        text=True,
    )

    if stage_result.returncode != 0:
        return "error"
    

    stage_check = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
        text=True,
    )

    if stage_check.returncode == 0:
        return "no_changes"
    

    subprocess.run(["git", "config", "--local", "user.name", AGENT_GIT_NAME], capture_output=True, text=True)
    subprocess.run(["git", "config", "--local", "user.email", AGENT_GIT_EMAIL], capture_output=True, text=True)

    commit_result = subprocess.run(
        ["git", "commit", "-m", "Updated README and summaries by readit-agent"],
        capture_output=True,
        text=True,
    )

    if commit_result.returncode != 0:
        return "error"

    push_result = subprocess.run(
        ["git", "push", "--force", "origin", "readit-agent/update"],
        capture_output=True,
        text=True,
    )

    if push_result.returncode != 0:
        return "error"

    return "success"


def is_safe_to_proceed():
  result = subprocess.run(
    ["git", "log", "-1", "--format=%an", "readit-agent/update"],      capture_output=True,
    text=True,
   )

  author = result.stdout.strip()

  if author == AGENT_GIT_NAME or '':
      return True
   
  return "Failure"

  
