"""Add provenance-backed candidate inferences.

Revision ID: 20260820_0004
Revises: 20260820_0003
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260820_0004"
down_revision: str | None = "20260820_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_inferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("inference_type", sa.String(length=50), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["people.id"],
            name="fk_candidate_inferences_person_id_people",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_candidate_inferences"),
        sa.UniqueConstraint(
            "person_id",
            "inference_type",
            "claim",
            name="uq_candidate_inferences_person_type_claim",
        ),
    )
    op.create_index(
        "ix_candidate_inferences_inference_type",
        "candidate_inferences",
        ["inference_type"],
    )
    op.create_index(
        "ix_candidate_inferences_person_id",
        "candidate_inferences",
        ["person_id"],
    )
    op.create_index(
        "ix_candidate_inferences_status",
        "candidate_inferences",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_inferences_status", table_name="candidate_inferences")
    op.drop_index("ix_candidate_inferences_person_id", table_name="candidate_inferences")
    op.drop_index("ix_candidate_inferences_inference_type", table_name="candidate_inferences")
    op.drop_table("candidate_inferences")
