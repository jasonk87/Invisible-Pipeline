from uuid import uuid4

from agent_core.types import TeamResult


class TeamSession:
    def __init__(self, team, task: str):
        self.team = team
        self.session_id = str(uuid4())
        self.original_task = task
        self.task_history = [task]
        self.transcript = []
        self.activity_log = []
        self.events = []
        self.turn_count = 0
        self.completed = False
        self.stop_reason = None

    def _build_prompt(self, active_agent) -> str:
        members = []
        for agent in self.team.agents:
            line = f"- {agent.name}"
            if getattr(agent, "role", None):
                line += f": Role: {agent.role}"
            if getattr(agent, "persona", None):
                line += f" Persona: {agent.persona}"
            members.append(line)
        team_members_text = "\n".join(members)
        current_agent_text = f"Name: {active_agent.name}"
        if getattr(active_agent, "role", None):
            current_agent_text += f"\nRole: {active_agent.role}"
        if getattr(active_agent, "persona", None):
            current_agent_text += f"\nPersona: {active_agent.persona}"
        try:
            from prompt_core import build_team_prompt

            return build_team_prompt(
                task_history=self.task_history,
                team_members_text=team_members_text,
                current_agent_text=current_agent_text,
                transcript=self.transcript,
                activity_log=self.activity_log if self.team.expose_tool_activity else None,
            )
        except ImportError:
            task_history_text = "\n".join(f"[{i+1}] {item}" for i, item in enumerate(self.task_history))
            transcript_text = "\n".join(f"{m['agent']}: {m['text']}" for m in self.transcript)
            parts = [
                f"TASK HISTORY:\n{task_history_text}",
                f"TEAM MEMBERS:\n{team_members_text}",
                f"CURRENT AGENT:\n{current_agent_text}",
                f"TEAM TRANSCRIPT:\n{transcript_text}",
            ]
            if self.team.expose_tool_activity and self.activity_log:
                activity_text = "\n".join(f"- {entry['agent']}: {entry['summary']}" for entry in self.activity_log)
                parts.append(f"TEAM ACTIVITY:\n{activity_text}")
            parts.append(
                "INSTRUCTION:\nContinue the team task. Respond with DONE only if the team task is complete under the team's completion policy."
            )
            return "\n\n".join(parts)

    def _result(self, text, completed, stop_reason) -> TeamResult:
        self.completed = completed
        self.stop_reason = stop_reason
        return TeamResult(
            text=text,
            completed=completed,
            stop_reason=stop_reason,
            transcript=self.transcript,
            events=self.events,
            metadata={"activity_log": self.activity_log, "session_id": self.session_id},
        )

    def run(self) -> TeamResult:
        done_votes = set()
        pending_done = False

        for _ in range(self.team.max_turns):
            agent = self.team.agents[self.turn_count % len(self.team.agents)]
            context_text = self._build_prompt(agent)
            result = agent.generate(context_text)

            self.transcript.append({"agent": agent.name, "text": result.text})
            self.events.append({"type": "team_turn", "title": f"{agent.name} responded", "details": {"text": result.text}})

            if self.team.expose_tool_activity:
                agent_events = (result.metadata or {}).get("events", [])
                added = 0
                for event in agent_events:
                    entry = self.team._format_activity_entry(agent.name, event)
                    if entry is not None:
                        self.activity_log.append(entry)
                        added += 1
                if added:
                    self.events.append(
                        {"type": "team_activity", "title": f"Recorded activity from {agent.name}", "details": {"count": added}}
                    )

            is_done = self.team._is_done_signal(result.text)
            if is_done:
                self.events.append(
                    {
                        "type": "done_signal",
                        "title": f"{agent.name} signaled DONE",
                        "details": {"policy": self.team.completion_policy},
                    }
                )

            self.turn_count += 1
            policy = self.team.completion_policy
            if policy == "single_done" and is_done:
                self.events.append({"type": "completion", "title": "Team completed", "details": {"stop_reason": "single_done"}})
                return self._result("DONE", True, "single_done")
            if policy == "reviewed":
                if pending_done:
                    if is_done:
                        self.events.append({"type": "completion", "title": "Team completed", "details": {"stop_reason": "reviewed"}})
                        return self._result("DONE", True, "reviewed")
                    pending_done = False
                elif is_done:
                    pending_done = True
            if policy == "all_members" and is_done:
                done_votes.add(agent.name)
                if len(done_votes) == len(self.team.agents):
                    self.events.append(
                        {"type": "completion", "title": "Team completed", "details": {"stop_reason": "all_members_done"}}
                    )
                    return self._result("DONE", True, "all_members_done")
            if policy == "supervised" and self.team.human_member == "proxy" and is_done and agent.name == "human_proxy":
                self.events.append({"type": "completion", "title": "Team completed", "details": {"stop_reason": "supervised_done"}})
                return self._result("DONE", True, "supervised_done")

        self.events.append({"type": "max_turns_reached", "title": "Max turns reached", "details": {"max_turns": self.team.max_turns}})
        return self._result(self.transcript[-1]["text"] if self.transcript else "", False, "max_turns_reached")

    def restart(self, task: str | None = None):
        if task is not None:
            self.original_task = task
            self.task_history = [task]
        else:
            self.task_history = [self.original_task]
        self.transcript = []
        self.activity_log = []
        self.events = []
        self.turn_count = 0
        self.completed = False
        self.stop_reason = None
        return self

    def continue_run(self, new_task: str) -> TeamResult:
        self.task_history.append(new_task)
        self.completed = False
        self.stop_reason = None
        return self.run()
