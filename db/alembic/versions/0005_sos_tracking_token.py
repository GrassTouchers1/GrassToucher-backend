"""Add tracking_token_hash, tracking_token_expires_at, and tracking_token_revoked to community_sos.

Revision ID: 0005_sos_tracking_token
Revises: 0004_idempotency_client_event_id
Create Date: 2026-11-25
"""
from alembic import op

revision = "0005_sos_tracking_token"
down_revision = "0004_idempotency_client_event_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE community_sos
            ADD COLUMN IF NOT EXISTS tracking_token_hash TEXT,
            ADD COLUMN IF NOT EXISTS tracking_token_expires_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS tracking_token_revoked INTEGER NOT NULL DEFAULT 0;

        CREATE UNIQUE INDEX IF NOT EXISTS uq_community_sos_tracking_token_hash
            ON community_sos (tracking_token_hash)
            WHERE tracking_token_hash IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS uq_community_sos_tracking_token_hash;
        ALTER TABLE community_sos
            DROP COLUMN IF EXISTS tracking_token_revoked,
            DROP COLUMN IF EXISTS tracking_token_expires_at,
            DROP COLUMN IF EXISTS tracking_token_hash;
    """)
