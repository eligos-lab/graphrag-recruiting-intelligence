"""Create Phase 1 core entities.

Revision ID: 20260820_0001
Revises:
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260820_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> list[sa.Column[object]]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_companies"),
        sa.UniqueConstraint("name", "country", name="uq_companies_name_country"),
    )
    op.create_index("ix_companies_name", "companies", ["name"])

    op.create_table(
        "domains",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_domains"),
        sa.UniqueConstraint("name", name="uq_domains_name"),
    )
    op.create_index("ix_domains_name", "domains", ["name"])

    op.create_table(
        "people",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("current_title", sa.String(length=255), nullable=True),
        sa.Column("years_experience", sa.Float(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_people"),
        sa.UniqueConstraint("source", "source_id", name="uq_people_source_source_id"),
    )
    op.create_index("ix_people_country", "people", ["country"])
    op.create_index("ix_people_current_title", "people", ["current_title"])
    op.create_index("ix_people_full_name", "people", ["full_name"])

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
    )
    op.create_index("ix_projects_name", "projects", ["name"])

    op.create_table(
        "skills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_skills"),
        sa.UniqueConstraint("normalized_name", name="uq_skills_normalized_name"),
    )
    op.create_index("ix_skills_normalized_name", "skills", ["normalized_name"])

    op.create_table(
        "technologies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_technologies"),
        sa.UniqueConstraint("name", name="uq_technologies_name"),
    )
    op.create_index("ix_technologies_name", "technologies", ["name"])

    op.create_table(
        "universities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_universities"),
        sa.UniqueConstraint("name", "country", name="uq_universities_name_country"),
    )
    op.create_index("ix_universities_name", "universities", ["name"])

    association_tables = (
        ("person_companies", "person_id", "people", "company_id", "companies"),
        ("person_skills", "person_id", "people", "skill_id", "skills"),
        ("person_technologies", "person_id", "people", "technology_id", "technologies"),
        ("person_projects", "person_id", "people", "project_id", "projects"),
        ("person_universities", "person_id", "people", "university_id", "universities"),
        ("person_domains", "person_id", "people", "domain_id", "domains"),
        ("company_domains", "company_id", "companies", "domain_id", "domains"),
        ("project_technologies", "project_id", "projects", "technology_id", "technologies"),
        ("project_domains", "project_id", "projects", "domain_id", "domains"),
    )
    for table, left_column, left_table, right_column, right_table in association_tables:
        op.create_table(
            table,
            sa.Column(left_column, sa.Uuid(), nullable=False),
            sa.Column(right_column, sa.Uuid(), nullable=False),
            sa.ForeignKeyConstraint(
                [left_column],
                [f"{left_table}.id"],
                name=f"fk_{table}_{left_column}_{left_table}",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                [right_column],
                [f"{right_table}.id"],
                name=f"fk_{table}_{right_column}_{right_table}",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint(left_column, right_column, name=f"pk_{table}"),
        )


def downgrade() -> None:
    for table in (
        "project_domains",
        "project_technologies",
        "company_domains",
        "person_domains",
        "person_universities",
        "person_projects",
        "person_technologies",
        "person_skills",
        "person_companies",
    ):
        op.drop_table(table)

    op.drop_index("ix_universities_name", table_name="universities")
    op.drop_table("universities")
    op.drop_index("ix_technologies_name", table_name="technologies")
    op.drop_table("technologies")
    op.drop_index("ix_skills_normalized_name", table_name="skills")
    op.drop_table("skills")
    op.drop_index("ix_projects_name", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_people_full_name", table_name="people")
    op.drop_index("ix_people_current_title", table_name="people")
    op.drop_index("ix_people_country", table_name="people")
    op.drop_table("people")
    op.drop_index("ix_domains_name", table_name="domains")
    op.drop_table("domains")
    op.drop_index("ix_companies_name", table_name="companies")
    op.drop_table("companies")
