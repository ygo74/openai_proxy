"""Introduce user_group_association M2M and drop users.groups JSON column."""

from alembic import op
import sqlalchemy as sa

# Set this to the previous revision in your history
revision: str = "20250831_02_user_group_m2m"
down_revision: str | None = "20250831_01_remove_model_type_from_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create association table and drop legacy column."""
    # Create user_group_association
    op.create_table(
        "user_group_association",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    )

    # Drop legacy users.groups column if present
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {col["name"] for col in inspector.get_columns("users")}
    if "groups" in user_columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("groups")


def downgrade() -> None:
    """Recreate legacy column and drop association table."""
    # Recreate users.groups column (nullable Text)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {col["name"] for col in inspector.get_columns("users")}
    if "groups" not in user_columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(sa.Column("groups", sa.Text(), nullable=True))

    # Drop association table
    op.drop_table("user_group_association")
