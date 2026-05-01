import unittest

from agent_core import AgentTeam


class StubResult:
    def __init__(self, text, metadata=None):
        self.text = text
        self.completed = False
        self.stop_reason = "continue"
        self.metadata = metadata or {}


class StubAgent:
    def __init__(self, name, outputs, metadata_events=None, role=None, persona=None):
        self.name = name
        self.role = role
        self.persona = persona
        self.outputs = outputs
        self.metadata_events = metadata_events or []
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        text = self.outputs.pop(0)
        events = self.metadata_events.pop(0) if self.metadata_events else []
        return StubResult(text, metadata={"events": events})


class AgentTeamTests(unittest.TestCase):
    def test_constructor_defaults_completion_policy_reviewed(self):
        team = AgentTeam([StubAgent("a1", ["DONE"])])
        self.assertEqual(team.completion_policy, "reviewed")

    def test_invalid_completion_policy_raises(self):
        with self.assertRaises(ValueError):
            AgentTeam([StubAgent("a1", ["x"])], completion_policy="bad")

    def test_invalid_team_mode_raises(self):
        with self.assertRaises(ValueError):
            AgentTeam([StubAgent("a1", ["x"])], team_mode="moderated")

    def test_supervised_with_human_member_false_raises(self):
        with self.assertRaises(ValueError):
            AgentTeam([StubAgent("a1", ["x"])], completion_policy="supervised", human_member=False)

    def test_add_agent_works(self):
        team = AgentTeam([StubAgent("a1", ["x"])])
        team.add_agent(StubAgent("a2", ["y"]))
        self.assertEqual(len(team.list_agents()), 2)

    def test_duplicate_add_agent_raises(self):
        team = AgentTeam([StubAgent("a1", ["x"])])
        with self.assertRaises(ValueError):
            team.add_agent(StubAgent("a1", ["y"]))

    def test_remove_agent_works(self):
        team = AgentTeam([StubAgent("a1", ["x"]), StubAgent("a2", ["y"])])
        self.assertTrue(team.remove_agent("a1"))
        self.assertFalse(team.remove_agent("missing"))

    def test_get_agent_and_list_agents(self):
        a1 = StubAgent("a1", ["x"])
        team = AgentTeam([a1])
        self.assertIs(team.get_agent("a1"), a1)
        self.assertIsNone(team.get_agent("none"))
        listed = team.list_agents()
        self.assertEqual(len(listed), 1)
        self.assertIsNot(listed, team.agents)

    def test_done_detection_rules(self):
        team = AgentTeam([StubAgent("a1", ["x"])])
        self.assertTrue(team._is_done_signal("DONE"))
        self.assertTrue(team._is_done_signal("done"))
        self.assertFalse(team._is_done_signal("Here is DONE"))

    def test_single_done_stops_immediately(self):
        team = AgentTeam([StubAgent("a1", ["DONE"]), StubAgent("a2", ["x"])], completion_policy="single_done", max_turns=3)
        result = team.run("task")
        self.assertTrue(result.completed)
        self.assertEqual(result.stop_reason, "single_done")
        self.assertEqual(len(result.transcript), 1)

    def test_reviewed_requires_next_agent_done(self):
        team = AgentTeam(
            [StubAgent("a1", ["DONE"]), StubAgent("a2", ["done"])],
            completion_policy="reviewed",
            max_turns=3,
        )
        result = team.run("task")
        self.assertTrue(result.completed)
        self.assertEqual(result.stop_reason, "reviewed")

    def test_reviewed_clears_pending_when_next_not_done(self):
        team = AgentTeam(
            [StubAgent("a1", ["DONE", "DONE"]), StubAgent("a2", ["not done", "still not done"])],
            completion_policy="reviewed",
            max_turns=4,
        )
        result = team.run("task")
        self.assertFalse(result.completed)
        self.assertEqual(result.stop_reason, "max_turns_reached")

    def test_all_members_waits_for_all_agents(self):
        team = AgentTeam(
            [StubAgent("a1", ["DONE"]), StubAgent("a2", ["DONE"]), StubAgent("a3", ["DONE"])],
            completion_policy="all_members",
            max_turns=3,
        )
        result = team.run("task")
        self.assertTrue(result.completed)
        self.assertEqual(result.stop_reason, "all_members_done")

    def test_supervised_accepts_human_proxy_done(self):
        team = AgentTeam(
            [StubAgent("a1", ["DONE"]), StubAgent("human_proxy", ["DONE"])],
            completion_policy="supervised",
            human_member="proxy",
            max_turns=2,
        )
        result = team.run("task")
        self.assertTrue(result.completed)
        self.assertEqual(result.stop_reason, "supervised_done")

    def test_supervised_human_member_true_no_auto_complete(self):
        team = AgentTeam(
            [StubAgent("a1", ["DONE", "DONE"])],
            completion_policy="supervised",
            human_member=True,
            max_turns=2,
        )
        result = team.run("task")
        self.assertFalse(result.completed)
        self.assertEqual(result.stop_reason, "max_turns_reached")

    def test_done_signal_and_completion_events(self):
        team = AgentTeam([StubAgent("a1", ["DONE"])], completion_policy="single_done", max_turns=1)
        result = team.run("task")
        event_types = [event["type"] for event in result.events]
        self.assertIn("done_signal", event_types)
        self.assertIn("completion", event_types)

    def test_max_turns_reached_event_emitted(self):
        team = AgentTeam([StubAgent("a1", ["x"])], completion_policy="single_done", max_turns=1)
        result = team.run("task")
        self.assertEqual(result.stop_reason, "max_turns_reached")
        self.assertEqual(result.events[-1]["type"], "max_turns_reached")

    def test_tool_call_observation_validation_error_error_become_activity_entries(self):
        events = [[
            {"type": "tool_call", "details": {"tool": "read_file", "args": {"path": "main.py"}}},
            {"type": "observation", "title": "read_file result: ok=True"},
            {"type": "validation_error", "title": "missing required arg path"},
            {"type": "error", "title": "tool_validation_failed"},
        ]]
        team = AgentTeam([StubAgent("builder", ["x"], metadata_events=events)], max_turns=1)
        result = team.run("task")
        activity = result.metadata["activity_log"]
        self.assertEqual([entry["type"] for entry in activity], ["tool_call", "observation", "validation_error", "error"])

    def test_team_activity_included_in_next_prompt_when_enabled(self):
        a1 = StubAgent("builder", ["x"], metadata_events=[[{"type": "tool_call", "details": {"tool": "read_file", "args": {"path": "main.py"}}}]])
        a2 = StubAgent("reviewer", ["y"])
        team = AgentTeam([a1, a2], max_turns=2, expose_tool_activity=True)
        team.run("task")
        self.assertIn("TEAM ACTIVITY:", a2.prompts[0])
        self.assertIn("builder called tool read_file", a2.prompts[0])

    def test_team_activity_omitted_when_disabled(self):
        a1 = StubAgent("builder", ["x"], metadata_events=[[{"type": "tool_call", "details": {"tool": "read_file", "args": {"path": "main.py"}}}]])
        a2 = StubAgent("reviewer", ["y"])
        team = AgentTeam([a1, a2], max_turns=2, expose_tool_activity=False)
        team.run("task")
        self.assertNotIn("TEAM ACTIVITY:", a2.prompts[0])

    def test_activity_log_present_in_team_result_metadata(self):
        a1 = StubAgent("builder", ["x"], metadata_events=[[{"type": "tool_call", "details": {"tool": "read_file", "args": {"path": "main.py"}}}]])
        team = AgentTeam([a1], max_turns=1)
        result = team.run("task")
        self.assertIn("activity_log", result.metadata)
        self.assertEqual(result.metadata["activity_log"][0]["agent"], "builder")

    def test_transcript_separate_from_activity(self):
        a1 = StubAgent("builder", ["builder response"], metadata_events=[[{"type": "tool_call", "details": {"tool": "read_file", "args": {"path": "main.py"}}}]])
        team = AgentTeam([a1], max_turns=1)
        result = team.run("task")
        self.assertEqual(result.transcript[0]["text"], "builder response")
        self.assertIn("called tool", result.metadata["activity_log"][0]["summary"])

    def test_team_activity_event_emitted_when_recorded(self):
        a1 = StubAgent("builder", ["x"], metadata_events=[[{"type": "tool_call", "details": {"tool": "read_file", "args": {"path": "main.py"}}}]])
        team = AgentTeam([a1], max_turns=1)
        result = team.run("task")
        self.assertIn("team_activity", [e["type"] for e in result.events])

    def test_create_session_returns_unique_ids(self):
        team = AgentTeam([StubAgent("a1", ["x", "x"])], max_turns=1)
        s1 = team.create_session("task 1")
        s2 = team.create_session("task 2")
        self.assertNotEqual(s1.session_id, s2.session_id)

    def test_team_run_creates_independent_sessions(self):
        team = AgentTeam([StubAgent("a1", ["DONE", "DONE"])], completion_policy="single_done", max_turns=1)
        r1 = team.run("task 1")
        r2 = team.run("task 2")
        self.assertNotEqual(r1.metadata["session_id"], r2.metadata["session_id"])

    def test_session_run_populates_transcript_activity_events(self):
        a1 = StubAgent("builder", ["x"], metadata_events=[[{"type": "tool_call", "details": {"tool": "read_file", "args": {"path": "main.py"}}}]])
        session = AgentTeam([a1], max_turns=1).create_session("task")
        session.run()
        self.assertEqual(len(session.transcript), 1)
        self.assertEqual(len(session.activity_log), 1)
        self.assertGreaterEqual(len(session.events), 2)

    def test_continue_run_preserves_prior_transcript(self):
        agent = StubAgent("a1", ["x", "y"])
        session = AgentTeam([agent], max_turns=1).create_session("task")
        session.run()
        session.continue_run("next")
        self.assertEqual([t["text"] for t in session.transcript], ["x", "y"])

    def test_continue_run_appends_new_task(self):
        session = AgentTeam([StubAgent("a1", ["x", "y"])], max_turns=1).create_session("task")
        session.run()
        session.continue_run("new instruction")
        self.assertEqual(session.task_history, ["task", "new instruction"])

    def test_continue_run_resets_completion_state(self):
        team = AgentTeam([StubAgent("a1", ["DONE", "x"])], completion_policy="single_done", max_turns=1)
        session = team.create_session("task")
        first = session.run()
        self.assertTrue(first.completed)
        second = session.continue_run("continue")
        self.assertFalse(second.completed)

    def test_session_isolation(self):
        team = AgentTeam([StubAgent("a1", ["x", "y"])], max_turns=1)
        s1 = team.create_session("task 1")
        s2 = team.create_session("task 2")
        s1.run()
        self.assertEqual(len(s1.transcript), 1)
        self.assertEqual(len(s2.transcript), 0)

    def test_team_result_includes_session_id(self):
        result = AgentTeam([StubAgent("a1", ["x"])], max_turns=1).run("task")
        self.assertIn("session_id", result.metadata)

    def test_restart_preserves_session_id(self):
        session = AgentTeam([StubAgent("a1", ["x", "y"])], max_turns=1).create_session("task")
        original_id = session.session_id
        session.run()
        session.restart()
        self.assertEqual(session.session_id, original_id)

    def test_restart_clears_transcript_activity_events(self):
        a1 = StubAgent("builder", ["x"], metadata_events=[[{"type": "tool_call", "details": {"tool": "read_file", "args": {"path": "main.py"}}}]])
        session = AgentTeam([a1], max_turns=1).create_session("task")
        session.run()
        session.restart()
        self.assertEqual(session.transcript, [])
        self.assertEqual(session.activity_log, [])
        self.assertEqual(session.events, [])

    def test_restart_resets_turn_count_and_completion_state(self):
        session = AgentTeam([StubAgent("a1", ["DONE"])], completion_policy="single_done", max_turns=1).create_session("task")
        session.run()
        session.restart()
        self.assertEqual(session.turn_count, 0)
        self.assertFalse(session.completed)
        self.assertIsNone(session.stop_reason)

    def test_restart_without_task_restores_original_task_history(self):
        session = AgentTeam([StubAgent("a1", ["x", "y"])], max_turns=1).create_session("task")
        session.continue_run("next")
        session.restart()
        self.assertEqual(session.task_history, ["task"])

    def test_restart_with_new_task_replaces_original_and_history(self):
        session = AgentTeam([StubAgent("a1", ["x"])], max_turns=1).create_session("task")
        session.restart("better task")
        self.assertEqual(session.original_task, "better task")
        self.assertEqual(session.task_history, ["better task"])

    def test_session_can_run_again_after_restart(self):
        session = AgentTeam([StubAgent("a1", ["x", "y"])], max_turns=1).create_session("task")
        first = session.run()
        self.assertEqual(first.text, "x")
        session.restart()
        second = session.run()
        self.assertEqual(second.text, "y")
        self.assertEqual(len(second.transcript), 1)

    def test_team_members_and_current_agent_sections_present(self):
        a1 = StubAgent("planner", ["x"], role="Creates plans.", persona="Concise.")
        a2 = StubAgent("builder", ["y"], role="Implements code.")
        team = AgentTeam([a1, a2], max_turns=2)
        team.run("task")
        prompt = a2.prompts[0]
        self.assertIn("TEAM MEMBERS:", prompt)
        self.assertIn("- planner: Role: Creates plans. Persona: Concise.", prompt)
        self.assertIn("- builder: Role: Implements code.", prompt)
        self.assertIn("CURRENT AGENT:", prompt)
        self.assertIn("Name: builder", prompt)
        self.assertIn("Role: Implements code.", prompt)

    def test_current_agent_persona_omitted_when_none(self):
        a1 = StubAgent("a1", ["x"], role="Role A")
        a2 = StubAgent("a2", ["y"], role="Role B", persona=None)
        team = AgentTeam([a1, a2], max_turns=2)
        team.run("task")
        current = a2.prompts[0].split("CURRENT AGENT:")[-1]
        self.assertNotIn("Persona:", current)


