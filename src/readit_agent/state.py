"""
LangGraph state schema for readit-agent.
 
Two categories of fields:
 
  - In-memory, this run only: messages, readme_written, safe_to_proceed.
    These reset every time the graph runs and don't need to survive
    between separate GitHub Actions runs.
 
  - Persisted to disk (.readit-agent/summaries.json), loaded before the
    graph starts and saved back only after a full successful run:
    summaries, last_commit_id.
 
last_commit_id is intentionally only updated on success. If a run
crashes partway through, last_commit_id stays at its old value, so the
next scheduled run (2-3 hours later, per the cron trigger) simply
recomputes the diff against the same starting point and retries —
no crash-recovery or mid-run checkpointing logic needed.
"""

from typing import TypedDict, Dict, Annotated
from langgraph.graph.message import add_messages


class ReadItAgentState(TypedDict):
    messages: Annotated[list, add_messages]
    summaries: Dict[str, str]
    last_commit_id: str
    readme_written: bool
    safe_to_proceed: bool