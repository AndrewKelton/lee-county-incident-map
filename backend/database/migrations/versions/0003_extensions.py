"""Enable the PostGIS and pg_trgm extensions.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-14

postgis backs the spatial column added in 0004. pg_trgm backs fuzzy address and
nature search on the read path.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    # postgis is deliberately left in place. The postgis docker image used by CI and the local
    # stack also installs postgis_topology and postgis_tiger_geocoder, both of which depend on
    # it, so DROP EXTENSION postgis fails there. CASCADE would drop extensions this migration
    # never created. An unused extension costs one table, so leaving it is the cheaper mistake.