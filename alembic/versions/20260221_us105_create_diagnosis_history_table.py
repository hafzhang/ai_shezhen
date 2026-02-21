"""create diagnosis_history table

Revision ID: 20260221_us105
Revises: 20260221_us104
Create Date: 2026-02-21

AI舌诊智能诊断系统 - Diagnosis History Table Migration
Phase 2: Database & Auth - US-105

This migration creates the diagnosis_history table with:
- UUID primary key
- Foreign keys to users and tongue_images tables
- JSONB fields for user_info, features, and results
- Model metadata (model_version, inference_time_ms)
- Feedback tracking (feedback, feedback_comment)
- Timestamps (created_at, updated_at)
- Composite index for user history queries

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260221_us105"
down_revision: Union[str, None] = "20260221_us104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create diagnosis_history table with indexes."""
    # Create diagnosis_history table
    op.create_table(
        "diagnosis_history",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            nullable=True,
            comment="Foreign key to users table (NULL for anonymous)",
        ),
        sa.Column(
            "tongue_image_id",
            UUID(as_uuid=True),
            nullable=False,
            comment="Foreign key to tongue_images table",
        ),
        sa.Column(
            "user_info",
            JSONB,
            nullable=True,
            comment="User input data (age, gender, chief_complaint)",
        ),
        sa.Column(
            "features",
            JSONB,
            nullable=True,
            comment="Extracted tongue features (6-dimension classification)",
        ),
        sa.Column(
            "results",
            JSONB,
            nullable=True,
            comment="Diagnosis results (syndrome, confidence, recommendations)",
        ),
        sa.Column(
            "model_version",
            sa.String(50),
            nullable=True,
            comment="Model version used for diagnosis",
        ),
        sa.Column(
            "inference_time_ms",
            sa.Integer(),
            nullable=True,
            comment="Inference time in milliseconds",
        ),
        sa.Column(
            "feedback",
            sa.Integer(),
            nullable=True,
            comment="User feedback (1=helpful, -1=not helpful, NULL=no feedback)",
        ),
        sa.Column(
            "feedback_comment",
            sa.Text(),
            nullable=True,
            comment="User feedback comment",
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
        sa.PrimaryKeyConstraint("id", name="diagnosis_history_pkey"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="diagnosis_history_user_id_fkey",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tongue_image_id"],
            ["tongue_images.id"],
            name="diagnosis_history_tongue_image_id_fkey",
            ondelete="CASCADE",
        ),
        comment="Diagnosis history - stores all diagnosis results with JSONB data",
    )

    # Create composite index on (user_id, created_at DESC) for user diagnosis history
    op.create_index(
        "ix_diagnosis_history_user_id_created_at",
        "diagnosis_history",
        ["user_id", sa.text("created_at DESC")],
        unique=False,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )

    # Create index on tongue_image_id for image-to-diagnosis lookup
    op.create_index(
        "ix_diagnosis_history_tongue_image_id",
        "diagnosis_history",
        ["tongue_image_id"],
        unique=False,
    )

    # Create index on created_at for time-based queries
    op.create_index(
        "ix_diagnosis_history_created_at",
        "diagnosis_history",
        ["created_at"],
        unique=False,
    )

    # Create index on model_version for filtering by model version
    op.create_index(
        "ix_diagnosis_history_model_version",
        "diagnosis_history",
        ["model_version"],
        unique=False,
        postgresql_where=sa.text("model_version IS NOT NULL"),
    )

    # Create partial index on feedback for filtering feedback provided
    op.create_index(
        "ix_diagnosis_history_feedback",
        "diagnosis_history",
        ["feedback"],
        unique=False,
        postgresql_where=sa.text("feedback IS NOT NULL"),
    )

    # Create GIN index on JSONB columns for efficient JSON queries
    # Create GIN index on user_info JSONB
    op.create_index(
        "ix_diagnosis_history_user_info_gin",
        "diagnosis_history",
        ["user_info"],
        unique=False,
        postgresql_using="gin",
    )

    # Create GIN index on features JSONB
    op.create_index(
        "ix_diagnosis_history_features_gin",
        "diagnosis_history",
        ["features"],
        unique=False,
        postgresql_using="gin",
    )

    # Create GIN index on results JSONB
    op.create_index(
        "ix_diagnosis_history_results_gin",
        "diagnosis_history",
        ["results"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Drop diagnosis_history table and indexes."""
    # Drop GIN indexes
    op.drop_index("ix_diagnosis_history_results_gin", table_name="diagnosis_history")
    op.drop_index("ix_diagnosis_history_features_gin", table_name="diagnosis_history")
    op.drop_index("ix_diagnosis_history_user_info_gin", table_name="diagnosis_history")

    # Drop regular indexes
    op.drop_index("ix_diagnosis_history_feedback", table_name="diagnosis_history")
    op.drop_index("ix_diagnosis_history_model_version", table_name="diagnosis_history")
    op.drop_index("ix_diagnosis_history_created_at", table_name="diagnosis_history")
    op.drop_index("ix_diagnosis_history_tongue_image_id", table_name="diagnosis_history")
    op.drop_index("ix_diagnosis_history_user_id_created_at", table_name="diagnosis_history")

    # Drop table (foreign keys will be automatically dropped)
    op.drop_table("diagnosis_history")
