"""
Chooses which LLM provider and model the agent runs on.

Selection happens entirely through .env — no CLI flags, matching the
zero-argument CLI design (see cli.py). Set LLM_PROVIDER and, optionally,
LLM_MODEL in your .env file.

graph.py never imports this directly with a specific provider in mind —
it just receives whatever object get_llm() returns and calls .invoke() /
.bind_tools() on it. Every provider class below implements that same
interface, so the graph's nodes stay provider-agnostic.
"""

import os

SUPPORTED_PROVIDERS = ("groq", "anthropic", "openai", "google")

# Sensible, low-cost defaults per provider — used only if LLM_MODEL is unset.
# Worth checking these are still current models before you ship this.
DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "google": "gemini-2.0-flash",
}

# Which env var holds the API key for each provider.
API_KEY_ENV_VARS = {
    "groq": "GROQ_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}


def get_llm():
    """Build and return a LangChain chat model based on .env config."""
    provider = os.environ.get("LLM_PROVIDER", "groq").strip().lower()

    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{provider}'. "
            f"Supported providers: {', '.join(SUPPORTED_PROVIDERS)}"
        )

    key_var = API_KEY_ENV_VARS[provider]
    api_key = os.environ.get(key_var)
    if not api_key:
        raise ValueError(
            f"LLM_PROVIDER is set to '{provider}' but {key_var} is missing "
            f"from your .env file."
        )

    model = os.environ.get("LLM_MODEL") or DEFAULT_MODELS[provider]

    if provider == "groq":
        # Core dependency — always installed, no try/except needed.
        from langchain_groq import ChatGroq
        return ChatGroq(model=model, api_key=api_key)

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as e:
            raise ImportError(
                "LLM_PROVIDER is set to 'anthropic' but langchain-anthropic "
                "isn't installed. Run: pip install -e '.[anthropic]'"
            ) from e
        return ChatAnthropic(model=model, api_key=api_key)

    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            raise ImportError(
                "LLM_PROVIDER is set to 'openai' but langchain-openai "
                "isn't installed. Run: pip install -e '.[openai]'"
            ) from e
        return ChatOpenAI(model=model, api_key=api_key)

    if provider == "google":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError as e:
            raise ImportError(
                "LLM_PROVIDER is set to 'google' but langchain-google-genai "
                "isn't installed. Run: pip install -e '.[google]'"
            ) from e
        return ChatGoogleGenerativeAI(model=model, google_api_key=api_key)