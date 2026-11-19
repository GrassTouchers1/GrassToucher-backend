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

"""Initial FloodNav baseline schema

Revision ID: 0001_initial_baseline
Revises: None
Create Date: 2026-11-17 03:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001_initial_baseline'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # Custom enum types
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE vehicle_type AS ENUM ('motorbike', 'car');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE reading_source AS ENUM ('sensor', 'crowd', 'ai');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE report_level AS ENUM ('light', 'medium', 'heavy');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    # 1. users
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            vehicle vehicle_type NOT NULL DEFAULT 'motorbike',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # 2. flood_points
    op.execute("""
        CREATE TABLE IF NOT EXISTS flood_points (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            geom geometry(Point, 4326) NOT NULL,
            sensor_id TEXT UNIQUE,
            threshold_cm INT NOT NULL DEFAULT 20,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_flood_points_geom ON flood_points USING GIST (geom);
    """)

    # 3. water_readings
    op.execute("""
        CREATE TABLE IF NOT EXISTS water_readings (
            id BIGSERIAL PRIMARY KEY,
            point_id INT NOT NULL REFERENCES flood_points(id) ON DELETE CASCADE,
            depth_cm NUMERIC(6,1) NOT NULL CHECK (depth_cm >= 0),
            source reading_source NOT NULL DEFAULT 'sensor',
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_readings_point_time ON water_readings (point_id, recorded_at DESC);
    """)

    # 4. reports
    op.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            user_id INT REFERENCES users(id) ON DELETE SET NULL,
            geom geometry(Point, 4326) NOT NULL,
            level report_level NOT NULL,
            photo_url TEXT,
            confirmed BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '45 minutes'
        );
        CREATE INDEX IF NOT EXISTS idx_reports_geom ON reports USING GIST (geom);
        CREATE INDEX IF NOT EXISTS idx_reports_expires ON reports (expires_at);
    """)

    # 5. predictions
    op.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id BIGSERIAL PRIMARY KEY,
            point_id INT NOT NULL REFERENCES flood_points(id) ON DELETE CASCADE,
            predicted_depth_cm NUMERIC(6,1) NOT NULL,
            horizon_min INT NOT NULL CHECK (horizon_min IN (30, 60)),
            risk_score NUMERIC(4,3) NOT NULL CHECK (risk_score BETWEEN 0 AND 1),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_predictions_point_time ON predictions (point_id, created_at DESC);
    """)

    # 6. nav_sessions
    op.execute("""
        CREATE TABLE IF NOT EXISTS nav_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id INT REFERENCES users(id) ON DELETE CASCADE,
            vehicle vehicle_type NOT NULL DEFAULT 'motorbike',
            current_pos geometry(Point, 4326),
            destination geometry(Point, 4326) NOT NULL,
            route_edges BIGINT[] NOT NULL DEFAULT '{}',
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_nav_active ON nav_sessions (active) WHERE active;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS nav_sessions CASCADE;")
    op.execute("DROP TABLE IF EXISTS predictions CASCADE;")
    op.execute("DROP TABLE IF EXISTS reports CASCADE;")
    op.execute("DROP TABLE IF EXISTS water_readings CASCADE;")
    op.execute("DROP TABLE IF EXISTS flood_points CASCADE;")
    op.execute("DROP TABLE IF EXISTS users CASCADE;")
    op.execute("DROP TYPE IF EXISTS report_level;")
    op.execute("DROP TYPE IF EXISTS reading_source;")
    op.execute("DROP TYPE IF EXISTS vehicle_type;")
