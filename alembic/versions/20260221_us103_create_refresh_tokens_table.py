"""create refresh_tokens table

Revision ID: 20260221_us103
Revises: 20260221_us102
Create Date: 2026-02-21

AI舌诊智能诊断系统 - Refresh Tokens Table Migration
Phase 2: Database & Auth - US-103

This migration creates the refresh_tokens table with:
- UUID primary key
- Foreign key to users table
- Token hash for security
- Expiration timestamp
- Revocation tracking (revoked_at)
- Indexes for common query patterns

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260221_us103"
down_revision: Union[str, None] = "20260221_us102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create refresh_tokens table with indexes."""
    # Create refresh_tokens table
    op.create_table(
        "refresh_tokens",
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
            "token",
            sa.String(255),
            nullable=False,
            unique=True,
            comment="JWT refresh token hash",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Token expiration timestamp",
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Token revocation timestamp (NULL if active)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="refresh_tokens_pkey"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="refresh_tokens_user_id_fkey",
            ondelete="CASCADE",
        ),
        comment="JWT refresh tokens storage - supports token refresh flow",
    )

    # Create index on user_id for user token lookup
    op.create_index(
        "ix_refresh_tokens_user_id",
        "refresh_tokens",
        ["user_id"],
        unique=False,
    )

    # Create index on token for token validation (unique already enforced by column)
    op.create_index(
        "ix_refresh_tokens_token",
        "refresh_tokens",
        ["token"],
        unique=True,
        postgresql_where=sa.text("token IS NOT NULL"),
    )

    # Create index on expires_at for cleanup of expired tokens
    op.create_index(
        "ix_refresh_tokens_expires_at",
        "refresh_tokens",
        ["expires_at"],
        unique=False,
    )

    # Create composite index on (user_id, expires_at) for active token queries
    op.create_index(
        "ix_refresh_tokens_user_id_expires_at",
        "refresh_tokens",
        ["user_id", "expires_at"],
        unique=False,
    )

    # Create index on revoked_at for filtering active tokens
    op.create_index(
        "ix_refresh_tokens_revoked_at",
        "refresh_tokens",
        ["revoked_at"],
        unique=False,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    """Drop refresh_tokens table and indexes."""
    # Drop indexes
    op.drop_index("ix_refresh_tokens_revoked_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")

    # Drop table (foreign key will be automatically dropped)
    op.drop_table("refresh_tokens")
