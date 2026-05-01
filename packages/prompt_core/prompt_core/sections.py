from dataclasses import dataclass


@dataclass(slots=True)
class PromptSection:
    title: str
    content: str

    def __post_init__(self):
        title = (self.title or "").strip()
        if not title:
            raise ValueError("title must be non-empty")
        self.title = title
        self.content = "" if self.content is None else str(self.content)
