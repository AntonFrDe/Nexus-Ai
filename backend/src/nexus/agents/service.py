from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from nexus.agents.definition import AGENT_FIELDS
from nexus.agents.models import Agent, AgentVersion
from nexus.agents.templates import AGENT_TEMPLATES
from nexus.nodes.config_model import validate_config


class AgentNotFound(Exception):
    pass


class AgentRefused(Exception):
    pass


class AgentStore:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self.factory = factory

    @staticmethod
    def problems(definition: dict[str, Any]) -> list[tuple[str, str]]:
        return validate_config("agent", AGENT_FIELDS, definition)

    def _agent(self, session: Session, agent_id: str) -> Agent:
        agent = session.get(Agent, agent_id)
        if agent is None:
            raise AgentNotFound(agent_id)
        return agent

    def all(self) -> list[Agent]:
        with self.factory() as session:
            rows = list(session.scalars(select(Agent).order_by(Agent.name)))
            session.expunge_all()
            return rows

    def get(self, agent_id: str) -> Agent:
        with self.factory() as session:
            agent = self._agent(session, agent_id)
            session.expunge(agent)
            return agent

    def _snapshot(self, session: Session, agent: Agent) -> None:
        session.add(
            AgentVersion(
                agent_id=agent.id,
                number=agent.version,
                name=agent.name,
                definition=agent.definition,
            )
        )

    def create(self, name: str, template: str | None) -> Agent:
        definition: dict[str, Any] = {"runtime": "native"}
        if template:
            known = next((item for item in AGENT_TEMPLATES if item.id == template), None)
            if known is None:
                raise AgentRefused(f"Unknown template: {template}")
            definition = dict(known.definition)
        with self.factory() as session, session.begin():
            agent = Agent(name=name, template=template, definition=definition)
            session.add(agent)
            session.flush()
            self._snapshot(session, agent)
            session.flush()
            session.expunge(agent)
            return agent

    def update(self, agent_id: str, name: str | None, definition: dict[str, Any] | None) -> Agent:
        """Every change is a new immutable version. Drafts may be incomplete until they run."""
        with self.factory() as session, session.begin():
            agent = self._agent(session, agent_id)
            new_name = name or agent.name
            new_definition = agent.definition if definition is None else definition
            if new_name != agent.name or new_definition != agent.definition:
                agent.name = new_name
                agent.definition = new_definition
                agent.version += 1
                self._snapshot(session, agent)
                session.flush()
            session.expunge(agent)
            return agent

    def delete(self, agent_id: str) -> None:
        with self.factory() as session, session.begin():
            session.delete(self._agent(session, agent_id))

    def clone(self, agent_id: str) -> Agent:
        source = self.get(agent_id)
        with self.factory() as session, session.begin():
            agent = Agent(
                name=f"{source.name} copy"[:120],
                template=source.template,
                definition=source.definition,
            )
            session.add(agent)
            session.flush()
            self._snapshot(session, agent)
            session.flush()
            session.expunge(agent)
            return agent

    def versions(self, agent_id: str) -> list[AgentVersion]:
        query = (
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.number.desc())
        )
        with self.factory() as session:
            self._agent(session, agent_id)
            rows = list(session.scalars(query))
            session.expunge_all()
            return rows

    def restore(self, agent_id: str, number: int) -> Agent:
        match = next((row for row in self.versions(agent_id) if row.number == number), None)
        if match is None:
            raise AgentNotFound(f"{agent_id} version {number}")
        return self.update(agent_id, match.name, match.definition)
