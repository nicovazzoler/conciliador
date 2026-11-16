"""moneda de operaciones

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-16 12:00:00

Las acciones de otras bolsas (WEGE3 en Brasil) se operan en su moneda. Lo que ya estaba queda en USD.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('operaciones', sa.Column('moneda', sa.String(length=3), server_default='USD', nullable=False))
    op.add_column('operaciones', sa.Column('tipo_cambio', sa.String(length=40), server_default='1', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('operaciones') as tabla:
        tabla.drop_column('tipo_cambio')
        tabla.drop_column('moneda')
