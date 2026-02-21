"""create tongue_images table

Revision ID: 20260221_us104
Revises: 20260221_us103
Create Date: 2026-02-21

AI舌诊智能诊断系统 - Tongue Images Table Migration
Phase 2: Database & Auth - US-104

This migration creates the tongue_images table with:
- UUID primary key
- Foreign key to users table (nullable for anonymous diagnosis)
- Image metadata (file_hash, original_filename, storage_path)
- Image dimensions (width, height)
- Processing flags (is_processed, segmentation_path, classification_path)
- Timestamps (created_at, updated_at, deleted_at)
- Indexes for common query patterns

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260221_us104"
down_revision: Union[str, None] = "20260221_us103"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create tongue_images table with indexes."""
    # Create tongue_images table
    op.create_table(
        "tongue_images",
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
            "file_hash",
            sa.String(64),
            nullable=False,
            unique=True,
            comment="SHA-256 hash of the image file",
        ),
        sa.Column(
            "original_filename",
            sa.String(255),
            nullable=True,
            comment="Original uploaded filename",
        ),
        sa.Column(
            "storage_path",
            sa.String(500),
            nullable=False,
            comment="Path to stored image file",
        ),
        sa.Column(
            "width",
            sa.Integer(),
            nullable=True,
            comment="Image width in pixels",
        ),
        sa.Column(
            "height",
            sa.Integer(),
            nullable=True,
            comment="Image height in pixels",
        ),
        sa.Column(
            "file_size",
            sa.BigInteger(),
            nullable=True,
            comment="File size in bytes",
        ),
        sa.Column(
            "mime_type",
            sa.String(50),
            nullable=True,
            comment="MIME type (e.g., image/jpeg)",
        ),
        sa.Column(
            "is_processed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="Whether image has been processed",
        ),
        sa.Column(
            "segmentation_path",
            sa.String(500),
            nullable=True,
            comment="Path to segmentation mask file",
        ),
        sa.Column(
            "classification_path",
            sa.String(500),
            nullable=True,
            comment="Path to classification result file",
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
        sa.PrimaryKeyConstraint("id", name="tongue_images_pkey"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="tongue_images_user_id_fkey",
            ondelete="SET NULL",
        ),
        comment="Tongue image storage - supports anonymous and authenticated uploads",
    )

    # Create index on user_id for user image lookup
    op.create_index(
        "ix_tongue_images_user_id",
        "tongue_images",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )

    # Create unique index on file_hash for deduplication
    op.create_index(
        "ix_tongue_images_file_hash",
        "tongue_images",
        ["file_hash"],
        unique=True,
        postgresql_where=sa.text("file_hash IS NOT NULL"),
    )

    # Create index on created_at for time-based queries
    op.create_index(
        "ix_tongue_images_created_at",
        "tongue_images",
        ["created_at"],
        unique=False,
    )

    # Create composite index on (user_id, created_at DESC) for user image history
    op.create_index(
        "ix_tongue_images_user_id_created_at",
        "tongue_images",
        ["user_id", sa.text("created_at DESC")],
        unique=False,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )

    # Create index on deleted_at for soft delete filtering
    op.create_index(
        "ix_tongue_images_deleted_at",
        "tongue_images",
        ["deleted_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Create index on is_processed for filtering unprocessed images
    op.create_index(
        "ix_tongue_images_is_processed",
        "tongue_images",
        ["is_processed"],
        unique=False,
        postgresql_where=sa.text("is_processed = false"),
    )


def downgrade() -> None:
    """Drop tongue_images table and indexes."""
    # Drop indexes
    op.drop_index("ix_tongue_images_is_processed", table_name="tongue_images")
    op.drop_index("ix_tongue_images_deleted_at", table_name="tongue_images")
    op.drop_index("ix_tongue_images_user_id_created_at", table_name="tongue_images")
    op.drop_index("ix_tongue_images_created_at", table_name="tongue_images")
    op.drop_index("ix_tongue_images_file_hash", table_name="tongue_images")
    op.drop_index("ix_tongue_images_user_id", table_name="tongue_images")

    # Drop table (foreign key will be automatically dropped)
    op.drop_table("tongue_images")
