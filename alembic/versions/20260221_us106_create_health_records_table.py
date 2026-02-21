"""create health_records table

Revision ID: 20260221_us106
Revises: 20260221_us105
Create Date: 2026-02-21

AI舌诊智能诊断系统 - Health Records Table Migration
Phase 2: Database & Auth - US-106

This migration creates the health_records table with:
- UUID primary key
- Foreign key to users table
- Record type (e.g., blood_pressure, weight, symptoms)
- JSONB field for flexible record_value storage
- Source tracking (user_input, device_import)
- Timestamps (record_date, created_at, updated_at, deleted_at)
- Composite index for user record type queries

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260221_us106"
down_revision: Union[str, None] = "20260221_us105"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create health_records table with indexes."""
    # Create enum type for record_type
    record_type_enum = sa.Enum(
        "blood_pressure",
        "heart_rate",
        "weight",
        "height",
        "temperature",
        "blood_sugar",
        "symptoms",
        "medication",
        "lab_results",
        "other",
        name="healthrecordtype",
    )
    record_type_enum.create(op.get_bind(), checkfirst=False)

    # Create health_records table
    op.create_table(
        "health_records",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            nullable=False,
            comment="Foreign key to users table",
        ),
        sa.Column(
            "record_type",
            record_type_enum,
            nullable=False,
            comment="Type of health record",
        ),
        sa.Column(
            "record_value",
            JSONB,
            nullable=False,
            comment="Health record data (flexible JSONB structure)",
        ),
        sa.Column(
            "record_date",
            sa.Date(),
            nullable=True,
            comment="Date of the health record (if applicable)",
        ),
        sa.Column(
            "source",
            sa.String(50),
            nullable=True,
            comment="Record source (user_input, device_import, etc.)",
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment="Additional notes or comments",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Soft delete timestamp",
        ),
        sa.PrimaryKeyConstraint("id", name="health_records_pkey"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="health_records_user_id_fkey",
            ondelete="CASCADE",
        ),
        comment="User health records - stores medical and health data with flexible JSONB values",
    )

    # Create composite index on (user_id, record_type) for user records by type
    op.create_index(
        "ix_health_records_user_id_record_type",
        "health_records",
        ["user_id", "record_type"],
        unique=False,
    )

    # Create index on record_date for time-based queries
    op.create_index(
        "ix_health_records_record_date",
        "health_records",
        ["record_date"],
        unique=False,
        postgresql_where=sa.text("record_date IS NOT NULL"),
    )

    # Create index on created_at for sorting by creation time
    op.create_index(
        "ix_health_records_created_at",
        "health_records",
        ["created_at"],
        unique=False,
    )

    # Create composite index on (user_id, record_date DESC) for user health history
    op.create_index(
        "ix_health_records_user_id_record_date",
        "health_records",
        ["user_id", sa.text("record_date DESC")],
        unique=False,
        postgresql_where=sa.text("record_date IS NOT NULL"),
    )

    # Create index on deleted_at for soft delete filtering
    op.create_index(
        "ix_health_records_deleted_at",
        "health_records",
        ["deleted_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Create GIN index on record_value JSONB for efficient JSON queries
    op.create_index(
        "ix_health_records_record_value_gin",
        "health_records",
        ["record_value"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Drop health_records table and indexes."""
    # Drop GIN index
    op.drop_index("ix_health_records_record_value_gin", table_name="health_records")

    # Drop regular indexes
    op.drop_index("ix_health_records_deleted_at", table_name="health_records")
    op.drop_index("ix_health_records_user_id_record_date", table_name="health_records")
    op.drop_index("ix_health_records_created_at", table_name="health_records")
    op.drop_index("ix_health_records_record_date", table_name="health_records")
    op.drop_index("ix_health_records_user_id_record_type", table_name="health_records")

    # Drop table (foreign key will be automatically dropped)
    op.drop_table("health_records")

    # Drop enum type
    op.execute("DROP TYPE IF EXISTS healthrecordtype")
