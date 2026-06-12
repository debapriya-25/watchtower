"""rename auth tokens to refresh_tokens and add token catalogue

Phase 2 repurposes the ``Token`` domain name for the crypto catalogue (per the
PRD). The Phase 1 authentication refresh-token table (formerly ``tokens``) is
moved to ``refresh_tokens``, and a fresh ``tokens`` table is created for the
catalogue.

Refresh-token rows are ephemeral (users simply re-authenticate), so this
migration drops and recreates rather than migrating data — which also keeps it
safe to run regardless of existing row counts.

Revision ID: 906ff88e1959
Revises: cf5038407d15
Create Date: 2026-06-12 16:01:30.557625

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '906ff88e1959'
down_revision: Union[str, None] = 'cf5038407d15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Authentication refresh tokens: tokens -> refresh_tokens ----------
    op.drop_index(op.f('ix_tokens_jti'), table_name='tokens')
    op.drop_index(op.f('ix_tokens_user_id'), table_name='tokens')
    op.drop_table('tokens')

    op.create_table(
        'refresh_tokens',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('jti', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_refresh_tokens_jti'), 'refresh_tokens', ['jti'], unique=True)
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)

    # --- Crypto catalogue: new tokens table ------------------------------
    op.create_table(
        'tokens',
        sa.Column('symbol', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('coingecko_id', sa.String(length=120), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tokens_coingecko_id'), 'tokens', ['coingecko_id'], unique=True)
    op.create_index(op.f('ix_tokens_is_active'), 'tokens', ['is_active'], unique=False)
    op.create_index(op.f('ix_tokens_symbol'), 'tokens', ['symbol'], unique=False)


def downgrade() -> None:
    # --- Drop catalogue tokens -------------------------------------------
    op.drop_index(op.f('ix_tokens_symbol'), table_name='tokens')
    op.drop_index(op.f('ix_tokens_is_active'), table_name='tokens')
    op.drop_index(op.f('ix_tokens_coingecko_id'), table_name='tokens')
    op.drop_table('tokens')

    # --- Restore auth tokens table ---------------------------------------
    op.create_table(
        'tokens',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('jti', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tokens_jti'), 'tokens', ['jti'], unique=True)
    op.create_index(op.f('ix_tokens_user_id'), 'tokens', ['user_id'], unique=False)

    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_jti'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
