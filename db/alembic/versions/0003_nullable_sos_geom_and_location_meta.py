"""Allow NULL geom on community_sos and add location verification metadata

Revision ID: 0003_nullable_sos_geom
Revises: 0002_multi_hazard_schema
Create Date: 2026-11-25 11:02:00.000000

"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0003_nullable_sos_geom'
down_revision: Union[str, Sequence[str], None] = '0002_multi_hazard_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE community_sos
            ALTER COLUMN geom DROP NOT NULL;

        ALTER TABLE community_sos
            ADD COLUMN IF NOT EXISTS location_source TEXT NOT NULL DEFAULT 'manual',
            ADD COLUMN IF NOT EXISTS location_accuracy_m DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS location_captured_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS location_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS location_description TEXT,
            ADD COLUMN IF NOT EXISTS location_landmark TEXT;
    """)


def downgrade() -> None:
    # Kiểm tra trước khi xóa metadata: nếu còn bản ghi geom IS NULL thì dừng rollback ngay để bảo toàn dữ liệu định vị
    op.execute("""
        DO $$
        DECLARE
            null_geom_count INTEGER;
        BEGIN
            SELECT COUNT(*) INTO null_geom_count FROM community_sos WHERE geom IS NULL;
            IF null_geom_count > 0 THEN
                RAISE EXCEPTION 'Không thể rollback migration 0003_nullable_sos_geom: còn % bản ghi SOS có geom IS NULL. Vui lòng bổ sung tọa độ hoặc xử lý trước khi downgrade để tránh mất location_description/location_landmark.', null_geom_count;
            END IF;

            ALTER TABLE community_sos
                ALTER COLUMN geom SET NOT NULL;

            ALTER TABLE community_sos
                DROP COLUMN IF EXISTS location_landmark,
                DROP COLUMN IF EXISTS location_description,
                DROP COLUMN IF EXISTS location_confirmed,
                DROP COLUMN IF EXISTS location_captured_at,
                DROP COLUMN IF EXISTS location_accuracy_m,
                DROP COLUMN IF EXISTS location_source;
        END $$;
    """)
