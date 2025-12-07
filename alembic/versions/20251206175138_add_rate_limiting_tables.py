"""add rate limiting tables

Revision ID: 20251206175138
Revises: ac696a9ca787
Create Date: 2025-12-06 17:51:38.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20251206175138'
down_revision: Union[str, None] = 'ac696a9ca787'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add rate limiting tables."""

    # Create enum type for scope_type
    scope_type_enum = postgresql.ENUM('global', 'model', 'group_model', name='scope_type_enum', create_type=True)
    scope_type_enum.create(op.get_bind(), checkfirst=True)

    # Create rate_limits table
    op.create_table(
        'rate_limits',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('scope_type', sa.Enum('global', 'model', 'group_model', name='scope_type_enum'), nullable=False),
        sa.Column('scope_id', sa.String(length=255), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scope_type', 'scope_id', name='uq_rate_limit_scope')
    )

    # Create indexes on rate_limits
    op.create_index('ix_rate_limits_scope_type', 'rate_limits', ['scope_type'])
    op.create_index('ix_rate_limits_scope_id', 'rate_limits', ['scope_id'])
    op.create_index('ix_rate_limits_enabled', 'rate_limits', ['enabled'])

    # Create rate_limit_windows table
    op.create_table(
        'rate_limit_windows',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('rate_limit_id', sa.Integer(), nullable=False),
        sa.Column('from_time', sa.Time(), nullable=False),
        sa.Column('to_time', sa.Time(), nullable=False),
        sa.Column('max_requests', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('max_tokens', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.ForeignKeyConstraint(['rate_limit_id'], ['rate_limits.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('max_requests >= -1', name='ck_max_requests_valid'),
        sa.CheckConstraint('max_tokens >= -1', name='ck_max_tokens_valid'),
        sa.CheckConstraint('to_time > from_time', name='ck_time_ordering')
    )

    # Create index on rate_limit_windows
    op.create_index('ix_rate_limit_windows_rate_limit_id', 'rate_limit_windows', ['rate_limit_id'])


def downgrade() -> None:
    """Downgrade schema to remove rate limiting tables."""

    # Drop tables
    op.drop_index('ix_rate_limit_windows_rate_limit_id', table_name='rate_limit_windows')
    op.drop_table('rate_limit_windows')

    op.drop_index('ix_rate_limits_enabled', table_name='rate_limits')
    op.drop_index('ix_rate_limits_scope_id', table_name='rate_limits')
    op.drop_index('ix_rate_limits_scope_type', table_name='rate_limits')
    op.drop_table('rate_limits')

    # Drop enum type
    scope_type_enum = postgresql.ENUM('global', 'model', 'group_model', name='scope_type_enum')
    scope_type_enum.drop(op.get_bind(), checkfirst=True)
