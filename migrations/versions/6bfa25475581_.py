"""empty message

Revision ID: 6bfa25475581
Revises: 
Create Date: 2019-07-13 19:42:36.768609

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6bfa25475581'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('incident',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('incident', sa.String(length=250), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('location',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('location', sa.String(length=250), nullable=False),
    sa.Column('needs_moderation', sa.Boolean(), nullable=False),
    sa.Column('latitude', sa.Float(), nullable=True),
    sa.Column('longitude', sa.Float(), nullable=True),
    sa.Column('address', sa.String(length=500), nullable=True),
    sa.Column('raw', sa.String(length=10000), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('location')
    )
    op.create_table('report',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('pages', sa.Integer(), nullable=True),
    sa.Column('on_madison', sa.Boolean(), nullable=False),
    sa.Column('downloaded', sa.Boolean(), nullable=False),
    sa.Column('converted', sa.Boolean(), nullable=False),
    sa.Column('inserted', sa.Boolean(), nullable=False),
    sa.Column('report_type', sa.Enum('arrest', 'incident', name='recordtype'), nullable=True),
    sa.Column('report_text', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('record',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('incident_type', sa.Enum('arrest', 'incident', name='recordtype'), nullable=True),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('time', sa.Time(), nullable=True),
    sa.Column('case_yr', sa.Integer(), nullable=True),
    sa.Column('case_id', sa.Integer(), nullable=True),
    sa.Column('report_id', sa.Integer(), nullable=True),
    sa.Column('location_id', sa.Integer(), nullable=True),
    sa.Column('shift', sa.Integer(), nullable=True),
    sa.Column('person', sa.String(length=255), nullable=True),
    sa.Column('person_res', sa.String(length=255), nullable=True),
    sa.ForeignKeyConstraint(['location_id'], ['location.id'], ),
    sa.ForeignKeyConstraint(['report_id'], ['report.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('case_yr', 'case_id', name='_case_uc')
    )
    op.create_table('incident_to_record',
    sa.Column('record_id', sa.Integer(), nullable=False),
    sa.Column('incident_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['incident_id'], ['incident.id'], ),
    sa.ForeignKeyConstraint(['record_id'], ['record.id'], ),
    sa.PrimaryKeyConstraint('record_id', 'incident_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('incident_to_record')
    op.drop_table('record')
    op.drop_table('report')
    op.drop_table('location')
    op.drop_table('incident')
    # ### end Alembic commands ###
