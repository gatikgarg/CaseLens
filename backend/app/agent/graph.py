from langgraph.graph import END, StateGraph

from backend.app.agent import nodes
from backend.app.agent.state import AgentState

MAX = {"fast": 4, "thorough": 8}


def after_plan(s):
    return "refuse" if s["route"] == "out_of_scope" else "agent"


def after_agent(s):
    wants_tools = bool(s["transcript"][-1].get("tool_calls"))
    return "exec_tools" if wants_tools and s["iterations"] < MAX[s["options"]["effort"]] else "compose"


def after_verify(s):
    return "compose" if (not s["verification"]["ok"] and s.get("repair_attempts", 0) < 1) else END


g = StateGraph(AgentState)
for name, fn in [
    ("plan", nodes.plan_node),
    ("agent", nodes.agent_node),
    ("exec_tools", nodes.exec_tools_node),
    ("compose", nodes.compose_node),
    ("verify", nodes.verify_node),
    ("refuse", nodes.refuse_node),
]:
    g.add_node(name, fn)
g.set_entry_point("plan")
g.add_conditional_edges("plan", after_plan, {"agent": "agent", "refuse": "refuse"})
g.add_conditional_edges("agent", after_agent, {"exec_tools": "exec_tools", "compose": "compose"})
g.add_edge("exec_tools", "agent")
g.add_edge("compose", "verify")
g.add_conditional_edges("verify", after_verify, {"compose": "compose", END: END})
g.add_edge("refuse", END)
agent = g.compile()

