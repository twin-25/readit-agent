from pathlib import Path
from typing import List

from langchain_core.tools import tool

EXCLUDED_DIRS = {
  ".git", "venv", ".venv", "env", "node_modules",
    "__pycache__", ".pytest_cache", "dist", "build",
    ".next", ".idea", ".vscode", "site-packages",
}

@tool
def list_files(path: str)-> str:
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
    Returns an error message string if the file doesn't exist
  """


  file_path = Path(path)

  try:
    content = file_path.read_text(encoding="utf-8")
    return content

  except FileNotFoundError:
    content = "No file found at the given path"
    return content