"""
Deterministic logic the LLM never calls directly.
 
Every function here is a fixed rule, not a judgment call — branch
creation, commit/push, PR open-or-update, and persisting the agent's
own memory (last_commit_id + summaries) to disk. Compare with
decision_tools.py, where every function is something the agent decides
to call based on its own reasoning.
"""


import json
from pathlib import Path

from langchain_core.tools import tool



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





  
