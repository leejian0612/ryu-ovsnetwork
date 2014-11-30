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
# Tunnelkey is copied from ryu plugin in icehouse release

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import exc
from sqlalchemy import UniqueConstraint

from sqlalchemy import func
from sqlalchemy import exc as sa_exc

from neutron.api.v2 import attributes as attr
from neutron.db import db_base_plugin_v2
from neutron.db import portbindings_db
from neutron.db import model_base
from neutron.db import models_v2

from neutron.extensions import ovsnetwork as ext_ovsnetwork
from neutron.openstack.common import uuidutils
from neutron.openstack.common import log as logging
from neutron.common import exceptions as n_exc
from oslo.config import cfg




LOG = logging.getLogger(__name__)


class TunnelKeyLast(model_base.BASEV2):
    """Last allocated Tunnel key.

    The next key allocation will be started from this value + 1
    """
    last_key = sa.Column(sa.Integer, primary_key=True)

    def __repr__(self):
        return "<TunnelKeyLast(%x)>" % self.last_key


class TunnelKey(model_base.BASEV2):
    """Port ID <-> tunnel key mapping."""
    port_id = sa.Column(sa.String(36), sa.ForeignKey("ports.id"),
                        nullable=False)
    tunnel_key = sa.Column(sa.Integer, primary_key=True,
                           nullable=False, autoincrement=False)

    def __repr__(self):
        return "<TunnelKey(%s,%x)>" % (self.port_id, self.tunnel_key)


