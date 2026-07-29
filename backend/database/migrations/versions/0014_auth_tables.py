"""Create users and refresh_tokens.

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-29

Uniqueness is on lower(email), so lookups must say lower(email) = lower(%s).

refresh_tokens stores sha256(token), never the token. sha256 and not argon2 because the
token is 32 random bytes, so there is nothing to brute force.

Rotation is single use and there is no reuse detection: refresh deletes the row it was
given and inserts a new one, logout deletes it. That was the agreed cut.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.users (
            id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            email         text        NOT NULL,
            password_hash text        NOT NULL,
            created_at    timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX users_email_lower_key ON public.users (lower(email))")

    op.execute(
        """
        CREATE TABLE public.refresh_tokens (
            token_hash bytea       PRIMARY KEY,
            user_id    bigint      NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
            expires_at timestamptz NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX refresh_tokens_user_id_idx ON public.refresh_tokens (user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.refresh_tokens")
    op.execute("DROP TABLE IF EXISTS public.users")
