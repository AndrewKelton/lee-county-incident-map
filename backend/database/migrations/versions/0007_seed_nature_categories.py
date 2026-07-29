"""Seed the categories and map every nature the feed has ever sent.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-14

All 110 natures present in production on 2026-07-14 are mapped, so nothing falls
back to OTHER today. OTHER exists for the natures the feed has not invented yet.
It gained one between this batch being planned and being written, so it will.

The strings must match the feed byte for byte, typos included. DAV has two spaces
before the parenthesis, and the source really does spell them CARJACKING W
FA/WAEPON and DEATH INVEST - UNDETERMINDED.

Two things worth knowing before reading the map.

DISTURBANCE is 45% of every incident on its own. That is not a mapping mistake, it
is what the Sheriff's own catch-all bucket looks like, and the feed carries no
field that could split it. Any analysis over all incidents is mostly an analysis
of DISTURBANCE.

The judgment calls, so they can be argued with: DOMESTIC VIOLENCE is VIOLENT but
DOMESTIC DISTURBANCE is DISTURBANCE. Recovered guns are FIREARM. INDECENT EXPOSURE
is HARASSMENT. RECOVERED OUT OF COUNTY is assumed to
be a vehicle, since every other RECOVER nature is property or a vehicle.

Idempotent, so re-running it re-asserts the mapping rather than failing.
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# code -> (label, sort order in the frontend filter)
CATEGORIES = {
    "VIOLENT":     ("Violent Crime",          10),
    "FIREARM":     ("Shots Fired & Firearms", 20),
    "BURGLARY":    ("Burglary",               30),
    "THEFT":       ("Theft & Property",       40),
    "VEHICLE":     ("Vehicle Crime",          50),
    "FRAUD":       ("Fraud & Financial",      60),
    "DRUGS":       ("Drugs & Narcotics",      70),
    "HARASSMENT":  ("Harassment & Stalking",  80),
    "DISTURBANCE": ("Disturbance",            90),
    "TRAFFIC":     ("Traffic",               100),
    "DEATH":       ("Death Investigation",   110),
    "ANIMAL":      ("Animal",                120),
    "HAZARD":      ("Bomb & Hazard",         130),
    "OTHER":       ("Other",                 999),
}

NATURES = {
    "VIOLENT": [
        "DOMESTIC VIOLENCE", "BATTERY", "ASSAULT/BATTERY", "ASSAULT", "ROBBERY",
        "BATTERY - 65+ OR OLDER", "ROBBERY W FIREARM", "HOMICIDE",
        "ROBBERY NO FIREARM/WEAPON", "KIDNAPPING / ABDUCTION", "STABBING",
        "BATTERY LEO", "ROBBERY W WEAPON", "HUMAN TRAFFICKING",
        "BATTERY - SCHOOL OFFICIAL", "CARJACKING", "CARJACKING W FA/WAEPON",
        "KIDNAPPING/ABDUCTION/FL", "CARJACKING NO FA/WEAPON",
        "ASSAULT/BATTERY AGAINST LEO", "VIOLENT CRIME",
    ],
    "FIREARM": [
        "SHOTS FIRED/HEARD", "SHOTS FIRED", "RECOVER FOUND GUN",
        "SHOOT/THROW DEADLY MISSLE", "RECOVER GUN", "SHOOTING - OCCUPIED DWELLING",
        "SHOOTING", "PROJECTING DEADLY MISSILE", "SHOOTING - OCCUPIED CONVEYANCE",
        "SHOOTING - ACCIDENTAL", "THROW/SHOOT MISSILE/WEAPON",
    ],
    "BURGLARY": [
        "BURGLARY - RESIDENCE", "BURGLARY - CONV", "BURGLARY - RESD",
        "BURGLARY - STRUCTURE", "BURGLARY - BUSINESS", "BURGLARY - STRUC",
        "BURGLARY - BUSN", "BURGLARY",
    ],
    "THEFT": [
        "GRAND THEFT", "THEFT MISD", "RECOVER STOLEN PROP", "RECOVER PROP",
        "GRAND THEFT - RETAIL", "ILLEGAL DUMPING", "GRAND THEFT - CONSTRUCTION SITE",
        "RECOVER PROPERTY", "THEFT", "THEFT - GRAND",
        "GRAND THEFT - CATALYTIC CONVERTER", "THEFT - LARCENY", "VANDALISM",
        "SHOPLIFTER", "THEFT - TRADE SECRETS", "RECOVER CARGO",
    ],
    "VEHICLE": [
        "STOLEN LICENSE PLATE/DECAL", "RECOVER STOLEN VEHICLE", "RECOVER VEHICLE",
        "STOLEN VEHICLE", "STOLEN PLATE", "STOLEN BOAT/WATERCRAFT",
        "RECOVER MOTOR VEHICLE", "STOLEN HEAVY EQUIPMENT", "RECOVER STOLEN BOAT",
        "RECOVER BOAT", "STOLEN BOAT", "RECOVER HEAVY EQUIP",
        "RECOVERED OUT OF COUNTY", "STOLEN HEAVY EQUIP", "GRAND THEFT AUTO",
        "RECOVER STOLEN HEAVY EQUIP", "STOLEN FARM EQUIPMENT",
    ],
    "FRAUD": [
        "FRAUD", "IDENTITY THEFT", "FRAUD LINE", "INTERNET CRIMES", "FORGERY",
        "ECONOMIC CRIME",
    ],
    "DRUGS": [
        "DRUG", "NARCOTICS", "NARCOTICS MISD", "NARCOTICS TIP", "NARCOTICS FELONY",
    ],
    "HARASSMENT": [
        "HARASSMENT", "INDECENT EXPOSURE", "STALKING", "CYBER STALKING",
        "AGG STALKING",
    ],
    "DISTURBANCE": [
        "DISTURBANCE", "DOMESTIC DISTURBANCE",
    ],
    "TRAFFIC": [
        "CRASH", "DAV  (DISABLED VEHICLE)", "HIT AND RUN CRASH", "TRAFFIC CONTROL",
    ],
    "DEATH": [
        "DEATH INVESTIGATION", "DEATH INVEST - NATURAL", "DEATH INVEST - OVERDOSE",
        "DEATH INVEST - ACCIDENTAL", "DEATH INVEST - SUICIDE",
        "DEATH INVEST - UNDETERMINDED",
    ],
    "ANIMAL": [
        "ANIMAL", "ANIMAL LIVESTOCK", "ANIMAL CRUELTY",
    ],
    "HAZARD": [
        "BOMB SQUAD OPERATION", "BOMB THREAT", "BOMB PUBLIC DISPLAY",
        "BOMB/SUSPICIOUS ITEM", "BOMB / SUSP ITEM", "BOMB DEMOLITIONS",
    ],
}

CATEGORY_SQL = text(
    """
    INSERT INTO public.incident_categories (code, label, sort_order)
    VALUES (:code, :label, :sort_order)
    ON CONFLICT (code) DO UPDATE
        SET label = EXCLUDED.label,
            sort_order = EXCLUDED.sort_order,
            updated_at = now()
    """
)

NATURE_SQL = text(
    """
    INSERT INTO public.nature_categories (nature, category_code)
    VALUES (:nature, :code)
    ON CONFLICT (nature) DO UPDATE
        SET category_code = EXCLUDED.category_code,
            updated_at = now()
    """
)


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        CATEGORY_SQL,
        [
            {"code": code, "label": label, "sort_order": sort_order}
            for code, (label, sort_order) in CATEGORIES.items()
        ],
    )
    bind.execute(
        NATURE_SQL,
        [
            {"nature": nature, "code": code}
            for code, natures in NATURES.items()
            for nature in natures
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM public.nature_categories")
    # OTHER is created by 0006 and is the read-path fallback, so it survives.
    op.execute("DELETE FROM public.incident_categories WHERE code <> 'OTHER'")