class OrchestratorModeTests(unittest.TestCase):
    def test_orchestrator_mode_requires_orchestrator(self):
        with self.assertRaises(ValueError):
            AgentTeam([StubAgent("a1", ["x"])], team_mode="orchestrator")

    def test_valid_orchestrator_stored(self):
        manager = StubAgent("manager", ['{"done": true, "final_answer": "ok"}'])
        team = AgentTeam([StubAgent("a1", ["x"])], team_mode="orchestrator", orchestrator=manager)
        self.assertIs(team.orchestrator, manager)

    def test_orchestrator_selects_next_agent_and_updates_transcript(self):
        manager = StubAgent("manager", ['{"next_agent":"builder","instruction":"Do work","reason":"needed"}', '{"done": true, "final_answer": "complete"}'])
        builder = StubAgent("builder", ["built result"], role="Implements code.")
        planner = StubAgent("planner", ["plan"], role="Plans")
        team = AgentTeam([planner, builder], team_mode="orchestrator", orchestrator=manager, max_turns=2)
        result = team.run("task")
        self.assertEqual(result.transcript[0]["agent"], "builder")
        self.assertIn("Do work", builder.prompts[0])

    def test_orchestrator_done_returns_final_answer(self):
        manager = StubAgent("manager", ['{"done": true, "final_answer": "FINAL"}'])
        team = AgentTeam([StubAgent("a1", ["x"])], team_mode="orchestrator", orchestrator=manager, max_turns=1)
        result = team.run("task")
        self.assertTrue(result.completed)
        self.assertEqual(result.stop_reason, "orchestrator_done")
        self.assertEqual(result.text, "FINAL")

    def test_orchestrator_invalid_json_failure(self):
        manager = StubAgent("manager", ["not json"])
        team = AgentTeam([StubAgent("a1", ["x"])], team_mode="orchestrator", orchestrator=manager, max_turns=1)
        result = team.run("task")
        self.assertEqual(result.stop_reason, "orchestrator_invalid_json")

    def test_orchestrator_unknown_agent_failure(self):
        manager = StubAgent("manager", ['{"next_agent":"missing","instruction":"x"}'])
        team = AgentTeam([StubAgent("a1", ["x"])], team_mode="orchestrator", orchestrator=manager, max_turns=1)
        result = team.run("task")
        self.assertEqual(result.stop_reason, "orchestrator_unknown_agent")

    def test_orchestrator_max_turns_fallback(self):
        manager = StubAgent("manager", ['{"next_agent":"a1","instruction":"x"}', '{"next_agent":"a1","instruction":"y"}'])
        a1 = StubAgent("a1", ["r1", "r2"])
        team = AgentTeam([a1], team_mode="orchestrator", orchestrator=manager, max_turns=1)
        result = team.run("task")
        self.assertEqual(result.stop_reason, "max_turns_reached")

    def test_orchestrator_events_emitted(self):
        manager = StubAgent("manager", ['{"next_agent":"a1","instruction":"x","reason":"r"}', '{"done": true, "final_answer": "ok"}'])
        a1 = StubAgent("a1", ["r1"])
        team = AgentTeam([a1], team_mode="orchestrator", orchestrator=manager, max_turns=2)
        result = team.run("task")
        event_types = [e["type"] for e in result.events]
        self.assertIn("orchestrator_decision", event_types)
        self.assertIn("orchestrator_done", event_types)

    def test_orchestrator_error_event_emitted(self):
        manager = StubAgent("manager", ["not json"])
        team = AgentTeam([StubAgent("a1", ["x"])], team_mode="orchestrator", orchestrator=manager, max_turns=1)
        result = team.run("task")
        self.assertIn("orchestrator_error", [e["type"] for e in result.events])

    def test_orchestrator_prompt_contains_routing_guidance(self):
        manager = StubAgent("manager", ['{"done": true, "final_answer": "ok"}'])
        a1 = StubAgent("planner", ["x"], role="Plans", persona="Concise")
        team = AgentTeam([a1], team_mode="orchestrator", orchestrator=manager, max_turns=1)
        team.run("task")
        prompt = manager.prompts[0]
        self.assertIn("current state of the task", prompt)
        self.assertIn("what is still missing", prompt)
        self.assertIn("each agent's role and persona", prompt)
        self.assertIn("Do not repeatedly select the same agent unless it is clearly necessary", prompt)
        self.assertIn("Only return done=true when", prompt)

    def test_orchestrator_prompt_contains_json_examples(self):
        manager = StubAgent("manager", ['{"done": true, "final_answer": "ok"}'])
        a1 = StubAgent("planner", ["x"])
        team = AgentTeam([a1], team_mode="orchestrator", orchestrator=manager, max_turns=1)
        team.run("task")
        prompt = manager.prompts[0]
        self.assertIn('"next_agent": "agent_name"', prompt)
        self.assertIn('"done": true, "final_answer": "final answer text"', prompt)


class SessionTraceAggregationTests(unittest.TestCase):
    def test_llm_traces_aggregated_and_tagged(self):
        class TraceLLM:
            def __init__(self): self._t=[{"x":1}]
            def clear_traces(self): self._t=[]
            def get_traces(self): return [{"id":"1"}]
        class A(StubAgent):
            def __init__(self): super().__init__("a1", ["x"]); self.llm=TraceLLM()
            def collect_llm_traces(self): return self.llm.get_traces()
        team = AgentTeam([A()], max_turns=1)
        result = team.run("task")
        self.assertEqual(result.metadata["llm_traces"][0]["agent"], "a1")

    def test_tool_traces_aggregated(self):
        md_events = [[{"type":"observation","details":{"metadata":{"tool_name":"t","duration_ms":1}}}]]
        a1 = StubAgent("a1", ["x"], metadata_events=md_events)
        team = AgentTeam([a1], max_turns=1)
        result = team.run("task")
        self.assertEqual(result.metadata["tool_traces"][0]["tool_name"], "t")


if __name__ == "__main__":
    unittest.main()
