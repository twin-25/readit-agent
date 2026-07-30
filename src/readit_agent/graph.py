from readit_agent.state import ReadItAgentState
from readit_agent.safety_tools import *
from langchain_core.messages import ToolMessage
#------------- Nodes------------------

def safety_gate_node(state: ReadItAgentState) -> dict:
  """Confirm its safe to proceed i.e no human tocuched it then creates a branch  so every downstream action lands on the right brach automatically.   """
  if not is_safe_to_proceed():
      return {"safe_to_proceed": False}

  branch_created = create_branch()
  if not branch_created:
      return {"safe_to_proceed": False}

  return {"safe_to_proceed": True}


def make_agent_reasoning_node(llm_with_tools):
  
  """Closure over llm_with_tools, same pattern as make_summarize_file
    in decision_tools.py — the LLM object can't be a normal node
    argument since LangGraph only ever passes (state) into a node.
 
    Deliberately simple: this node doesn't know or construct any
    prompt text. All of that (the system prompt, old summaries) is
    baked into messages ONCE, at the very start of the run, in cli.py
    — before the graph ever starts. Since messages only ever grows,
    never resets, that first message is still there on every later
    turn without this node needing to repeat or reconstruct anything."""
  
  def agent_reasoning_node(state: ReadItAgentState) -> dict:
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)

    return {"messages": [response]}

  return agent_reasoning_node

def make_tool_execution_node(tools):
  """Closure over llm_with_tools, same pattern as make_summarize_file
    in decision_tools.py — the LLM object can't be a normal node
    argument since LangGraph only ever passes (state) into a node.
 
    Deliberately simple: this node doesn't know or construct any
    prompt text. All of that (the system prompt, old summaries) is
    baked into messages ONCE, at the very start of the run, in cli.py
    — before the graph ever starts. Since messages only ever grows,
    never resets, that first message is still there on every later
    turn without this node needing to repeat or reconstruct anything."""
 
    def agent_reasoning_node(state: ReadItAgentState) -> dict:
        messages = state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}
 
    return agent_reasoning_node
 
 
def make_tool_execution_node(tools):
  """Closure over the tool list, same pattern as
    make_agent_reasoning_node. Builds tool_registry ONCE (name -> tool
    object), so every call just does a dict lookup rather than
    rebuilding the mapping each turn.
 
    Also handles the deterministic bookkeeping: if summarize_file was
    the tool that ran, its result gets merged into state["summaries"].
    The merge happens with {**old, **new} rather than state["summaries"]
    being returned partially, because "summaries" has no reducer in
    state.py (unlike messages/add_messages) — LangGraph's default
    behavior for un-annotated fields is to REPLACE the old value
    entirely with whatever a node returns, not merge it. Returning only
    this turn's new summaries would silently wipe out every summary
    from previous turns and previous runs."""

  tool_registry = {tool.name: tool for tool in tools}
  def tool_execution_node(state: ReadItAgentState) -> dict:
    tool_calls = state["messages"][-1].tool_calls
    results = []
    new_summaries = {}

    for tool_call in tool_calls:
      tool_name = tool_call["name"]
      tool = tool_registry[tool_name]
      result = ToolMessage(content=tool.invoke(tool_call["args"]), tool_call_id=tool_call["id"])
      if tool_name == "summarize_file":
        new_summaries[tool_call["args"]["path"]] = result.content

      results.append(result)

    merged_summaries = {**state["summaries"], **new_summaries}
    return {"messages": results, "summaries" : merged_summaries}

  return tool_execution_node
     
        


#------------- Edges ------------------

def route_after_safety_gate(state: ReadItAgentState) -> str:

  """Reads the saftey_gate_node wrote and route based on the results
  """
  if not state["safe_to_proceed"]:
      return "stop"

  return "continue"

def route_after_agent_reasoning(state: ReadItAgentState) -> str:

  """
  reads teh fast appended message to check for tool call and routes based on the result
  """

  last_message = state["messages"][-1]
  if last_message.tool_calls:
     return "continue_tools"

  return "done" 