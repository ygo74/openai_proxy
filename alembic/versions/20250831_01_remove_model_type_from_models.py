"""Drop model_type and api_version columns from models table."""

from alembic import op
import sqlalchemy as sa

# Replace with your real revision IDs
revision: str = "20250831_01_remove_model_type_from_models"
down_revision: str | None = None  # set to previous revision ID if you have one
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove the polymorphic discriminator 'model_type' and legacy 'api_version' columns."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("models")}

    with op.batch_alter_table("models", schema=None) as batch_op:
        if "model_type" in columns:
            batch_op.drop_column("model_type")
        if "api_version" in columns:
            batch_op.drop_column("api_version")


def downgrade() -> None:
    """Recreate 'model_type' (NOT NULL, default backfilled) and 'api_version' (nullable)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("models")}

    # Recreate columns as nullable first
    with op.batch_alter_table("models", schema=None) as batch_op:
        if "model_type" not in columns:
            batch_op.add_column(sa.Column("model_type", sa.String(length=50), nullable=True))
        if "api_version" not in columns:
            batch_op.add_column(sa.Column("api_version", sa.String(length=50), nullable=True))

    # Backfill and set NOT NULL for model_type only
    op.execute("UPDATE models SET model_type = 'standard' WHERE model_type IS NULL")

    with op.batch_alter_table("models", schema=None) as batch_op:
        batch_op.alter_column(
            "model_type",
            existing_type=sa.String(length=50),
            nullable=False,
        )
