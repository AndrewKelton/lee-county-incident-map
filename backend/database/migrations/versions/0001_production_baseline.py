"""Baseline the production ingestion schema.

Revision ID: 0001
Revises: None
Create Date: 2026-07-12

Create the database schema that the data collection pipeline already uses.

Empty databases should run this to create the three current tables.
Existing databases should be marked as revision 0001 without running this migration.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.crawl_queries (
            query text NOT NULL,
            parent_query text,
            canonical text NOT NULL,
            depth integer NOT NULL,
            status text DEFAULT 'pending'::text NOT NULL,
            worker_id text,
            started_at timestamp with time zone,
            completed_at timestamp with time zone,
            result_count integer,
            error_message text,
            CONSTRAINT crawl_queries_pkey PRIMARY KEY (query)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.geocode_cache (
            key text NOT NULL,
            lat double precision NOT NULL,
            lon double precision NOT NULL,
            quality text,
            cached_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT geocode_cache_pkey PRIMARY KEY (key)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.incidents (
            source text NOT NULL,
            source_incident_id text NOT NULL,
            occurred_at timestamp with time zone NOT NULL,
            fetched_at timestamp with time zone NOT NULL,
            lat double precision,
            lon double precision,
            nature text,
            disposition text,
            address text,
            city text,
            geocoded_at timestamp with time zone,
            geocode_quality text,
            status text,
            raw jsonb NOT NULL,
            geocode_attempts integer DEFAULT 0 NOT NULL,
            geocode_locked_by text,
            geocode_locked_at timestamp with time zone,
            last_changed timestamp with time zone,
            CONSTRAINT incidents_pkey PRIMARY KEY (source, source_incident_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_crawl_canonical ON public.crawl_queries USING btree (canonical)"
    )
    op.execute(
        "CREATE INDEX idx_crawl_status ON public.crawl_queries USING btree (status)"
    )
    op.execute(
        "CREATE INDEX idx_incidents_location ON public.incidents USING btree (lat, lon) "
        "WHERE (lat IS NOT NULL)"
    )
    op.execute(
        "CREATE INDEX idx_incidents_occurred ON public.incidents USING btree (occurred_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_incidents_source_time "
        "ON public.incidents USING btree (source, occurred_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.incidents")
    op.execute("DROP TABLE public.geocode_cache")
    op.execute("DROP TABLE public.crawl_queries")
