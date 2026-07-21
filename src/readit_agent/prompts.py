"""
Prompt text used by decision_tools.py and graph.py.

Kept as plain Python string constants (not .txt files) so they're
automatically bundled by pip install, same as any other module under
src/readit_agent/ — no extra packaging config needed.
"""

SUMMARIZE_FILE_PROMPT = """
You are analyzing a source file from a software project.
File path: {path}
Summarize the file in 2 to 3 concise sentences. Explain:
1. The file's main purpose within the project
2. Its primary responsibilities or the type of functionality it provides
3. How it contributes to the broader project, when that can be inferred
Keep the summary high-level. Do not describe exact syntax, individual function signatures, internal algorithms, imports, or line-by-line implementation details unless one detail is essential to understanding the file's purpose.
Use the file path as context, especially when the file is short or contains limited information. Do not invent functionality that cannot be supported by the path or content. If the file is empty or only performs package initialization, state that clearly.
Write in plain prose only — no markdown, no bullet points, no headers, no bold text.
File content:
---
{content}
---
Return only the summary.
"""