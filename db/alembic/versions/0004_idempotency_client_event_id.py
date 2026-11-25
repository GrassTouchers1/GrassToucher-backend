"""Add client_event_id and payload_hash idempotency to community_sos and reports

Revision ID: 0004_idempotency_client_event_id
Revises: 0003_nullable_sos_geom
Create Date: 2026-11-25 11:25:00.000000

"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0004_idempotency_client_event_id'
down_revision: Union[str, Sequence[str], None] = '0003_nullable_sos_geom'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE community_sos
            ADD COLUMN IF NOT EXISTS client_event_id TEXT,
            ADD COLUMN IF NOT EXISTS payload_hash TEXT;

        CREATE UNIQUE INDEX IF NOT EXISTS uq_community_sos_client_event_id
            ON community_sos (client_event_id)
            WHERE client_event_id IS NOT NULL;

        ALTER TABLE reports
            ADD COLUMN IF NOT EXISTS client_event_id TEXT,
            ADD COLUMN IF NOT EXISTS payload_hash TEXT;

        CREATE UNIQUE INDEX IF NOT EXISTS uq_reports_client_event_id
            ON reports (client_event_id)
            WHERE client_event_id IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS uq_reports_client_event_id;
        ALTER TABLE reports
            DROP COLUMN IF EXISTS payload_hash,
            DROP COLUMN IF EXISTS client_event_id;

        DROP INDEX IF EXISTS uq_community_sos_client_event_id;
        ALTER TABLE community_sos
            DROP COLUMN IF EXISTS payload_hash,
            DROP COLUMN IF EXISTS client_event_id;
    """)
