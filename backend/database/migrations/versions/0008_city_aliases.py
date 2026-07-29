"""Map the city spellings the feed uses onto canonical municipalities.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-14

The feed sends 88 distinct city strings for what is really a handful of towns, and
it truncates inconsistently. Three cities are genuinely broken today. A user
filtering the frontend by the correct spelling would see:

    NORTH FORT MYERS    5,125 of 13,038 rows    39%
    FORT MYERS BEACH      867 of  1,922 rows    45%
    SAINT JAMES CITY      210 of    452 rows    46%

FORT MYERS and LEHIGH ACRES have variants too, but they already resolve over 99%
of their rows, so those entries are only here because they cost nothing.

incidents.city and incidents.raw are never touched. This is a read-side lookup:

    LEFT JOIN city_aliases ca ON ca.raw_city = i.city
    ... CASE WHEN ca.raw_city IS NOT NULL THEN ca.canonical_city ELSE i.city END

A canonical_city of NULL means the feed gave no usable municipality, which is how
blanks, 'LEE CTY' and a stray zip code stay distinguishable from a real town. A
spelling nobody has mapped falls through to the raw value rather than failing.

Deliberately not mapped:

    'CAP' (5 rows) is Cape Coral or Captiva and none of its rows are geocoded, so
    there is nothing to disambiguate it with. Guessing would be worse than leaving
    it alone.

    Punta Gorda, Naples, Chicago, Philadelphia and the rest of the long tail are
    real places. They are not misspellings of Lee County towns and they stay as
    they are.

'FT' is Fort Myers. Its geocoded rows sit 2.0km from the Fort Myers centroid and
15.2km from Fort Myers Beach.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# canonical -> the raw spellings that mean it
ALIASES = {
    "NORTH FORT MYERS": [
        "NORTH FORT MYER", "N FORT MYERS", "N FT MYERS", "N F", "NORTH FT MYERS",
        "NFM", "N. FT. MYERS", "NORTH FT. MYERS", "NFORT MYERS", "N. FORT MYERS",
        "NORT FTMYERS",
    ],
    "FORT MYERS": [
        "FT MYERS", "FT", "FT. MYERS", "FORT MYERS 33913",
    ],
    "FORT MYERS BEACH": [
        "FORT MYERS BEAC", "FT MYERS BEACH", "FORT MYERS BCH",
    ],
    "SAINT JAMES CITY": [
        "ST JAMES CITY", "ST. JAMES CITY", "SAINT JAMES CIT",
    ],
    "LEHIGH ACRES": [
        "LEHIGH", "LEH", "LEIGH ACRES", "LEHIGHACRES", "LEHIGH ACRES,",
        "LEHIGH  ACRES", "LEHIGH ACRFES", "LEEHIGH ACRES",
    ],
    "ESTERO": [
        "ETSERO",
    ],
}

# Not a municipality. These read as NULL so the API can tell "no city" from a real town.
NO_CITY = ["", "LEE CTY", "COUNTY", "FLORIDA", "33919", "33971"]

ALIAS_SQL = text(
    """
    INSERT INTO public.city_aliases (raw_city, canonical_city)
    VALUES (:raw_city, :canonical_city)
    ON CONFLICT (raw_city) DO UPDATE
        SET canonical_city = EXCLUDED.canonical_city
    """
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.city_aliases (
            raw_city       text PRIMARY KEY,
            canonical_city text
        )
        """
    )
    rows = [
        {"raw_city": raw, "canonical_city": canonical}
        for canonical, spellings in ALIASES.items()
        for raw in spellings
    ]
    rows += [{"raw_city": raw, "canonical_city": None} for raw in NO_CITY]
    op.get_bind().execute(ALIAS_SQL, rows)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.city_aliases")