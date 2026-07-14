"""Add the indexes the public API read path needs.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-14

Only the incident-side indexes. The spec also lists indexes for refresh tokens,
saved areas and reports, but those tables do not exist yet, so they belong with
the migration that creates them.

What the API actually queries, and what covers it:

    map viewport            geom && envelope            incidents_geom_gix (0004)
    list, newest first      keyset on (occurred_at,     incidents_keyset
                            source, source_incident_id)
    filter by category      nature = ANY(...)           incidents_nature_time
                            then sort by time
    filter by city          city = ANY(...)             incidents_city_time
                            then sort by time
    address search          address ILIKE '%main%'      incidents_address_trgm

The category and city filters both resolve to a list of raw values first (a nature
list from nature_categories, a spelling list from city_aliases) and then hit
incidents. So the index they need is on the raw column, not on the canonical one.

Address search needs trigrams rather than a prefix index because people type
fragments of a street name, not the start of an address.

No index on location_quality. It is true for 99.4% of geocoded rows, so it filters
almost nothing and an index on it would never be chosen.

No index on disposition yet. It would be a good filter dimension, but no endpoint
asks for it, and a speculative index costs write throughput on every flush.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX incidents_keyset
            ON public.incidents (occurred_at DESC, source DESC, source_incident_id DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX incidents_nature_time
            ON public.incidents (nature, occurred_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX incidents_city_time
            ON public.incidents (city, occurred_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX incidents_address_trgm
            ON public.incidents USING GIN (address gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.incidents_address_trgm")
    op.execute("DROP INDEX IF EXISTS public.incidents_city_time")
    op.execute("DROP INDEX IF EXISTS public.incidents_nature_time")
    op.execute("DROP INDEX IF EXISTS public.incidents_keyset")