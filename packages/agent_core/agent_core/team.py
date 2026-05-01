import json

from agent_core.team_session import TeamSession


class AgentTeam:
    def __init__(
        self,
        agents: list | None = None,
        max_turns: int = 10,
        team_mode: str = "round_robin",
        human_member=False,
        completion_policy: str = "reviewed",
        expose_tool_activity: bool = True,
    ):
        agents = agents or []
        if not agents:
            raise ValueError("agents must contain at least one agent")
        if max_turns < 1:
            raise ValueError("max_turns must be >= 1")
        if team_mode != "round_robin":
            raise ValueError("team_mode must be 'round_robin'")
        if human_member not in (False, True, "proxy"):
            raise ValueError("human_member must be False, True, or 'proxy'")
        if completion_policy not in ("single_done", "reviewed", "all_members", "supervised"):
            raise ValueError("invalid completion_policy")
        if completion_policy == "supervised" and human_member is False:
            raise ValueError("supervised completion_policy requires owner participation")

        self.agents = []
        for agent in agents:
            self.add_agent(agent)

        self.max_turns = max_turns
        self.team_mode = team_mode
        self.human_member = human_member
        self.completion_policy = completion_policy
        self.expose_tool_activity = expose_tool_activity

    def create_session(self, task: str) -> TeamSession:
        return TeamSession(self, task)

    def run(self, task: str):
        return self.create_session(task).run()

    def add_agent(self, agent) -> None:
        if self.get_agent(agent.name) is not None:
            raise ValueError(f"agent with name '{agent.name}' already exists")
        self.agents.append(agent)

    def remove_agent(self, name: str) -> bool:
        for idx, agent in enumerate(self.agents):
            if agent.name == name:
                del self.agents[idx]
                return True
        return False

    def get_agent(self, name: str):
        for agent in self.agents:
            if agent.name == name:
                return agent
        return None

    def list_agents(self) -> list:
        return list(self.agents)

    def _is_done_signal(self, text: str) -> bool:
        return (text or "").strip().lower() == "done"

    def _format_activity_entry(self, agent_name: str, event: dict) -> dict | None:
        event_type = event.get("type")
        title = event.get("title", "")
        details = event.get("details", {})

        if event_type == "tool_call":
            tool = details.get("tool") or details.get("tool_name", "unknown")
            args = details.get("args", {})
            summary = f"{agent_name} called tool {tool} with args {json.dumps(args, sort_keys=True)}"
        elif event_type == "observation":
            summary = f"{agent_name} observed {title}" if title else f"{agent_name} observed tool result"
        elif event_type == "validation_error":
            summary = f"{agent_name} saw validation error: {title or 'validation error'}"
        elif event_type == "error":
            summary = f"{agent_name} stopped with error: {title or 'error'}"
        else:
            return None

        return {"agent": agent_name, "type": event_type, "title": title, "summary": summary}
