import json
import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError

BLOCK = re.compile(r"```nexus-proposal\s*\n(.*?)(?:```|\Z)", re.DOTALL)

SYSTEM_PROMPT = """Tu es l'assistant de NEXUS. Tu aides la personne a avancer sur son projet.
Reponds dans la langue de la personne, simplement et sans jargon inutile.

Quand elle demande une roadmap ou des agents, reponds brievement, puis termine ton message par
un seul bloc exactement sous cette forme, sans rien apres :

```nexus-proposal
{"roadmap": {"title": "...", "steps": [{"title": "...", "detail": "..."}]},
 "agents": [{"name": "...", "role": "...", "system_prompt": "..."}]}
```

Mets seulement les parties demandees. N'ajoute jamais ce bloc dans les autres cas.
Rien n'est cree tant que la personne n'a pas valide."""

ShortText = Annotated[str, Field(min_length=1, max_length=200)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoadmapStep(Strict):
    title: ShortText
    detail: str = Field(default="", max_length=2000)


class Roadmap(Strict):
    title: ShortText
    steps: list[RoadmapStep] = Field(min_length=1, max_length=30)


class ProposedAgent(Strict):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    role: str = Field(default="", max_length=200)
    system_prompt: str = Field(min_length=1, max_length=8000)


class Proposal(Strict):
    roadmap: Roadmap | None = None
    agents: list[ProposedAgent] = Field(default_factory=list, max_length=10)


def split_proposal(text: str) -> tuple[str, Proposal | None]:
    """Separates the reply from its proposal. Model output is untrusted: anything that does not
    match the schema exactly is no proposal, and the reply stays readable."""
    match = BLOCK.search(text)
    if match is None:
        return text.strip(), None
    try:
        proposal = Proposal.model_validate(json.loads(match.group(1)))
    except (ValueError, ValidationError):
        return text.strip(), None
    if proposal.roadmap is None and not proposal.agents:
        return text.strip(), None
    return BLOCK.sub("", text).strip(), proposal
