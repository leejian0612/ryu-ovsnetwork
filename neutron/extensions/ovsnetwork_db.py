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
from neutron.db import portbindings_db
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
    vm_port_id = sa.Column(sa.String(36), sa.ForeignKey("ports.id"))
    vm_host = sa.Column(sa.String(255), nullable=True)
    ovs_port_id = sa.Column(sa.String(36), sa.ForeignKey("ports.id"))
    ovs_network_id = sa.Column(sa.String(36), sa.ForeignKey("ovsnetworks.id"))
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
            raise ext_ovsnetwork.OVSNetworkNotFound(id=id)
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
            context.session.delete(ovs_network)
            self._process_ovs_network_delete(context, id)

    def _make_vm_link_dict(self, vm_link, fields=None):
        res = {'id': vm_link['id'],
               'tenant_id': vm_link['tenant_id'],
               'name': vm_link['name'],
               'vm_host': vm_link['vm_host'],
               'vm_port_id': vm_link['vm_port_id'],
               'ovs_port_id': vm_link['ovs_port_id'],
               'ovs_network_id': vm_link['ovs_network_id'],
              }       
        return self._fields(res, fields)        


    def _get_vm_link(self, context, id):
        try:
            query = self._model_query(context, VMLink)
            vm_link = query.filter(VMLink.id == id).one()

        except exc.NoResultFound:
            return None
        return vm_link

    def _process_vm_link_create(self, context, ovs_network_id):
        p = {'port': {'network_id': ovs_network_id}}

        p['port']['device_owner'] = 'vm_link:ovs_port'
        ovs_port = db_base_plugin_v2.create_port(context, p)

        p['port']['device_owner'] = 'vm_link:vm_port'
        vm_port = db_base_plugin_v2.create_port(context, p)

        return vm_port['id'], ovs_port['id']
    
    def _process_vm_link_update(self, context, id, ovs_network_id):
        #here id is old ovs_port_id, first delete old ovs_port, and
        #then create a new ovs_port on new ovs_network!
        db_base_plugin_v2.delete_port(context, id=id)
        p = {'port': {'network_id': ovs_network_id}}
        p['port']['device_owner'] = 'vm_link:ovs_port'
        ovs_port = db_base_plugin_v2.create_port(context, p)
    
    def _process_vm_link_delete(self, context, ovs_port_id, vm_port_id):
        db_base_plugin_v2.delete_port(context, id=ovs_port_id)
        db_base_plugin_v2.delete_port(context, id=vm_port_id)
    
    def _get_ovs_network_id_by_name(self, context, name):
        try:
            query = self._model_query(context, OVSNetwork)
            ovs_network = query.filter(OVSNetwork.name == name).one()
        except exc.NoResultFound:
            raise ext_ovsnetwork.OVSNetworkNotFound(id=name)
        return ovs_network['id']

    def get_vm_link(self, context, id, fields=None):
        with context.session.begin(subtransactions=True):
            vm_link = self._get_vm_link(context, id)
            if vm_link != None:
                ret = self._make_vm_link_dict(vm_link, fields)            
                return ret 
            else:
                raise ext_ovsnetwork.VMLinkNotFound(id=id)                    

    def get_vm_links(self, context, filters=None, fields=None,
                     sorts=None, limit=None, marker=None,
                     page_reverse=False):
        marker_obj = self._get_marker_obj(context, 'vm_link',
                                          limit, marker)
        return self._get_collection(context,
                                    VMLink,
                                    self._make_vm_link_dict,
                                    filters=filters, fields=fields,
                                    sorts=sorts,
                                    limit=limit, marker_obj=marker_obj,
                                    page_reverse=page_reverse)

    def create_vm_link(self, context, vm_link):
        vm_link = vm_link['vm_link']
        tenant_id = self._get_tenant_id_for_create(context, vm_link)
        name = vm_link.get('name', None)
        vm_host = vm_link.get('vm_host')
        if not attr.is_attr_set('vm_host'):
            raise ext_ovsnetwork.HostNotSetInVMLink()
        ovs_network_name = vm_link.get('ovs_network_name')
        ovs_network_id = vm_link.get('ovs_network_id')
        if not attr.is_attr_set(ovs_network_id) 
            if attr.is_attr_set(ovs_network_name):
                ovs_network_id = self._get_ovs_network_id_by_name(context, ovs_network_name)       
            else:
                raise ext_ovsnetwork.OVSNetworkNotFound()  
        vm_port_id, ovs_port_id = self._process_vm_link_create(context, ovs_network_id)
        with context.session.begin(subtransactions=True):
            vm_link_db = VMLink(id = uuidutils.generate_uuid(),
                                tenant_id = tenant_id,
                                name = name,
                                vm_port_id = vm_port_id,
                                vm_host = vm_host,
                                ovs_port_id = ovs_port_id;
                                ovs_network_id = ovs_network_id)
            context.session.add(vm_link_db)
        return self._make_vm_link_dict(ovs_network_db)
    
    def update_vm_link(self, context, id, vm_link):
        vm_link = vm_link['vm_link']
        with context.session.begin(subtransactions=True):
            vm_link_db = self._get_vm_link(context, id)
            if not vm_link_db:
                return None
            old_ovs_id = vm_link_db['ovs_network_id']
            new_ovs_id = vm_link['ovs_network_id']
            if not new_ovs_id:
                new_ovs_id = self._get_ovs_network_id_by_name(context, vm_link['ovs_network_name'])
            if old_ovs_id != new_ovs_id:
                vm_link['ovs_port_id'] = self._process_vm_link_update(context, 
                                             vm_link_db['ovs_port_id'], vm_link['ovs_network_id'])
            else:
                vm_link['ovs_port_id'] = vm_link_db['ovs_port_id']
            vm_link['vm_link']['vm_port_id'] = vm_link_db['vm_port_id']
            vm_link_db.update(vm_link['vm_link'])
        return self._make_vm_link_dict(vm_link_db) 

    def delete_vm_link(self, context, id):
        vm_link = self._get_vm_link(context, id)

        with context.session.begin(subtransactions=True):
            self._process_vm_link_delete(context, id)
            context.session.delete(vm_link)

    #ovs_link operation
    def _make_ovs_link_dict(self, ovs_link, fields=None):
        res = {'id': ovs_link['id'],
               'tenant_id': ovs_link['tenant_id'],
               'name': ovs_link['name'],
               'left_port_id': ovs_link['left_port_id'],
               'left_ovs_id': ovs_link['left_ovs_id'],
               'right_port_id': ovs_link['right_port_id'],
               'right_ovs_id': ovs_link['right_ovs_id']
              }       
        return self._fields(res, fields)        

    def _get_ovs_link(self, context, id):
        try:
            query = self._model_query(context, OVSLink)
            ovs_link = query.filter(OVSLink.id == id).one()

        except exc.NoResultFound:
            return None
        return ovs_link
   
    def _get_ovs_link_endpoint_ids(self, context, ovs_link):
        left_ovs_name = ovs_link.get('left_ovs_name')
        left_ovs_id = ovs_link.get('left_ovs_id')
        if not attr.is_attr_set(left_ovs_id) 
            if attr.is_attr_set(left_ovs_name):
                left_ovs_id = self._get_ovs_network_id_by_name(context, left_ovs_name)       
            else:
                raise ext_ovsnetwork.OVSNetworkNotFound()  
        right_ovs_name = ovs_link.get('right_ovs_name')
        right_ovs_id = ovs_link.get('right_ovs_id')
        if not attr.is_attr_set(right_ovs_id) 
            if attr.is_attr_set(right_ovs_name):
                right_ovs_id = self._get_ovs_network_id_by_name(context, right_ovs_name)       
            else:
                raise ext_ovsnetwork.OVSNetworkNotFound()  
        return left_ovs_id, right_ovs_id

    def _process_ovs_link_create(self, context, left_ovs_id, right_ovs_id):
        p = {'port': {'network_id': left_ovs_id}}
        p['port']['device_owner'] = 'ovs_link:left_ovs_port'
        left_ovs_port = db_base_plugin_v2.create_port(context, p)

        p = {'port': {'network_id': right_ovs_id}}
        p['port']['device_owner'] = 'ovs_link:right_ovs_port'
        right_ovs_port = db_base_plugin_v2.create_port(context, p)

        return left_ovs_port['id'], right_ovs_port['id']
    
    def _process_ovs_link_delete(self, context, left_port_id, right_port_id):
        db_base_plugin_v2.delete_port(context, id=left_port_id)
        db_base_plugin_v2.delete_port(context, id=right_port_id)
    
    def get_ovs_link(self, context, id, fields=None):
        with context.session.begin(subtransactions=True):
            ovs_link = self._get_ovs_link(context, id)
            if vm_link != None:
                ret = self._make_ovs_link_dict(vm_link, fields)            
                return ret 
            else:
                raise ext_ovsnetwork.OVSLinkNotFound(id=id)                    

    def get_ovs_links(self, context, filters=None, fields=None,
                      sorts=None, limit=None, marker=None,
                      page_reverse=False):
        marker_obj = self._get_marker_obj(context, 'ovs_link',
                                          limit, marker)
        return self._get_collection(context,
                                    OVSLink,
                                    self._make_ovs_link_dict,
                                    filters=filters, fields=fields,
                                    sorts=sorts,
                                    limit=limit, marker_obj=marker_obj,
                                    page_reverse=page_reverse)

    def create_ovs_link(self, context, ovs_link):
        ovs_link = ovs_link['ovs_link']
        id = ovs_link.get('id') or uuidutils.generate_uuid()
        tenant_id = self._get_tenant_id_for_create(context, ovs_link)
        name = ovs_link.get('name', None)
        left_ovs_id, right_ovs_id = self._get_ovs_link_endpoint_ids(context, ovs_link)
        left_port_id, right_port_id = self._process_ovs_link_create(context, left_ovs_id, right_ovs_id)
        with context.session.begin(subtransactions=True):
            ovs_link_db = OVSLink(id = id,
                                  tenant_id = tenant_id,
                                  name = name,
                                  left_port_id = left_port_id,
                                  left_ovs_id = left_ovs_id,
                                  right_port_id = right_port_id,
                                  right_ovs_id = right_ovs_id)
            context.session.add(ovs_link_db)
        return self._make_ovs_link_dict(ovs_network_db)

    def update_ovs_link(self, context, id, ovs_link):
        self.delete_ovs_link(context, id)
        ovs_link['ovs_link']['id'] = id 
        self.create_ovs_link(context, ovs_link)
    
    def delete_ovs_link(self, context, id):
        ovs_link = self._get_ovs_link(context, id)

        with context.session.begin(subtransactions=True):
            self._process_ovs_link_delete(context, id)
            context.session.delete(ovs_link)
