"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-08-31

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("address", sa.String(255), nullable=False),
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("onboarding_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)

    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("tastes", sa.JSON(), nullable=True),
        sa.Column("drink_types", sa.JSON(), nullable=True),
        sa.Column("temperature", sa.String(10), nullable=True),
        sa.Column("caffeine", sa.String(10), nullable=True),
        sa.Column("allergies", sa.JSON(), nullable=True),
        sa.Column("dietary_restrictions", sa.JSON(), nullable=True),
    )

    op.create_table(
        "menu_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("ingredients", sa.JSON(), nullable=True),
        sa.Column("price", sa.Numeric(6, 2), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_chat_messages_user_id", "chat_messages", ["user_id"])

    op.create_table(
        "favorites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("menu_item_id", sa.Integer(), sa.ForeignKey("menu_items.id"), nullable=False),
        sa.UniqueConstraint("user_id", "menu_item_id", name="uq_user_menu_item"),
    )
    op.create_index("ix_favorites_user_id", "favorites", ["user_id"])


def downgrade() -> None:
    op.drop_table("favorites")
    op.drop_table("chat_messages")
    op.drop_table("menu_items")
    op.drop_table("user_preferences")
    op.drop_table("users")
