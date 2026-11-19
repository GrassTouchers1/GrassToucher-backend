# Copyright 2026 GrassTouchers Team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""Multi-Hazard Disaster, Shelter, and SOS schemas

Revision ID: 0002_multi_hazard_schema
Revises: 0001_initial_baseline
Create Date: 2026-11-17 03:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002_multi_hazard_schema'
down_revision: Union[str, Sequence[str], None] = '0001_initial_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Custom enum types
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE disaster_type AS ENUM ('flood', 'landslide', 'storm', 'heavy_rain', 'flash_flood', 'other');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE disaster_severity AS ENUM ('low', 'medium', 'high', 'critical');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE disaster_status AS ENUM ('warning', 'active', 'receding', 'resolved');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE shelter_status AS ENUM ('open', 'full', 'closed');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE sos_priority AS ENUM ('low', 'medium', 'high', 'critical');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE sos_status AS ENUM ('pending', 'acknowledged', 'dispatched', 'rescued', 'cancelled');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    # 2. Table: disaster_events
    op.execute("""
        CREATE TABLE IF NOT EXISTS disaster_events (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            hazard_type disaster_type NOT NULL DEFAULT 'flood',
            severity disaster_severity NOT NULL DEFAULT 'medium',
            status disaster_status NOT NULL DEFAULT 'active',
            description TEXT,
            geom geometry(Geometry, 4326) NOT NULL,
            radius_m NUMERIC(8, 1) DEFAULT 100.0,
            start_time TIMESTAMPTZ NOT NULL DEFAULT now(),
            end_time TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_disaster_events_geom ON disaster_events USING GIST (geom);
        CREATE INDEX IF NOT EXISTS idx_disaster_events_status ON disaster_events (status);
    """)

    # 3. Table: evacuation_shelters
    op.execute("""
        CREATE TABLE IF NOT EXISTS evacuation_shelters (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT,
            geom geometry(Point, 4326) NOT NULL,
            capacity INT NOT NULL DEFAULT 200,
            current_occupancy INT NOT NULL DEFAULT 0,
            contact_phone TEXT,
            supplies_status TEXT DEFAULT 'Sẵn sàng (Lương thực & Y tế)',
            status shelter_status NOT NULL DEFAULT 'open',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_evacuation_shelters_geom ON evacuation_shelters USING GIST (geom);
        CREATE INDEX IF NOT EXISTS idx_evacuation_shelters_status ON evacuation_shelters (status);
    """)

    # 4. Table: community_sos
    op.execute("""
        CREATE TABLE IF NOT EXISTS community_sos (
            id SERIAL PRIMARY KEY,
            contact_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            geom geometry(Point, 4326) NOT NULL,
            people_count INT NOT NULL DEFAULT 1,
            has_elderly_or_children BOOLEAN NOT NULL DEFAULT FALSE,
            water_level_cm NUMERIC(6, 1) DEFAULT 0.0,
            priority sos_priority NOT NULL DEFAULT 'high',
            status sos_status NOT NULL DEFAULT 'pending',
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_community_sos_geom ON community_sos USING GIST (geom);
        CREATE INDEX IF NOT EXISTS idx_community_sos_status ON community_sos (status);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS community_sos CASCADE;")
    op.execute("DROP TABLE IF EXISTS evacuation_shelters CASCADE;")
    op.execute("DROP TABLE IF EXISTS disaster_events CASCADE;")
    op.execute("DROP TYPE IF EXISTS sos_status;")
    op.execute("DROP TYPE IF EXISTS sos_priority;")
    op.execute("DROP TYPE IF EXISTS shelter_status;")
    op.execute("DROP TYPE IF EXISTS disaster_status;")
    op.execute("DROP TYPE IF EXISTS disaster_severity;")
    op.execute("DROP TYPE IF EXISTS disaster_type;")
