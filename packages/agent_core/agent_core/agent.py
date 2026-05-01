from agent_core.modes import ALLOWED_RESPONSE_MODES
from agent_core.prompt_builder import PromptBuilder
from agent_core.types import AgentResult, AgentStep


class Agent:
    def __init__(
        self,
        name: str = "agent",
        model: str = "ollama:gemma:e2b",
        response_mode: str = "pipeline",
        max_rounds: int = 4,
        timeout: int | None = None,
        memory=None,
        tools=None,
        workspace=None,
        generate_fn=None,
        pipeline_fn=None,
        context_builder_factory=None,
        prompt_builder=None,
    ):
        if response_mode not in ALLOWED_RESPONSE_MODES:
            raise ValueError(f"Invalid response_mode: {response_mode}")

        self.name = name
        self.model = model
        self.response_mode = response_mode
        self.max_rounds = max_rounds
        self.timeout = timeout
        self.memory = memory
        self.tools = tools
        self.workspace = workspace
        self.generate_fn = generate_fn
        self.pipeline_fn = pipeline_fn
        self.context_builder_factory = context_builder_factory
        self.prompt_builder = prompt_builder or PromptBuilder()

    def _get_generate_fn(self):
        if self.generate_fn is not None:
            return self.generate_fn
        try:
            from model_router import generate
        except ImportError as exc:
            raise RuntimeError("model_router is not installed") from exc
        return generate

    def build_prompt(self, task: str, facts: list[str] | None = None, instruction: str | None = None) -> str:
        return self.prompt_builder.build(
            task=task,
            facts=facts,
            tools=self.tools,
            workspace=self.workspace,
            memory=self.memory,
            instruction=instruction,
        )

    def generate(self, task: str, facts: list[str] | None = None) -> AgentResult:
        gen = self._get_generate_fn()

        if self.response_mode == "raw":
            prompt = self.build_prompt(task, facts)
            text = gen(prompt=prompt, model=self.model, timeout=self.timeout)
            return AgentResult(text=text)

        if self.response_mode == "think":
            think_prompt = self.build_prompt(task, facts, instruction="Think privately and produce useful reasoning notes.")
            notes = gen(prompt=think_prompt, model=self.model, timeout=self.timeout)
            final_prompt = (
                f"TASK:\n{task}\n\nPRIVATE_NOTES:\n{notes}\n\nINSTRUCTION:\nProduce final answer only."
            )
            final = gen(prompt=final_prompt, model=self.model, timeout=self.timeout)
            return AgentResult(text=final, metadata={"thinking_used": True})

        pipeline = self.pipeline_fn
        if pipeline is None:
            try:
                from invisible_pipeline import run_pipeline
            except ImportError as exc:
                raise RuntimeError("invisible_pipeline is not installed") from exc
            pipeline = run_pipeline

        result = pipeline(
            task=task,
            max_rounds=self.max_rounds,
            model=self.model,
            facts=facts,
            timeout=self.timeout,
            generate_fn=self.generate_fn,
        )
        return AgentResult(
            text=result.final_answer,
            completed=result.completed,
            metadata={"rounds_used": result.rounds_used},
        )

    def next_step(self, task: str, facts: list[str] | None = None) -> AgentStep:
        result = self.generate(task, facts)
        return AgentStep(kind="final", text=result.text, metadata=result.metadata)
