"""Add the category catalog and the nature to category mapping.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-14

The feed's nature field has 110 distinct values and is not an API contract. It
carries near duplicates (BURGLARY - RESIDENCE and BURGLARY - RESD), five spellings
of theft, and at least one upstream typo (CARJACKING W FA/WAEPON).

So the frontend filters on a stable category code and never on a raw nature.

incidents has no foreign key to either table. Ingestion keeps writing whatever the
feed sends, and a nature nobody has mapped yet resolves to OTHER on read:

    LEFT JOIN nature_categories nc ON nc.nature = i.nature
    ... COALESCE(nc.category_code, 'OTHER')

That is why OTHER is seeded here, in the schema, rather than in the 0007 seed. It
is the fallback every read depends on, so it has to exist even if the seed never
runs.

code is the API contract and is stable. label is display text and can be edited.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.incident_categories (
            code       text        PRIMARY KEY,
            label      text        NOT NULL,
            sort_order integer     NOT NULL,
            active     boolean     NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.nature_categories (
            nature        text        PRIMARY KEY,
            category_code text        NOT NULL REFERENCES public.incident_categories(code)
                                      ON UPDATE CASCADE,
            updated_at    timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        INSERT INTO public.incident_categories (code, label, sort_order)
        VALUES ('OTHER', 'Other', 999)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.nature_categories")
    op.execute("DROP TABLE IF EXISTS public.incident_categories")