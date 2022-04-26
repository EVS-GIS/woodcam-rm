"""add recording parameters

Revision ID: 77b752ddd223
Revises: 6d037e99c04d
Create Date: 2022-04-26 13:31:59.356854

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '77b752ddd223'
down_revision = '6d037e99c04d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('stations', sa.Column('rec_resolution', sa.String(length=12), nullable=True))
    op.add_column('stations', sa.Column('rec_fps', sa.Integer(), nullable=True))
    op.add_column('stations', sa.Column('rec_codec', sa.String(length=12), nullable=True))
    op.add_column('stations', sa.Column('rec_compression', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('stations', 'rec_compression')
    op.drop_column('stations', 'rec_codec')
    op.drop_column('stations', 'rec_fps')
    op.drop_column('stations', 'rec_resolution')
    # ### end Alembic commands ###
