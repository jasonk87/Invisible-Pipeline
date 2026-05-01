from dataclasses import replace
from typing import Callable

from context_core.policies import estimate_tokens, get_context_window
from context_core.result import ContextPackResult
from context_core.section import ContextSection


class ContextBuilder:
    def __init__(
        self,
        model: str,
        generate_fn: Callable[..., str],
        context_window: int | None = None,
        max_usage_ratio: float = 0.80,
    ):
        self.model = model
        self.generate_fn = generate_fn
        self.context_window = get_context_window(model, context_window)
        self.max_usage_ratio = max_usage_ratio
        self.sections: list[ContextSection] = []

    def add_section(self, section: ContextSection):
        self.sections.append(section)

    def add(self, name, text, policy="compact", priority=50):
        self.add_section(ContextSection(name=name, text=text, policy=policy, priority=priority))

    def pack(self, task: str) -> ContextPackResult:
        max_tokens = int(self.context_window * self.max_usage_ratio)
        warnings: list[str] = []
        errors: list[str] = []
        compacted: list[str] = []
        dropped: list[str] = []

        preserve = sorted([s for s in self.sections if s.policy == "preserve"], key=lambda s: s.priority)
        others = sorted([s for s in self.sections if s.policy != "preserve"], key=lambda s: s.priority)

        included: list[ContextSection] = []
        task_block = f"TASK:\n{task}"
        current_tokens = estimate_tokens(task_block)

        for sec in preserve:
            sec_block = f"SECTION: {sec.name}\n{sec.text}"
            sec_tokens = estimate_tokens(sec_block)
            if current_tokens + sec_tokens > max_tokens:
                errors.append("Preserve sections exceed token budget")
                return ContextPackResult(False, "", current_tokens, max_tokens, warnings, errors, compacted, dropped)
            included.append(sec)
            current_tokens += sec_tokens

        for sec in others:
            candidate_text = sec.text
            sec_block = f"SECTION: {sec.name}\n{candidate_text}"
            sec_tokens = estimate_tokens(sec_block)
            if current_tokens + sec_tokens <= max_tokens:
                included.append(sec)
                current_tokens += sec_tokens
                continue

            if sec.policy == "compact":
                prompt = (
                    f"TASK:\n{task}\n\nCONTENT:\n{sec.text}\n\nINSTRUCTION:\n"
                    "Compress this content while preserving details required to answer the task.\n"
                    "Remove redundancy and noise.\n"
                    "Keep facts, constraints, file names, errors, and decisions."
                )
                compact_text = self.generate_fn(prompt=prompt, model=self.model, timeout=None)
                compact_section = replace(sec, text=compact_text)
                compact_block = f"SECTION: {sec.name}\n{compact_text}"
                compact_tokens = estimate_tokens(compact_block)
                if current_tokens + compact_tokens <= max_tokens:
                    included.append(compact_section)
                    compacted.append(sec.name)
                    current_tokens += compact_tokens
                    continue
                dropped.append(sec.name)
                warnings.append(f"Compacted section still did not fit: {sec.name}")
                continue

            if sec.policy == "truncate":
                available = max_tokens - current_tokens
                if available <= estimate_tokens(f"SECTION: {sec.name}\n"):
                    dropped.append(sec.name)
                    warnings.append(f"Dropped truncated section due to no space: {sec.name}")
                    continue
                max_chars = max(0, (available * 4) - len(f"SECTION: {sec.name}\n"))
                trimmed = sec.text[:max_chars]
                included.append(replace(sec, text=trimmed))
                current_tokens += estimate_tokens(f"SECTION: {sec.name}\n{trimmed}")
                warnings.append(f"Truncated section: {sec.name}")
                continue

            if sec.policy == "drop":
                dropped.append(sec.name)
                continue

            errors.append(f"Unsupported policy: {sec.policy}")
            return ContextPackResult(False, "", current_tokens, max_tokens, warnings, errors, compacted, dropped)

        lines = [task_block, ""]
        for sec in included:
            lines.append(f"SECTION: {sec.name}")
            lines.append(sec.text)
            lines.append("")
        final_text = "\n".join(lines).rstrip() + "\n"
        final_tokens = estimate_tokens(final_text)

        if final_tokens > max_tokens:
            errors.append("Packed context still exceeds token budget")
            return ContextPackResult(False, "", final_tokens, max_tokens, warnings, errors, compacted, dropped)

        return ContextPackResult(True, final_text, final_tokens, max_tokens, warnings, errors, compacted, dropped)
