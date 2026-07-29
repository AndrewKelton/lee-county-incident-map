"""Add a monotonic dataset revision for cache invalidation.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-14

The API needs one number that changes whenever anything a user can see changes, so
ETags can be correct instead of guessed. No existing column can do that job:

    max(fetched_at)  is first-seen time. The upsert never lists fetched_at in its
                     DO UPDATE SET, so it is frozen the moment a row is inserted.
    max(last_changed) advances on a status change but not on a geocode.
                     mark_geocoded writes lat, lon and geocoded_at and leaves
                     last_changed alone, so 10k rows appearing on the map would
                     not move it.

So the revision is maintained by a trigger on incidents. That keeps the pipeline
unchanged: nothing in the Lambda or the workers knows this exists.

The trigger is FOR EACH STATEMENT, not per row, so an hourly flush of 1500
incidents bumps the revision once rather than 1500 times.

The transition table is the part that matters. A statement-level trigger fires even
when the statement changed nothing, and the flush re-sends every open incident
every hour, so most upserts change no rows at all. Without the EXISTS check on the
transition table, a completely quiet hour would still bump the revision and blow
every client's cache for nothing.

Separate triggers for insert and update because Postgres will not accept a
transition table on a trigger with more than one event. There is no delete trigger:
nothing deletes incidents.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.dataset_revision (
            id         boolean     PRIMARY KEY DEFAULT true CHECK (id),
            revision   bigint      NOT NULL DEFAULT 1,
            changed_at timestamptz NOT NULL DEFAULT now(),
            reason     text
        )
        """
    )
    op.execute("INSERT INTO public.dataset_revision (id) VALUES (true)")

    op.execute(
        """
        CREATE FUNCTION public.bump_dataset_revision() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (SELECT 1 FROM changed) THEN
                UPDATE public.dataset_revision
                SET revision   = revision + 1,
                    changed_at = now(),
                    reason     = TG_TABLE_NAME || ' ' || lower(TG_OP);
            END IF;
            RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER incidents_revision_on_insert
            AFTER INSERT ON public.incidents
            REFERENCING NEW TABLE AS changed
            FOR EACH STATEMENT EXECUTE FUNCTION public.bump_dataset_revision()
        """
    )
    op.execute(
        """
        CREATE TRIGGER incidents_revision_on_update
            AFTER UPDATE ON public.incidents
            REFERENCING NEW TABLE AS changed
            FOR EACH STATEMENT EXECUTE FUNCTION public.bump_dataset_revision()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS incidents_revision_on_update ON public.incidents")
    op.execute("DROP TRIGGER IF EXISTS incidents_revision_on_insert ON public.incidents")
    op.execute("DROP FUNCTION IF EXISTS public.bump_dataset_revision()")
    op.execute("DROP TABLE IF EXISTS public.dataset_revision")