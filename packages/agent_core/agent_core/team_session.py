import json
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

    def _team_members_text(self):
        members = []
        for agent in self.team.agents:
            line = f"- {agent.name}"
            if getattr(agent, "role", None):
                line += f": Role: {agent.role}"
            if getattr(agent, "persona", None):
                line += f" Persona: {agent.persona}"
            members.append(line)
        return "\n".join(members)

    def _build_prompt(self, active_agent) -> str:
        team_members_text = self._team_members_text()
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
            history = "\n".join(f"[{i+1}] {task}" for i, task in enumerate(self.task_history))
            transcript_text = "\n".join(f"{e.get('agent', '')}: {e.get('text', '')}" for e in self.transcript)
            activity_text = "\n".join(f"- {e.get('agent', '')}: {e.get('summary', '')}" for e in self.activity_log)
            parts = [f"TASK HISTORY:\n{history}", f"TEAM MEMBERS:\n{team_members_text}", f"CURRENT AGENT:\n{current_agent_text}"]
            if transcript_text:
                parts.append(f"TEAM TRANSCRIPT:\n{transcript_text}")
            if self.team.expose_tool_activity and activity_text:
                parts.append(f"TEAM ACTIVITY:\n{activity_text}")
            parts.append("INSTRUCTION:\nContinue the team task. Respond with DONE only if the team task is complete under the team's completion policy.")
            return "\n\n".join(parts)

    def _build_orchestrator_prompt(self):
        choices = ", ".join(agent.name for agent in self.team.agents)
        return self._build_prompt(active_agent=self.team.orchestrator) + (
            "\n\nORCHESTRATOR INSTRUCTION:\n"
            "You are responsible for coordinating a team of agents.\n\n"
            "Select the most appropriate agent for the next step based on:\n"
            "- the current state of the task\n"
            "- what has already been done\n"
            "- what is still missing\n"
            "- each agent's role and persona\n\n"
            "Use different agents when appropriate.\n"
            "Do not repeatedly select the same agent unless it is clearly necessary.\n\n"
            "Only return done=true when:\n"
            "- the task is fully complete\n"
            "- no further agent contribution is needed\n"
            "- the final answer is ready for the user\n\n"
            "Valid next_agent choices:\n"
            f"{choices}\n\n"
            "Return ONLY valid JSON.\n\n"
            "To choose an agent:\n"
            '{"next_agent": "agent_name", "instruction": "specific instruction for that agent", "reason": "why this agent is the right next choice"}\n\n'
            "To finish:\n"
            '{"done": true, "final_answer": "final answer text"}'
        )

    def _build_worker_prompt(self, worker, instruction: str):
        return self._build_prompt(active_agent=worker) + f"\n\nORCHESTRATOR TASK:\n{instruction or self.original_task}"

    def _parse_orchestrator_decision(self, text: str) -> dict:
        return json.loads(text)

    def _record_activity(self, agent_name, result):
        if not self.team.expose_tool_activity:
            return
        agent_events = (result.metadata or {}).get("events", [])
        added = 0
        for event in agent_events:
            entry = self.team._format_activity_entry(agent_name, event)
            if entry is not None:
                self.activity_log.append(entry)
                added += 1
        if added:
            self.events.append({"type": "team_activity", "title": f"Recorded activity from {agent_name}", "details": {"count": added}})

    def _result(self, text, completed, stop_reason) -> TeamResult:
        self.completed = completed
        self.stop_reason = stop_reason
        return TeamResult(text=text, completed=completed, stop_reason=stop_reason, transcript=self.transcript, events=self.events, metadata={"activity_log": self.activity_log, "session_id": self.session_id})

    def _run_round_robin(self) -> TeamResult:
        done_votes = set(); pending_done = False
        for _ in range(self.team.max_turns):
            agent = self.team.agents[self.turn_count % len(self.team.agents)]
            result = agent.generate(self._build_prompt(agent))
            self.transcript.append({"agent": agent.name, "text": result.text})
            self.events.append({"type": "team_turn", "title": f"{agent.name} responded", "details": {"text": result.text}})
            self._record_activity(agent.name, result)
            is_done = self.team._is_done_signal(result.text)
            if is_done:
                self.events.append({"type": "done_signal", "title": f"{agent.name} signaled DONE", "details": {"policy": self.team.completion_policy}})
            self.turn_count += 1
            p = self.team.completion_policy
            if p == "single_done" and is_done:
                self.events.append({"type": "completion", "title": "Team completed", "details": {"stop_reason": "single_done"}})
                return self._result("DONE", True, "single_done")
            if p == "reviewed":
                if pending_done:
                    if is_done:
                        self.events.append({"type": "completion", "title": "Team completed", "details": {"stop_reason": "reviewed"}})
                        return self._result("DONE", True, "reviewed")
                    pending_done = False
                elif is_done:
                    pending_done = True
            if p == "all_members" and is_done:
                done_votes.add(agent.name)
                if len(done_votes) == len(self.team.agents):
                    self.events.append({"type": "completion", "title": "Team completed", "details": {"stop_reason": "all_members_done"}})
                    return self._result("DONE", True, "all_members_done")
            if p == "supervised" and self.team.human_member == "proxy" and is_done and agent.name == "human_proxy":
                self.events.append({"type": "completion", "title": "Team completed", "details": {"stop_reason": "supervised_done"}})
                return self._result("DONE", True, "supervised_done")
        self.events.append({"type": "max_turns_reached", "title": "Max turns reached", "details": {"max_turns": self.team.max_turns}})
        return self._result(self.transcript[-1]["text"] if self.transcript else "", False, "max_turns_reached")

    def _run_orchestrator(self) -> TeamResult:
        for _ in range(self.team.max_turns):
            decision_text = self.team.orchestrator.generate(self._build_orchestrator_prompt()).text
            try:
                decision = self._parse_orchestrator_decision(decision_text)
            except Exception:
                self.events.append({"type": "orchestrator_error", "title": "Orchestrator returned invalid JSON", "details": {}})
                return self._result(self.transcript[-1]["text"] if self.transcript else "", False, "orchestrator_invalid_json")
            if decision.get("done") is True:
                self.events.append({"type": "orchestrator_done", "title": "Orchestrator completed the task", "details": {}})
                return self._result(decision.get("final_answer", ""), True, "orchestrator_done")
            next_agent = decision.get("next_agent")
            instruction = decision.get("instruction") or self.original_task
            reason = decision.get("reason", "")
            worker = self.team.get_agent(next_agent)
            if worker is None:
                self.events.append({"type": "orchestrator_error", "title": "Orchestrator selected unknown agent", "details": {"next_agent": next_agent}})
                return self._result(self.transcript[-1]["text"] if self.transcript else "", False, "orchestrator_unknown_agent")
            self.events.append({"type": "orchestrator_decision", "title": f"Orchestrator selected {next_agent}", "details": {"next_agent": next_agent, "instruction": instruction, "reason": reason}})
            result = worker.generate(self._build_worker_prompt(worker, instruction))
            self.transcript.append({"agent": worker.name, "text": result.text})
            self.events.append({"type": "team_turn", "title": f"{worker.name} responded", "details": {"text": result.text}})
            self._record_activity(worker.name, result)
            self.turn_count += 1
        self.events.append({"type": "max_turns_reached", "title": "Max turns reached", "details": {"max_turns": self.team.max_turns}})
        return self._result(self.transcript[-1]["text"] if self.transcript else "", False, "max_turns_reached")

    def run(self) -> TeamResult:
        if self.team.team_mode == "orchestrator":
            return self._run_orchestrator()
        return self._run_round_robin()

    def restart(self, task: str | None = None):
        if task is not None:
            self.original_task = task
            self.task_history = [task]
        else:
            self.task_history = [self.original_task]
        self.transcript = []; self.activity_log = []; self.events = []; self.turn_count = 0; self.completed = False; self.stop_reason = None
        return self

    def continue_run(self, new_task: str) -> TeamResult:
        self.task_history.append(new_task); self.completed = False; self.stop_reason = None
        return self.run()
