# prompt_core

Deterministic prompt text builders used by higher-level packages.

- Includes stronger default agent grounding instructions.
- Team prompts discourage repetition and premature `DONE`.
- Tool correction prompts require strict JSON-only corrected calls.

`prompt_core` does not call models or execute tools.
