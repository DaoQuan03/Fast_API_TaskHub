"""Add composite indexes for task filtering and comment listing

Revision ID: 0003_add_task_comment_composite_indexes
Revises: 0002_add_refresh_tokens
Create Date: 2026-11-26 11:05:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003_add_task_comment_composite_indexes"
down_revision: Union[str, None] = "0002_add_refresh_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_tasks_project_status",
        "tasks",
        ["project_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_tasks_project_priority",
        "tasks",
        ["project_id", "priority"],
        unique=False,
    )
    op.create_index(
        "ix_comments_task_created_at",
        "comments",
        ["task_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_comments_task_created_at", table_name="comments")
    op.drop_index("ix_tasks_project_priority", table_name="tasks")
    op.drop_index("ix_tasks_project_status", table_name="tasks")
