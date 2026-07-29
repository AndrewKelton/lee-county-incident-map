"""Flag incidents whose coordinates are implausible for Lee County.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-14

About 510 of the 103k geocoded rows sit far outside the county, some as far off as
Chicago and Nebraska. Those are geocoder misses: a street name that also 
exists elsewhere resolved to the wrong place.
Attribution as of 2026-07-14:

    overpass:intersection      0 bad of  4,820   0.00%
    EXACT                    390 bad of 93,972   0.42%
    AMBIGUOUS                238 bad of  1,433  16.61%

This migration only flags the bad rows so the API can leave them
off the map.

Generated, like geom, so nothing writes it and it cannot drift. It also repairs
itself: when the geocoder later fills in lat and lon, the flag follows.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (south, west, north, east). Lee County, padded
LEE_COUNTY_BBOX = (26.27, -82.35, 26.90, -81.50)


def upgrade() -> None:
    south, west, north, east = LEE_COUNTY_BBOX
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute(
        f"""
        ALTER TABLE public.incidents
            ADD COLUMN location_quality text
            GENERATED ALWAYS AS (
                CASE
                    WHEN lat IS NULL THEN NULL
                    WHEN lat BETWEEN {south} AND {north}
                     AND lon BETWEEN {west} AND {east} THEN 'in_county'
                    ELSE 'out_of_county'
                END
            ) STORED
        """
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("ALTER TABLE public.incidents DROP COLUMN IF EXISTS location_quality")