"""Add a generated geom column and a spatial index to incidents.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-14

geom is GENERATED from lat and lon, so nothing writes it and it cannot drift out
of step with them. The ingestion upsert names its 15 columns explicitly and the
pipeline never does SELECT *, so this column is invisible to it. No pipeline
change is needed.

The CHECK constraints are deliberately earth ranges, not a Lee County box.
Coordinates as far off as Chicago and Nebraska are already in the table from bad
geocodes, and they are flagged in 0005 rather than rejected here. Rejecting them
would mean the pipeline could no longer write a row it has already written.

Checked against production on 2026-07-14: zero rows have a partial coordinate
pair, an out of range value, NaN, or infinity, so both constraints are added
valid rather than NOT VALID.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A stored generated column rewrites the table under ACCESS EXCLUSIVE. Seconds at 113k rows.
    # The timeout is on acquiring the lock, so this fails fast instead of queueing behind a flush.
    op.execute("SET LOCAL lock_timeout = '5s'")

    op.execute(
        """
        ALTER TABLE public.incidents
            ADD COLUMN geom geometry(Point, 26959)
            GENERATED ALWAYS AS (
                ST_Transform(ST_SetSRID(ST_MakePoint(lon, lat), 4326), 26959)
            ) STORED
        """
    )
    op.execute(
        """
        ALTER TABLE public.incidents
            ADD CONSTRAINT incidents_coordinate_pair_complete
            CHECK ((lat IS NULL) = (lon IS NULL))
        """
    )
    op.execute(
        """
        ALTER TABLE public.incidents
            ADD CONSTRAINT incidents_coordinates_on_earth
            CHECK (lat IS NULL OR (lat BETWEEN -90 AND 90 AND lon BETWEEN -180 AND 180))
        """
    )
    # Not CONCURRENTLY: that cannot run inside Alembic's transaction, and a GiST build over
    # 113k rows blocks writes for about a second. Not worth the complexity.
    op.execute("CREATE INDEX incidents_geom_gix ON public.incidents USING GIST (geom)")


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("DROP INDEX IF EXISTS public.incidents_geom_gix")
    op.execute(
        "ALTER TABLE public.incidents DROP CONSTRAINT IF EXISTS incidents_coordinates_on_earth"
    )
    op.execute(
        "ALTER TABLE public.incidents DROP CONSTRAINT IF EXISTS incidents_coordinate_pair_complete"
    )
    op.execute("ALTER TABLE public.incidents DROP COLUMN IF EXISTS geom")
