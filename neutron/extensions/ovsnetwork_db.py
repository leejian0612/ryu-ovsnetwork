# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Nicira Networks, Inc.  All rights reserved.
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
# @author: Jian LI, BUPT

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import exc
from sqlalchemy import UniqueConstraint

from neutron.api.v2 import attributes as attr
from neutron.db import db_base_plugin_v2
from neutron.db import model_base
from neutron.db import models_v2

import ovsnetwork as ext_ovsnetwork
from neutron.openstack.common import uuidutils

class OVSNetwork(model_base.BASEV2, models_v2.HasTenant):
    id = sa.Column(sa.String(36),
                   sa.ForeignKey("networks.id", ondelete='CASCADE'),
                   primary_key=True)
    name = sa.Column(sa.String(255))
    host = sa.Column(sa.String(255), nullable=True)
    controller_ipv4_address = sa.Column(sa.String(36))
    controller_port_num = sa.Column(sa.Integer) 
    __table_args__ = (
        UniqueConstraint("name", "tenant_id"),
    )

class VMLink(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    name = sa.Column(sa.String(255))
    vm_port_id = sa.Column(sa.String(36),
                           sa.ForeignKey("ports.id", ondelete='CASCADE'))
    ovs_port_id = sa.Column(sa.String(36),
                            sa.ForeignKey("ports.id", ondelete='CASCADE'))
    ovs_network_id = sa.Column(sa.String(36),
                               sa.ForeignKey("ovsnetworks.id", ondelete='CASCADE'))
    ovs_network_name = sa.Column(sa.String(36),
                                 sa.ForeignKey("ovsnetworks.name", ondelete='CASCADE'))
    __table_args__ = (
        UniqueConstraint("name", "tenant_id"),
    )

class OVSLink(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    name = sa.Column(sa.String(255))
    left_port_id = sa.Column(sa.String(36),
                   sa.ForeignKey("ports.id", ondelete='CASCADE'))
    right_port_id = sa.Column(sa.String(36),
                    sa.ForeignKey("ports.id", ondelete='CASCADE'))
    left_ovs_id = sa.Column(sa.String(36), nullable=False,
                            sa.ForeignKey("ovsnetworks.id", ondelete='CASCADE')
    right_ovs_id = sa.Column(sa.String(36), nullable=False,
                             sa.ForeignKey("ovsnetworks.id", ondelete='CASCADE')
    left_ovs_name = sa.Column(sa.String(36),
                              sa.ForeignKey("ovsnetworks.name", ondelete='CASCADE'))
    right_ovs_name = sa.Column(sa.String(36),
                               sa.ForeignKey("ovsnetworks.name", ondelete='CASCADE'))
    __table_args__ = (
        UniqueConstraint("name", "tenant_id"),
    )


class OVSNetworkDbMixin(ext_ovsnetwork.OVSNetworkPluginBase):
    """Mixin class to add ovs network extension to db_plugin_base_v2."""

    def _make_ovs_network_dict(self, ovs_network, fields=None):
        res = {'id': ovs_network['id'],
               'tenant_id': ovs_network['tenant_id'],
               'name': ovs_network['name'],
               'controller_ipv4_address': ovs_network['controller_ipv4_address'],
               'controller_port_num': ovs_network.get('controller_port_num', None),
               #'tunnel_key':ovsnetwork.get('tunnel_key',None)
              }       
        return self._fields(res, fields)        


    def _get_ovsnetwork(self, context, id):
        try:
            query = self._model_query(context, OVSNetwork)
            ovs_network = query.filter(OVSNetwork.id == id).one()

        except exc.NoResultFound:
            return None
        return ovs_network

    def _process_ovs_network_create(self, context, ovs_network):
        
       network = models_v2.Network(id = ovs_network.get('id'),
                                   tenant_id = ovs_network.get('tenant_id'))
       with context.session.begin(subtransactions=True):
           context.session.add(network) 

    def _process_ovs_network_delete(self, context, id):

       try:
            query = self._model_query(context, models_v2.Network)
            network = query.filter(Network.id == id).one()

       except exc.NoResultFound:
           return
        
       with context.session.begin(subtransactions=True):
           context.session.delete(network) 
    
    def get_ovsnetwork(self, context, id, fields=None):
        with context.session.begin(subtransactions=True):
            ovs_network = self._get_ovsnetwork(context, id)
            if ovs_network != None:
                ret = self._make_ovs_network_dict(ovs_network, fields)            
                return ret 
            else:
                raise ext_ovsnetwork.OVSNetworkNotFound(id=id)                    

    def get_ovsnetworks(self, context, filters=None, fields=None,
                        sorts=None, limit=None, marker=None,
                        page_reverse=False):
        marker_obj = self._get_marker_obj(context, 'ovs_network',
                                          limit, marker)
        return self._get_collection(context,
                                    OVSNetwork,
                                    self._make_ovs_network_dict,
                                    filters=filters, fields=fields,
                                    sorts=sorts,
                                    limit=limit, marker_obj=marker_obj,
                                    page_reverse=page_reverse)

    def create_ovs_network(self, context, ovs_network):
        ovs_network = ovs_network['ovs_network']
        tenant_id = self._get_tenant_id_for_create(context, ovs_network)
        name = ovs_network.get('name', None)
        host = ovs_network.get('host', None)
        controller_ipv4_address = ovs_network.get('controller_ipv4_address', None)
        controller_port_num = ovs_network.get('controller_ipv4_port', None)
        with context.session.begin(subtransactions=True):
            ovs_network_db = OVSNetwork(id = uuidutils.generate_uuid(),
                                        tenant_id = tenant_id,
                                        name = name,
                                        host = host,
                                        controller_ipv4_address = controller_ipv4_address,
                                        controller_port_num = controller_port_num)
            context.session.add(ovs_network_db)
            #Add a new network record when creating an ovs_network.
            self._process_ovs_network_create(context, ovs_network)
        return self._make_ovs_network_dict(ovs_network_db)
    
    def update_ovsnetwork(self, context, id, ovs_network):
        with context.session.begin(subtransactions=True):
            ovs_network_db = self._get_ovsnetwork(context, id)
            if not ovs_network_db:
                return None
            ovs_network_db.update(ovs_network['ovsnetwork'])
        return self._make_ovs_network_dict(ovsnetwork_db) 

    def delete_ovs_network(self, context, id):
        filters = {'ovs_network_id': [id]}
        # this is not implemented
        vmlinks = self._get_vm_links(context, filters)
        ovslinks = self.get_ovs_links(context, filters)
        if vmlinks or ovslinks:
            raise ext_ovsnetwork.OVSNetworkHasLinks(id=id)
        ovs_network = self._get_ovs_network(context, id)

        with context.session.begin(subtransactions=True):
            context.session.delete(sg)
            self._process_ovs_network_delete(context, id)

