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

class OVSNetwork(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    #id = sa.Column(sa.String(36),
                   #sa.ForeignKey("networks.id", ondelete='CASCADE'),
                   #primary_key=True)
    name = sa.Column(sa.String(255))
    host = sa.Column(sa.String(255), nullable=False)
    controller_ipv4_address = sa.Column(sa.String(36))
    controller_port_num = sa.Column(sa.Integer) 
    __table_args__ = (
        UniqueConstraint("name", "tenant_id"),
    )

class VMLink(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    name = sa.Column(sa.String(255))
    local_port_id = sa.Column(sa.String(36),
                    sa.ForeignKey("ports.id", ondelete='CASCADE'))
    remote_port_id = sa.Column(sa.String(36),
                     sa.ForeignKey("ports.id", ondelete='CASCADE'))
    local_host = sa.Column(sa.String(255), nullable=False)
    remote_host = sa.Column(sa.String(255), nullable=False)
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

    def create_ovs_network(self, context, ovs_network):
        ovs_network = ovs_network['ovs_network']
        tenant_id = self._get_tenant_id_for_create(context, ovs_network)
        with context.session.begin(subtransactions=True):
            ovs_network_db = OVSNetwork(id = uuidutils.generate_uuid(),
                                        tenant_id = tenant_id,
                                        name = ovs_network['name'],
                                        host = ovs_network['host'],
                                        controller_ipv4_address = ovs_network['controller_ipv4_address'],
                                        controller_ipv4_port = ovs_network['controller_ipv4_port'])

    def _get_ovsnetwork(self, context, id):
        try:
            query = self._model_query(context, OVSNetwork)
            ovs_network = query.filter(OVSNetwork.id == id).one()

        except exc.NoResultFound:
            return None
        return ovs_network
    
    def _make_ovs_network_dict(self, ovsnetwork, fields=None):
        res = {'id': ovsnetwork['id'],
               'tenant_id':ovsnetwork['tenant_id'],
               'controller_ipv4_address': ovsnetwork.get('controller_ipv4_address',None),
               'controller_port_num': ovsnetwork.get('controller_port_num',None),
               #'tunnel_key':ovsnetwork.get('tunnel_key',None)
              }       
        return self._fields(res, fields)        
              
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
        marker_obj = self._get_marker_obj(context, 'ovsnetwork',
                                          limit, marker)
        return self._get_collection(context,
                                    OVSNetwork,
                                    self._make_ovs_network_dict,
                                    filters=filters, fields=fields,
                                    sorts=sorts,
                                    limit=limit, marker_obj=marker_obj,
                                    page_reverse=page_reverse)
    
    def update_ovsnetwork(self, context, id, ovsnetwork):
        with context.session.begin(subtransactions=True):
            ovsnetwork_db = self._get_ovsnetwork(context, id)
            if not ovsnetwork_db:
                return None
            ovsnetwork_db.update(ovsnetwork['ovsnetwork'])
        return self._make_ovs_network_dict(ovsnetwork_db) 
                                      
    def _ensure_network_is_an_ovs(self, context, network):
        return network['network'].get('is_an_ovs')
    
    def _process_network_create_ovs(self, context, network):
        
       #print "network is: ",network
       #print "\nnetwork_id is",network.get('id',None)
       ovs_network = OVSNetwork(id = network.get('id'),
                                tenant_id = network.get('tenant_id'))
       with context.session.begin(subtransactions=True):
           context.session.add(ovs_network) 
    
            
'''    
    def _process_network_delete_ovs(self, context, id):
        query = self._model_query(context, OVSNetwork)
        ovs_network = query.filter(ovs_network.id == id)
        if ovs_network != None:
            with context.session.begin(subtransactions=True):
                context.session.delete(ovs_network)
'''    

