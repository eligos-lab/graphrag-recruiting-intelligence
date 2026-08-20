"""Add structured ingestion persistence.

Revision ID: 20260820_0002
Revises: 20260820_0001
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260820_0002"
down_revision: str | None = "20260820_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _normalized_name_expression(column: str = "name") -> sa.TextClause:
    return sa.text(f"lower(regexp_replace(trim({column}), '[^[:alnum:]]+', ' ', 'g'))")


def upgrade() -> None:
    op.add_column("people", sa.Column("normalized_identity", sa.String(length=512), nullable=True))
    op.create_index("ix_people_normalized_identity", "people", ["normalized_identity"])

    for table in ("companies", "technologies", "projects", "universities", "domains"):
        op.add_column(table, sa.Column("normalized_name", sa.String(length=255), nullable=True))
        op.execute(
            sa.update(sa.table(table, sa.column("normalized_name"), sa.column("name"))).values(
                normalized_name=_normalized_name_expression()
            )
        )
        op.alter_column(
            table, "normalized_name", existing_type=sa.String(length=255), nullable=False
        )
        op.create_index(f"ix_{table}_normalized_name", table, ["normalized_name"])

    op.drop_constraint("uq_companies_name_country", "companies", type_="unique")
    op.create_unique_constraint(
        "uq_companies_normalized_name_country",
        "companies",
        ["normalized_name", "country"],
        postgresql_nulls_not_distinct=True,
    )
    op.drop_constraint("uq_technologies_name", "technologies", type_="unique")
    op.create_unique_constraint(
        "uq_technologies_normalized_name", "technologies", ["normalized_name"]
    )
    op.drop_constraint("uq_universities_name_country", "universities", type_="unique")
    op.create_unique_constraint(
        "uq_universities_normalized_name_country",
        "universities",
        ["normalized_name", "country"],
        postgresql_nulls_not_distinct=True,
    )
    op.drop_constraint("uq_domains_name", "domains", type_="unique")
    op.create_unique_constraint("uq_domains_normalized_name", "domains", ["normalized_name"])

    op.create_table(
        "skill_aliases",
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skills.id"],
            name="fk_skill_aliases_skill_id_skills",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("alias", name="pk_skill_aliases"),
    )
    op.create_index("ix_skill_aliases_skill_id", "skill_aliases", ["skill_id"])

    op.create_table(
        "raw_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
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
            name="fk_raw_documents_person_id_people",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_raw_documents"),
        sa.UniqueConstraint("checksum", name="uq_raw_documents_checksum"),
        sa.UniqueConstraint("source", "external_id", name="uq_raw_documents_source_external_id"),
    )
    op.create_index("ix_raw_documents_checksum", "raw_documents", ["checksum"])
    op.create_index("ix_raw_documents_person_id", "raw_documents", ["person_id"])


def downgrade() -> None:
    op.drop_index("ix_raw_documents_person_id", table_name="raw_documents")
    op.drop_index("ix_raw_documents_checksum", table_name="raw_documents")
    op.drop_table("raw_documents")
    op.drop_index("ix_skill_aliases_skill_id", table_name="skill_aliases")
    op.drop_table("skill_aliases")

    op.drop_constraint("uq_domains_normalized_name", "domains", type_="unique")
    op.create_unique_constraint("uq_domains_name", "domains", ["name"])
    op.drop_constraint("uq_universities_normalized_name_country", "universities", type_="unique")
    op.create_unique_constraint("uq_universities_name_country", "universities", ["name", "country"])
    op.drop_constraint("uq_technologies_normalized_name", "technologies", type_="unique")
    op.create_unique_constraint("uq_technologies_name", "technologies", ["name"])
    op.drop_constraint("uq_companies_normalized_name_country", "companies", type_="unique")
    op.create_unique_constraint("uq_companies_name_country", "companies", ["name", "country"])

    for table in ("domains", "universities", "projects", "technologies", "companies"):
        op.drop_index(f"ix_{table}_normalized_name", table_name=table)
        op.drop_column(table, "normalized_name")

    op.drop_index("ix_people_normalized_identity", table_name="people")
    op.drop_column("people", "normalized_identity")
