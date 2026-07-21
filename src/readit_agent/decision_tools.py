from pathlib import Path
from typing import List
import subprocess

from langchain_core.tools import tool

from readit_agent.prompts import SUMMARIZE_FILE_PROMPT

EXCLUDED_DIRS = {
  ".git", "venv", ".venv", "env", "node_modules",
    "__pycache__", ".pytest_cache", "dist", "build",
    ".next", ".idea", ".vscode", "site-packages", ".env"
}

@tool
def list_files(path: str)-> List[str]:
  """List all files in the repository, skipping dependency, build,
    and version-control folders (e.g. node_modules, .git, venv).
    Returns paths relative to the given directory, e.g. 'src/app.py'.
    Use this first to see the repo's structure before reading any file."""
  
  dir_path = Path(path)
  results = []

  for file_path in dir_path.rglob("*"):
    if not file_path.is_file():
      continue

    if set(file_path.parts) & EXCLUDED_DIRS:
      continue

    results.append(str(file_path.relative_to(dir_path)))

  return results


@tool
def read_file(path: str) -> str:
  """
  Read the exact, full content of a single file. Use this when you
    need ground truth — e.g. the exact install command, an exact function
    signature, or precise usage syntax — rather than relying on a
    paraphrased summary from summarize_file, which may lose exact wording.
    Returns an error message string if the file doesn't exist.
  """


  file_path = Path(path)

  try:
    content = file_path.read_text(encoding="utf-8")
    return content

  except FileNotFoundError:
    content = "No file found at the given path"
    return content
  

@tool
def get_git_diff(last_commit_id: str) ->List[str]:
  """
  Get the list of files that changed since the last time README was generated. Use this after the first run , instead of list_files, so you only investigate what actually changed rather than re-reading the whole repo."""

  result = subprocess.run(
    ["git", "diff", "--name-only", last_commit_id, "HEAD"],
    capture_output=True,
    text=True,
  )

  if result.stdout == "":
    return []
  return result.stdout.strip().split("\n")


def make_summarize_file(llm):
  @tool
  def summarize_file(path: str)->str:
    """
    Read a file and generate a short summary of what it does.
    Use this to understand a file's purpose cheaply, without needing
    to re-read its full content on future turns. The summary gets
    cached, so you won't need to call this again for the same file
    unless it changes.
    """
    content = read_file.invoke({"path": path})
    prompt = SUMMARIZE_FILE_PROMPT.format(path=path, content=content)
    response = llm.invoke(prompt)
    return response.content

  return summarize_file


@tool
def write_readme(content: str) -> str:
  """
  Write the given content to README.md. Call this once you've gathered
  enough summaries and have generated the full README text yourself as
  plain markdown. This is the last content-decision step — after this,
  the actual git commit and pull request happen automatically.
  """
  with open("README.md", "w") as f:
    f.write(content)

  return "wrote the README successfully"