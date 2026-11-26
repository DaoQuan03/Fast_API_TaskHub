from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import COLOR_MAX_LENGTH, DEFAULT_LABEL_COLOR, LABEL_NAME_MAX_LENGTH
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.task import Task


class TaskLabel(Base):
    __tablename__ = "task_labels"

    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    label_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class Label(Base):
    __tablename__ = "labels"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_labels_project_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(LABEL_NAME_MAX_LENGTH), nullable=False)
    color: Mapped[str] = mapped_column(
        String(COLOR_MAX_LENGTH), default=DEFAULT_LABEL_COLOR, nullable=False
    )

    project: Mapped["Project"] = relationship("Project", back_populates="labels")
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        secondary="task_labels",
        back_populates="labels",
        passive_deletes=True,
    )
