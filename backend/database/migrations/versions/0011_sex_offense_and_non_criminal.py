"""Add the SEX_OFFENSE and NON_CRIMINAL categories.

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-14

The CommunityCrimeMap import brings crime types the Sheriff's public feed does not
publish at all: 2,671 sexual offences, plus arson, DUI and weapons violations. It
also carries about 28k rows that are not crimes (welfare checks, alarms, found
property, information reports), and the frontend needs to be able to hide those
without hiding OTHER, which is a real crime we could not classify.

INDECENT EXPOSURE moves from HARASSMENT to SEX_OFFENSE. Migration 0007 put it in
HARASSMENT.

Where the two sources disagree about what a nature means, the Sheriff's vocabulary
wins, because the taxonomy is ours. CCM classes DISTURBANCE as an assault, ANIMAL
as non-criminal, and PROJECTING DEADLY MISSILE as a theft. The import re-asserts
nothing that 0007 already mapped.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO public.incident_categories (code, label, sort_order)
        VALUES ('SEX_OFFENSE',  'Sexual Offense', 25),
               ('NON_CRIMINAL', 'Non-Criminal',  900)
        ON CONFLICT (code) DO UPDATE
            SET label = EXCLUDED.label,
                sort_order = EXCLUDED.sort_order,
                updated_at = now()
        """
    )
    op.execute(
        """
        UPDATE public.nature_categories
        SET category_code = 'SEX_OFFENSE', updated_at = now()
        WHERE nature = 'INDECENT EXPOSURE'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE public.nature_categories
        SET category_code = 'HARASSMENT', updated_at = now()
        WHERE nature = 'INDECENT EXPOSURE'
        """
    )
    # The import points hundreds of natures at these two, and the foreign key blocks the
    # delete while they do. Drop those mappings rather than reassigning them to OTHER.
    # Both read as OTHER either way, but deleting them means re-running the import restores
    # the real mapping, where reassigning would leave it permanently wrong: the importer
    # inserts with ON CONFLICT DO NOTHING, so it would never correct a row that still exists.
    op.execute(
        """
        DELETE FROM public.nature_categories
        WHERE category_code IN ('SEX_OFFENSE', 'NON_CRIMINAL')
        """
    )
    op.execute(
        "DELETE FROM public.incident_categories WHERE code IN ('SEX_OFFENSE', 'NON_CRIMINAL')"
    )