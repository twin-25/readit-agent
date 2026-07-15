"""Entrypoint: parse env, resolve repo context, kick off the graph."""
 
from dotenv import load_dotenv
 
from readit_agent.llm_config import get_llm
 
 
def main():
    load_dotenv()
    llm = get_llm()
    print(f"readit-agent starting with: {llm.__class__.__name__}")
    # graph.py isn't wired up yet — this is the current stopping point.
 
 
if __name__ == "__main__":
    main()