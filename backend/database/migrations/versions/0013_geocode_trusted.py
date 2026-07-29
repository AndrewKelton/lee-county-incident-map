"""Flag coordinates from the geocoder tiers that return road centroids.

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-14

location_quality (0005) catches a geocode that lands in Chicago. It cannot catch one
that lands in the middle of Colonial Boulevard, because the middle of Colonial
Boulevard is very much inside Lee County.

Nominatim's road-class tiers do exactly that. They match a street name and return the
centre of the street, and a primary road is kilometres long. Measured against the
CommunityCrimeMap import, which gives a true coordinate for 20,109 of our geocoded
rows, the error rate by tier is:

    nominatim:primary        87.9% wrong by more than 2km, median error 7.5km
    nominatim:tertiary       50.0%
    AMBIGUOUS                36.9%
    nominatim:secondary      30.8%
    nominatim:residential    18.2%
    EXACT (Census)            0.8%
    nominatim:house           0.0%
    overpass:intersection     0.0%   of 4,821 rows

Only the first two are distrusted here. That hides 1,190 rows, about 0.45% of the
geocoded set, at 86% precision: 97 genuinely wrong against 16 good ones lost.

Widening the rule to include AMBIGUOUS, secondary and residential was measured and
rejected. It drops to 51% precision, which throws away as many correct incidents as
wrong ones. Do not "improve" this by adding tiers without measuring first.

Census EXACT cannot be fixed this way. Its error rate is only 0.8%, but it owns 94,157
rows, so it is still the largest single source of bad pins at roughly 776. Distrusting
the tier would hide 94k rows to catch those. That residue is 0.29% of the dataset and
is accepted.

NULL means there are no coordinates at all, matching how location_quality reads. So the
map filter is `location_quality = 'in_county' AND geocode_trusted`, and both are null
safe.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UNTRUSTED = ("nominatim:primary", "nominatim:tertiary")


def upgrade() -> None:
    tiers = ", ".join(f"'{tier}'" for tier in UNTRUSTED)
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute(
        f"""
        ALTER TABLE public.incidents
            ADD COLUMN geocode_trusted boolean
            GENERATED ALWAYS AS (
                CASE
                    WHEN lat IS NULL THEN NULL
                    WHEN COALESCE(geocode_quality, '') IN ({tiers}) THEN false
                    ELSE true
                END
            ) STORED
        """
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("ALTER TABLE public.incidents DROP COLUMN IF EXISTS geocode_trusted")
