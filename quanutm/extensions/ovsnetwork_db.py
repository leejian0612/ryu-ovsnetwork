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
# @author: Aaron Rosen, Nicira, Inc

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import exc
from sqlalchemy.orm import scoped_session

from quantum.api.v2 import attributes as attr
from quantum.db import db_base_plugin_v2
from quantum.db import model_base
from quantum.db import models_v2

import ovsnetwork as ext_ovsnetwork
from quantum.openstack.common import uuidutils

class OVSNetwork(model_base.BASEV2,models_v2.HasId,models_v2.HasTenant):
    id = sa.Column(sa.String(36),
                   sa.ForeignKey("networks.id",ondelete='CASCADE'),
                   primary_key=True)
    controller_ipv4_address = sa.Column(sa.String(36))
    controller_port_num = sa.Column(sa.Integer) 

class OVSNetworkDbMixin(ext_ovsnetwork.OVSNetworkPluginBase):
    """Mixin class to add ovs extension to db_plugin_base_v2."""
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
               'tunnel_key':ovsnetwork.get('tunnel_key',None)}       
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

