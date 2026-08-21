"""Add candidate age metadata.

Revision ID: 20260821_0006
Revises: 20260820_0005
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_0006"
down_revision: str | None = "20260820_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("people", sa.Column("age", sa.Integer(), nullable=True))
    op.create_index("ix_people_age", "people", ["age"])


def downgrade() -> None:
    op.drop_index("ix_people_age", table_name="people")
    op.drop_column("people", "age")
