from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from nexus.agents.service import AgentStore
from nexus.projects.models import Project, ProjectMessage, ProjectResult
from nexus.projects.proposals import Proposal

HISTORY_LIMIT = 30


class ProjectNotFound(Exception):
    pass


class ProjectRefused(Exception):
    pass


class ProjectStore:
    def __init__(self, factory: sessionmaker[Session], agents: AgentStore) -> None:
        self.factory = factory
        self.agents = agents

    def _project(self, session: Session, project_id: str) -> Project:
        project = session.get(Project, project_id)
        if project is None:
            raise ProjectNotFound(project_id)
        return project

    def all(self) -> list[dict[str, Any]]:
        counts = (
            select(ProjectMessage.project_id, func.count().label("messages"))
            .group_by(ProjectMessage.project_id)
            .subquery()
        )
        results = (
            select(ProjectResult.project_id, func.count().label("results"))
            .group_by(ProjectResult.project_id)
            .subquery()
        )
        query = (
            select(Project, counts.c.messages, results.c.results)
            .outerjoin(counts, counts.c.project_id == Project.id)
            .outerjoin(results, results.c.project_id == Project.id)
            .order_by(Project.updated_at.desc())
        )
        with self.factory() as session:
            return [
                {
                    "id": project.id,
                    "name": project.name,
                    "description": project.description,
                    "updated_at": project.updated_at,
                    "messages": messages or 0,
                    "results": result_count or 0,
                }
                for project, messages, result_count in session.execute(query)
            ]

    def create(self, name: str, description: str) -> Project:
        with self.factory() as session, session.begin():
            project = Project(name=name, description=description)
            session.add(project)
            session.flush()
            session.expunge(project)
            return project

    def update(self, project_id: str, name: str | None, description: str | None) -> None:
        with self.factory() as session, session.begin():
            project = self._project(session, project_id)
            project.name = name or project.name
            if description is not None:
                project.description = description

    def delete(self, project_id: str) -> None:
        """Removes the conversation and results. Agents stay, since workflows may use them."""
        with self.factory() as session, session.begin():
            session.delete(self._project(session, project_id))

    def detail(self, project_id: str) -> dict[str, Any]:
        with self.factory() as session:
            project = self._project(session, project_id)
            messages = session.scalars(
                select(ProjectMessage)
                .where(ProjectMessage.project_id == project_id)
                .order_by(ProjectMessage.created_at)
            ).all()
            results = session.scalars(
                select(ProjectResult)
                .where(ProjectResult.project_id == project_id)
                .order_by(ProjectResult.created_at)
            ).all()
            return {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "updated_at": project.updated_at,
                "messages": [
                    {
                        "id": row.id,
                        "role": row.role,
                        "content": row.content,
                        "model": row.model,
                        "proposal": row.proposal,
                        "proposal_status": row.proposal_status,
                        "created_at": row.created_at,
                    }
                    for row in messages
                ],
                "results": [
                    {
                        "id": row.id,
                        "kind": row.kind,
                        "title": row.title,
                        "content": row.content,
                        "created_at": row.created_at,
                    }
                    for row in results
                ],
            }

    def add_message(
        self,
        project_id: str,
        role: str,
        content: str,
        model: str | None = None,
        proposal: Proposal | None = None,
    ) -> dict[str, Any]:
        with self.factory() as session, session.begin():
            project = self._project(session, project_id)
            project.updated_at = datetime.now(UTC)
            row = ProjectMessage(
                project_id=project_id,
                role=role,
                content=content,
                model=model,
                proposal=proposal.model_dump() if proposal else None,
                proposal_status="pending" if proposal else None,
            )
            session.add(row)
            session.flush()
            return {"id": row.id, "proposal": row.proposal}

    def history(self, project_id: str) -> list[dict[str, str]]:
        with self.factory() as session:
            rows = session.scalars(
                select(ProjectMessage)
                .where(ProjectMessage.project_id == project_id)
                .order_by(ProjectMessage.created_at.desc())
                .limit(HISTORY_LIMIT)
            ).all()
            return [{"role": row.role, "content": row.content} for row in reversed(rows)]

    def _pending(self, session: Session, project_id: str, message_id: str) -> ProjectMessage:
        message = session.get(ProjectMessage, message_id)
        if message is None or message.project_id != project_id:
            raise ProjectNotFound(message_id)
        if message.proposal_status != "pending":
            raise ProjectRefused("This proposal has already been answered")
        return message

    def reject(self, project_id: str, message_id: str) -> None:
        with self.factory() as session, session.begin():
            self._pending(session, project_id, message_id).proposal_status = "rejected"

    def approve(self, project_id: str, message_id: str) -> None:
        """The only path from model output to real objects, and only after a click."""
        with self.factory() as session, session.begin():
            message = self._pending(session, project_id, message_id)
            proposal = Proposal.model_validate(message.proposal)
            message.proposal_status = "approved"
            if proposal.roadmap:
                session.add(
                    ProjectResult(
                        project_id=project_id,
                        kind="roadmap",
                        title=proposal.roadmap.title,
                        content=proposal.roadmap.model_dump(),
                    )
                )
            for item in proposal.agents:
                definition = {
                    "role": item.role,
                    "system_prompt": item.system_prompt,
                    "runtime": "native",
                    "model": message.model or "",
                }
                agent = self.agents.create(item.name, None)
                self.agents.update(agent.id, None, definition)
                session.add(
                    ProjectResult(
                        project_id=project_id,
                        kind="agent",
                        title=item.name,
                        content={"agent_id": agent.id, "role": item.role},
                    )
                )
