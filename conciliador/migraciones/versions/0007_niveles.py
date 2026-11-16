"""stop loss y take profit

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-16 22:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('niveles',
    sa.Column('activo', sa.String(length=20), nullable=False),
    sa.Column('moneda', sa.String(length=3), server_default='USD', nullable=False),
    sa.Column('stop_loss', sa.String(length=40), nullable=True),
    sa.Column('take_profit', sa.String(length=40), nullable=True),
    sa.Column('tocado', sa.String(length=12), nullable=True),
    sa.Column('tocado_el', sa.Date(), nullable=True),
    sa.PrimaryKeyConstraint('activo')
    )


def downgrade() -> None:
    op.drop_table('niveles')
