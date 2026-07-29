"""Make incidents.last_changed NOT NULL.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-13

The ingestion upsert compares EXCLUDED.fetched_at > incidents.last_changed. When
last_changed is NULL that comparison is NULL, not false, so the row never
updates. The branch that would refill last_changed sits behind the same
condition, so the row cannot recover on its own.

The pipeline used to refill it on every connection. Commit 2b6e806 removed that.

Production had no NULL rows on 2026-07-13, so the backfill below does nothing
there.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute(
        """
        UPDATE public.incidents
        SET last_changed = fetched_at
        WHERE last_changed IS NULL
        """
    )
    op.execute(
        "ALTER TABLE public.incidents ALTER COLUMN last_changed SET NOT NULL"
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute(
        "ALTER TABLE public.incidents ALTER COLUMN last_changed DROP NOT NULL"
    )
