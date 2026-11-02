from typing import Any

from pydantic import BaseModel


class AgentTemplate(BaseModel):
    id: str
    name: str
    definition: dict[str, Any]


def _template(id_: str, name: str, role: str, prompt: str) -> AgentTemplate:
    definition = {"role": role, "system_prompt": prompt, "runtime": "native"}
    return AgentTemplate(id=id_, name=name, definition=definition)


AGENT_TEMPLATES: list[AgentTemplate] = [
    _template(
        "planner",
        "Planner",
        "Planning",
        "Break the request into small ordered steps. Name the risks and what to verify.",
    ),
    _template(
        "developer",
        "Developer",
        "Implementation",
        "Make the smallest correct change. Follow the surrounding code and explain any trade-off.",
    ),
    _template(
        "reviewer",
        "Code Reviewer",
        "Review",
        "Review independently. Report only real defects, each with a concrete failing case.",
    ),
    _template(
        "researcher",
        "Researcher",
        "Research",
        "Answer from the sources given. Mark what is verified and what remains uncertain.",
    ),
    _template(
        "extractor",
        "Data Extractor",
        "Extraction",
        "Extract the requested fields as JSON. Use null for anything absent. Never guess.",
    ),
    _template(
        "summarizer",
        "Summarizer",
        "Summary",
        "Summarize faithfully and briefly. Keep decisions, numbers and open questions.",
    ),
]