class OVSNetwork(model_base.BASEV2, models_v2.HasTenant):
    id = sa.Column(sa.String(36), 
                   sa.ForeignKey("networks.id",ondelete='CASCADE'),
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
    left_ovs_id = sa.Column(sa.String(36),
                            sa.ForeignKey('ovsnetworks.id', ondelete='CASCADE'))
    right_ovs_id = sa.Column(sa.String(36),
                            sa.ForeignKey('ovsnetworks.id', ondelete='CASCADE'))
    __table_args__ = (
        UniqueConstraint("name", "tenant_id"),
    )


class TunnelKeyDbMixin(object):
    # VLAN: 12 bits
    # GRE, VXLAN: 24bits
    # TODO(yamahata): STT: 64bits
    _KEY_MIN_HARD = 1
    _KEY_MAX_HARD = 0xffffffff

    def __init__(self, key_min=_KEY_MIN_HARD, key_max=_KEY_MAX_HARD):
        self.key_min = key_min
        self.key_max = key_max

        if (key_min < self._KEY_MIN_HARD or key_max > self._KEY_MAX_HARD or
                key_min > key_max):
            raise ValueError(_('Invalid tunnel key options '
                               'tunnel_key_min: %(key_min)d '
                               'tunnel_key_max: %(key_max)d. '
                               'Using default value') % {'key_min': key_min,
                                                         'key_max': key_max})

    def _last_key(self, session):
        try:
            return session.query(TunnelKeyLast).one()
        except exc.MultipleResultsFound:
            max_key = session.query(
                func.max(TunnelKeyLast.last_key))
            if max_key > self.key_max:
                max_key = self.key_min

            session.query(TunnelKeyLast).delete()
            last_key = TunnelKeyLast(last_key=max_key)
        except exc.NoResultFound:
            last_key = TunnelKeyLast(last_key=self.key_min)

        session.add(last_key)
        session.flush()
        return session.query(TunnelKeyLast).one()

    def _find_key(self, session, last_key):
        """Try to find unused tunnel key.
        Trying to find unused tunnel key in TunnelKey table starting
        from last_key + 1.
        When all keys are used, raise sqlalchemy.orm.exc.NoResultFound
        """
        # key 0 is used for special meanings. So don't allocate 0.

        # sqlite doesn't support
        # '(select order by limit) union all (select order by limit) '
        # 'order by limit'
        # So do it manually
        # new_key = session.query("new_key").from_statement(
        #     # If last_key + 1 isn't used, it's the result
        #     'SELECT new_key '
        #     'FROM (SELECT :last_key + 1 AS new_key) q1 '
        #     'WHERE NOT EXISTS '
        #     '(SELECT 1 FROM tunnelkeys WHERE tunnel_key = :last_key + 1) '
        #
        #     'UNION ALL '
        #
        #     # if last_key + 1 used,
        #     # find the least unused key from last_key + 1
        #     '(SELECT t.tunnel_key + 1 AS new_key '
        #     'FROM tunnelkeys t '
        #     'WHERE NOT EXISTS '
        #     '(SELECT 1 FROM tunnelkeys ti '
        #     ' WHERE ti.tunnel_key = t.tunnel_key + 1) '
        #     'AND t.tunnel_key >= :last_key '
        #     'ORDER BY new_key LIMIT 1) '
        #
        #     'ORDER BY new_key LIMIT 1'
        # ).params(last_key=last_key).one()
        try:
            new_key = session.query("new_key").from_statement(
                # If last_key + 1 isn't used, it's the result
                'SELECT new_key '
                'FROM (SELECT :last_key + 1 AS new_key) q1 '
                'WHERE NOT EXISTS '
                '(SELECT 1 FROM tunnelkeys WHERE tunnel_key = :last_key + 1) '
            ).params(last_key=last_key).one()
        except exc.NoResultFound:
            new_key = session.query("new_key").from_statement(
                # if last_key + 1 used,
                # find the least unused key from last_key + 1
                '(SELECT t.tunnel_key + 1 AS new_key '
                'FROM tunnelkeys t '
                'WHERE NOT EXISTS '
                '(SELECT 1 FROM tunnelkeys ti '
                ' WHERE ti.tunnel_key = t.tunnel_key + 1) '
                'AND t.tunnel_key >= :last_key '
                'ORDER BY new_key LIMIT 1) '
            ).params(last_key=last_key).one()

        new_key = new_key[0]  # the result is tuple.
        LOG.debug(_("last_key %(last_key)s new_key %(new_key)s"),
                  {'last_key': last_key, 'new_key': new_key})
        if new_key > self.key_max:
            LOG.debug(_("No key found"))
            raise exc.NoResultFound()
        return new_key

    def _allocate(self, session, port_id):
        last_key = self._last_key(session)
        try:
            new_key = self._find_key(session, last_key.last_key)
        except exc.NoResultFound:
            new_key = self._find_key(session, self.key_min)

        tunnel_key = TunnelKey(port_id=port_id,
                               tunnel_key=new_key)
        last_key.last_key = new_key
        session.add(tunnel_key)
        return new_key

    _TRANSACTION_RETRY_MAX = 16

    def allocate(self, session, port_id):
        count = 0
        while True:
            session.begin(subtransactions=True)
            try:
                new_key = self._allocate(session, port_id)
                session.commit()
                break
            except sa_exc.SQLAlchemyError:
                session.rollback()

            count += 1
            if count > self._TRANSACTION_RETRY_MAX:
                # if this happens too often, increase _TRANSACTION_RETRY_MAX
                LOG.warn(_("Transaction retry exhausted (%d). "
                           "Abandoned tunnel key allocation."), count)
                raise n_exc.ResourceExhausted()

        return new_key

    def delete(self, session, port_id):
        session.query(TunnelKey).filter_by(
            port_id=port_id).delete()
        session.flush()

    def get(self, session, port_id):
        return session.query(TunnelKey).filter_by(
            port_id=port_id).one().tunnel_key


class OVSNetworkDbMixin(ext_ovsnetwork.OVSNetworkPluginBase):
    """Mixin class to add ovs network extension to db_plugin_base_v2."""


    def _make_ovs_network_dict(self, ovs_network, fields=None):
        res = {'id': ovs_network['id'],
               'tenant_id': ovs_network['tenant_id'],
               'name': ovs_network['name'],
               'host': ovs_network['host'],
               'controller_ipv4_address': ovs_network['controller_ipv4_address'],
               'controller_port_num': ovs_network.get('controller_port_num', None),
               #'tunnel_key':ovsnetwork.get('tunnel_key',None)
              }       
        return self._fields(res, fields)        


    def _get_ovs_network(self, context, id):
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
           query = context.session.query(models_v2.Network)
           network = query.filter(models_v2.Network.id == id).one()
       except exc.NoResultFound:
           return
       with context.session.begin(subtransactions=True):
           context.session.delete(network) 
    
    def get_ovs_network(self, context, id, fields=None):
        with context.session.begin(subtransactions=True):
            ovs_network = self._get_ovs_network(context, id)
            if ovs_network != None:
                ret = self._make_ovs_network_dict(ovs_network, fields)            
                return ret 

    def get_ovs_networks(self, context, filters=None, fields=None,
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
        controller_port_num = ovs_network.get('controller_port_num', None)
        with context.session.begin(subtransactions=True):
            id = uuidutils.generate_uuid()
            ovs_network.update({'id': id})
            #Add a new network record before creating an ovs_network.
            self._process_ovs_network_create(context, ovs_network)
            ovs_network_db = OVSNetwork(id = id,
                                        tenant_id = tenant_id,
                                        name = name,
                                        host = host,
                                        controller_ipv4_address = controller_ipv4_address,
                                        controller_port_num = controller_port_num)
            context.session.add(ovs_network_db)
        return self._make_ovs_network_dict(ovs_network_db)
    
    def update_ovs_network(self, context, id, ovs_network):
        with context.session.begin(subtransactions=True):
            ovs_network_db = self._get_ovs_network(context, id)
            if not ovs_network_db:
                return None
            ovs_network_db.update(ovs_network['ovs_network'])
        return self._make_ovs_network_dict(ovs_network_db) 

    def delete_ovs_network(self, context, id):
        filters = {'ovs_network_id': [id]}
        # this is not implemented
        vmlinks = self.get_vm_links(context, filters)
        ovslinks = self.get_ovs_links(context, filters)
        if vmlinks or ovslinks:
            raise ext_ovsnetwork.OVSNetworkHasLinks(id=id)
        ovs_network = self._get_ovs_network(context, id)
        host = ovs_network['host']

        with context.session.begin(subtransactions=True):
            self._process_ovs_network_delete(context, id)
            context.session.delete(ovs_network)
        return host

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
    
    def _process_vm_link_create(self, context, tenant_id, ovs_network_id):
        with context.session.begin(subtransactions=True):
            vm_port_id = uuidutils.generate_uuid()
            ovs_port_id = uuidutils.generate_uuid()
            for port_id in [vm_port_id, ovs_port_id]:
                if port_id == vm_port_id:
                   device_owner = 'vm_link:vm_port'
                else:
                   device_owner = 'vm_link:ovs_port'

                port = models_v2.Port(tenant_id=tenant_id,
                    name='',
                    id=port_id,
                    network_id=ovs_network_id,
                    mac_address=db_base_plugin_v2.NeutronDbPluginV2._generate_mac(context, ovs_network_id),
                    admin_state_up=True,
                    status='ACTIVE',
                    device_id='',
                    device_owner=device_owner)
                context.session.add(port)
            return vm_port_id, ovs_port_id

    def _process_vm_link_update(self, context, old_port_id, new_ovs_id):
       with context.session.begin(subtransactions=True):
           try:
               query = context.session.query(models_v2.Port)
               port = query.filter(models_v2.Port.id == old_port_id).one()
           except exc.NoResultFound:
               LOG.debug(_("can not find port %s"), id)
               return
           context.session.delete(port) 
           port_id = uuidutils.generate_uuid()
           device_owner = 'vm_link:ovs_port'
           port = models_v2.Port(tenant_id=tenant_id,
                name='',
                id=port_id,
                network_id=new_ovs_id,
                mac_address=db_base_plugin_v2.NeutronDbPluginV2._generate_mac(context, new_ovs_id),
                admin_state_up=True,
                status='ACTIVE',
                device_id='',
                device_owner=device_owner)
           context.session.add(port)
           return port_id
    
    def _process_vm_link_delete(self, context, vm_port_id, ovs_port_id):
       with context.session.begin(subtransactions=True):
           for id in [vm_port_id, ovs_port_id]:
               try:
                   query = context.session.query(models_v2.Port)
                   port = query.filter(models_v2.Port.id == id).one()
               except exc.NoResultFound:
                   LOG.debug(_("can not find port %s"), id)
                   return
               context.session.delete(port) 
    
    def _get_ovs_network_id_by_name(self, context, name):
        try:
            query = self._model_query(context, OVSNetwork)
            ovs_network = query.filter(OVSNetwork.name == name).one()
        except exc.NoResultFound:
            raise ext_ovsnetwork.OVSNetworkNotFound(id=name)
        return ovs_network['id']

    def _get_ovs_network_host_by_id(self, context, id):
        try:
            query = self._model_query(context, OVSNetwork)
            ovs_network = query.filter(OVSNetwork.id == id).one()
        except exc.NoResultFound:
            raise ext_ovsnetwork.OVSNetworkNotFound(id=id)
        return ovs_network['host']

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
        if not attr.is_attr_set(ovs_network_id):
            if attr.is_attr_set(ovs_network_name):
                ovs_network_id = self._get_ovs_network_id_by_name(context, ovs_network_name)       
            else:
                raise ext_ovsnetwork.OVSNetworkNotFound()  
        with context.session.begin(subtransactions=True):
            vm_port_id, ovs_port_id = self._process_vm_link_create(context, tenant_id, ovs_network_id)
            vm_link_db = VMLink(id = uuidutils.generate_uuid(),
                                tenant_id = tenant_id,
                                name = name,
                                vm_port_id = vm_port_id,
                                vm_host = vm_host,
                                ovs_port_id = ovs_port_id,
                                ovs_network_id = ovs_network_id)
            context.session.add(vm_link_db)
        return self._make_vm_link_dict(vm_link_db)
    
    def update_vm_link(self, context, id, vm_link):
        vm_link = vm_link['vm_link']
        with context.session.begin(subtransactions=True):
            vm_link_db = self._get_vm_link(context, id)
            if not vm_link_db:
                return None
            old_ovs_id = vm_link_db['ovs_network_id']
            new_ovs_id = vm_link.get('ovs_network_id')
            ovs_network_name = vm_link.get('ovs_network_name')
            if not new_ovs_id and ovs_network_name:
                new_ovs_id = self._get_ovs_network_id_by_name(context, vm_link['ovs_network_name'])
                if old_ovs_id != new_ovs_id:
                    vm_link['ovs_port_id'] = self._process_vm_link_update(context, 
                                                 vm_link_db['ovs_port_id'], vm_link['ovs_network_id'])
            vm_link_db.update(vm_link)
        return self._make_vm_link_dict(vm_link_db) 

    def delete_vm_link(self, context, id):
        vm_link = self._get_vm_link(context, id)

        with context.session.begin(subtransactions=True):
            self._process_vm_link_delete(context, vm_link['vm_port_id'], vm_link['ovs_port_id'])
            context.session.delete(vm_link)
        return self._make_vm_link_dict(vm_link)

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
        if not attr.is_attr_set(left_ovs_id): 
            if attr.is_attr_set(left_ovs_name):
                left_ovs_id = self._get_ovs_network_id_by_name(context, left_ovs_name)       
            else:
                raise ext_ovsnetwork.OVSNetworkNotFound()  
        right_ovs_name = ovs_link.get('right_ovs_name')
        right_ovs_id = ovs_link.get('right_ovs_id')
        if not attr.is_attr_set(right_ovs_id): 
            if attr.is_attr_set(right_ovs_name):
                right_ovs_id = self._get_ovs_network_id_by_name(context, right_ovs_name)       
            else:
                raise ext_ovsnetwork.OVSNetworkNotFound()  
        return left_ovs_id, right_ovs_id

    def _process_ovs_link_create(self, context, left_ovs_id, right_ovs_id, tenant_id):
        port_ids = []
        with context.session.begin(subtransactions=True):
            for ovs_network_id in [left_ovs_id, right_ovs_id]:
                port_id=uuidutils.generate_uuid() 
                port = models_v2.Port(tenant_id=tenant_id,
                                  name='',
                                  id=port_id,
                                  network_id=ovs_network_id,
                                  mac_address=db_base_plugin_v2.NeutronDbPluginV2._generate_mac(context, ovs_network_id),
                                  admin_state_up=True,
                                  status='ACTIVE',
                                  device_id='',
                                  device_owner='ovs_link:ovs_port')
                LOG.debug(_("lijian port_id is %s\n %s\n %s\n"), port_id, type(port_id), dir(port_id))
                context.session.add(port)
                #p = {'port': {'network_id': ovs_network_id}}
                #p['port']['device_owner'] = 'ovs_link:ovs_port'
                #p['port']['mac_address'] = object()
                #port = db_base_plugin_v2.NeutronDbPluginV2.create_port(self, context, p)
                port_ids.append(port['id'])
        return port_ids[0],port_ids[1]
    
    def _process_ovs_link_delete(self, context, left_port_id, right_port_id):
       with context.session.begin(subtransactions=True):
           for id in [left_port_id, right_port_id]:
               try:
                   query = context.session.query(models_v2.Port)
                   port = query.filter(models_v2.Port.id == id).one()
               except exc.NoResultFound:
                   LOG.debug(_("can not find port %s"), id)
                   return
               context.session.delete(port) 
    
    def get_ovs_link(self, context, id, fields=None):
        with context.session.begin(subtransactions=True):
            ovs_link = self._get_ovs_link(context, id)
            if ovs_link != None:
                ret = self._make_ovs_link_dict(ovs_link, fields)            
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
        with context.session.begin(subtransactions=True):
            left_port_id, right_port_id = self._process_ovs_link_create(context, left_ovs_id, right_ovs_id, tenant_id)
            ovs_link_db = OVSLink(id = id,
                                  tenant_id = tenant_id,
                                  name = name,
                                  left_port_id = left_port_id,
                                  left_ovs_id = left_ovs_id,
                                  right_port_id = right_port_id,
                                  right_ovs_id = right_ovs_id)
            context.session.add(ovs_link_db)
        return self._make_ovs_link_dict(ovs_link_db)

    #def update_ovs_link(self, context, id, ovs_link):
    #    # should we support ovs link update? This should be considered in future! lijian
    #    self.delete_ovs_link(context, id)
    #    ovs_link['ovs_link']['id'] = id 
    #    self.create_ovs_link(context, ovs_link)
    
    def delete_ovs_link(self, context, id):
        ovs_link = self._get_ovs_link(context, id)

        with context.session.begin(subtransactions=True):
            self._process_ovs_link_delete(context, ovs_link['left_port_id'], ovs_link['right_port_id'])
            context.session.delete(ovs_link)
        return self._make_ovs_link_dict(ovs_link)
