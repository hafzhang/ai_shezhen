"""create users table

Revision ID: 20260221_us102
Revises:
Create Date: 2026-02-21

AI舌诊智能诊断系统 - Users Table Migration
Phase 2: Database & Auth - US-102

This migration creates the users table with:
- UUID primary key
- WeChat/Douyin openid fields (nullable)
- Phone/Email fields (nullable with unique constraint)
- User profile fields (nickname, avatar_url)
- Password hash for traditional login
- Timestamps (created_at, updated_at, deleted_at)
- Indexes for common query patterns

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260221_us102"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create users table with indexes."""
    # Create users table
    op.create_table(
        "users",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("openid", sa.String(100), nullable=True, comment="WeChat/Douyin openid"),
        sa.Column(
            "openid_type",
            sa.Enum("wechat", "douyin", name="openidtype"),
            nullable=True,
            comment="OpenID provider type",
        ),
        sa.Column("phone", sa.String(20), nullable=True, unique=True, comment="Phone number"),
        sa.Column(
            "email", sa.String(255), nullable=True, unique=True, comment="Email address"
        ),
        sa.Column("nickname", sa.String(100), nullable=True, comment="User nickname"),
        sa.Column(
            "avatar_url", sa.String(500), nullable=True, comment="Avatar image URL"
        ),
        sa.Column(
            "password_hash", sa.String(255), nullable=True, comment="Bcrypt password hash"
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
            "deleted_at", sa.DateTime(timezone=True), nullable=True, comment="Soft delete timestamp"
        ),
        sa.PrimaryKeyConstraint("id", name="users_pkey"),
        comment="User accounts table - supports WeChat/Douyin mini-program and traditional login",
    )

    # Create index on openid for mini-program user lookup
    op.create_index(
        "ix_users_openid",
        "users",
        ["openid"],
        unique=False,
        postgresql_where=sa.text("openid IS NOT NULL"),
    )

    # Create index on phone for phone login lookup
    op.create_index(
        "ix_users_phone",
        "users",
        ["phone"],
        unique=True,
        postgresql_where=sa.text("phone IS NOT NULL"),
    )

    # Create index on email for email login lookup
    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )

    # Create composite index on created_at for time-based queries
    op.create_index("ix_users_created_at", "users", ["created_at"], unique=False)

    # Create index on deleted_at for soft delete filtering
    op.create_index(
        "ix_users_deleted_at",
        "users",
        ["deleted_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Drop users table and indexes."""
    # Drop indexes
    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_index("ix_users_created_at", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_phone", table_name="users")
    op.drop_index("ix_users_openid", table_name="users")

    # Drop enum type
    op.execute("DROP TYPE IF EXISTS openidtype")

    # Drop table
    op.drop_table("users")
