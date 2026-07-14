"""Canonicalize the city spellings the CommunityCrimeMap import produces.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-14

CCM has no city field. The city is parsed out of a single Address string, and that
string is dirty in ways the Sheriff feed is not. Migration 0008 already covers the
spellings both sources share (NORTH FORT MYER, FORT MYERS BEAC, ST JAMES CITY,
FT MYERS, LEE CTY). These are the ones only CCM produces.

E FORT MYERS and S FORT MYERS are neighbourhoods, not municipalities. Somebody
filtering for Fort Myers wants them, and 6,539 rows say E FORT MYERS.

MYERS, MYER, CORAL and MYERS BEAC are what is left of a comma landing inside a city
name upstream ('SIX MILE CYPRESS FORT, MYERS, FL'). The importer's parser resolves
most of these on its own by letting a place name match across the stray comma, which
takes MYERS from 2,393 rows down to 580. These are the stragglers.

FLORIDA, FL and FLORIDA FT are not places. They read as NULL so the API can tell
"no city" from a real town.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ALIASES = {
    "FORT MYERS": [
        "E FORT MYERS", "S FORT MYERS", "MYERS", "FL FORT MYERS", "FL FT FORT MYERS",
        "33901 FORT MYERS",
    ],
    "NORTH FORT MYERS": ["MYER"],
    "FORT MYERS BEACH": ["MYERS BEAC"],
    "CAPE CORAL": ["CORAL"],
    "LEHIGH ACRES": ["ACRES"],
    "ESTERO": ["VILLAGIO ESTERO"],
    "ALVA": ["B ALVA"],
}

NO_CITY = ["FLORIDA", "FL", "FLORIDA FT", "FLORIDA FT N", "FL FT", "FL AVE"]

ALIAS_SQL = text(
    """
    INSERT INTO public.city_aliases (raw_city, canonical_city)
    VALUES (:raw_city, :canonical_city)
    ON CONFLICT (raw_city) DO UPDATE
        SET canonical_city = EXCLUDED.canonical_city
    """
)


def upgrade() -> None:
    rows = [
        {"raw_city": raw, "canonical_city": canonical}
        for canonical, spellings in ALIASES.items()
        for raw in spellings
    ]
    rows += [{"raw_city": raw, "canonical_city": None} for raw in NO_CITY]
    op.get_bind().execute(ALIAS_SQL, rows)


def downgrade() -> None:
    everything = [raw for spellings in ALIASES.values() for raw in spellings] + NO_CITY
    op.get_bind().execute(
        text("DELETE FROM public.city_aliases WHERE raw_city = ANY(:raws)"),
        {"raws": everything},
    )
