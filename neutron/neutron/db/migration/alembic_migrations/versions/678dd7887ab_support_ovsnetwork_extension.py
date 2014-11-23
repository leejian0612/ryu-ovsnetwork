# Copyright 2014 OpenStack Foundation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

"""Support ovsnetwork extension! 

Revision ID: 678dd7887ab
Revises: icehouse
Create Date: 2014-11-23 13:50:10.185289

"""

# revision identifiers, used by Alembic.
revision = '678dd7887ab'
down_revision = 'icehouse'

# Change to ['*'] if this migration applies to all plugins

migration_for_plugins = [
    'neutron.plugins.ml2.plugin.Ml2Plugin'
]

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from neutron.db import migration

### added by Jian LI to support ovsnetwork extension ###

def upgrade(active_plugins=None, options=None):
    if not migration.should_run(active_plugins, migration_for_plugins):
        return

    op.create_table('ovsnetworks',
    sa.Column('tenant_id', sa.String(length=255), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('host', sa.String(length=255), nullable=True),
    sa.Column('controller_ipv4_address', sa.String(length=36), nullable=True),
    sa.Column('controller_port_num', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    mysql_default_charset=u'utf8',
    mysql_engine=u'InnoDB'
    )

    op.create_table('vmlinks',
    sa.Column('tenant_id', sa.String(length=255), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('vm_port_id', sa.String(length=36), nullable=False),
    sa.Column('vm_host', sa.String(length=255), nullable=True),
    sa.Column('ovs_port_id', sa.String(length=36), nullable=False),
    sa.Column('ovs_network_id', sa.String(length=36), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    mysql_default_charset=u'utf8',
    mysql_engine=u'InnoDB'
    )

    op.create_table('ovslinks',
    sa.Column('tenant_id', sa.String(length=255), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('left_port_id', sa.String(length=36), nullable=False),
    sa.Column('right_port_id', sa.String(length=36), nullable=False),
    sa.Column('left_ovs_id', sa.String(length=36), nullable=False),
    sa.Column('right_ovs_id', sa.String(length=36), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    mysql_default_charset=u'utf8',
    mysql_engine=u'InnoDB'
    )


def downgrade(active_plugins=None, options=None):
    if not migration.should_run(active_plugins, migration_for_plugins):
        return

    op.drop_table('ovsnetworks')
    op.drop_table('vmlinks')
    op.drop_table('ovslinks')
