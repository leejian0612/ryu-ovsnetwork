# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2012, Nachi Ueno, NTT MCL, Inc.
# All Rights Reserved.
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

import netaddr
from oslo.config import cfg
from neutron.common import constants as q_const
from neutron.common import utils
from neutron.db import ovsnetwork_db
from neutron.openstack.common import log as logging
from neutron.api.v2 import attributes

LOG = logging.getLogger(__name__)

ovs_network_opts = [
    cfg.IntOpt(
        'tunnel_key_min',
        default=1,
        help=_('Min tunnek key for ovs network isolation stategy.')),
    cfg.IntOpt(
        'tunnel_key_max',
        default=0xffffffff,
        help=_('Max tunnek key for ovs network isolation stategy.')),
]
cfg.CONF.register_opts(ovs_network_opts, 'OVSNETWORK')
link_port={'port':{
    'mac_address':attributes.ATTR_NOT_SPECIFIED,
    'admin_state_up':True,
    'fixed_ips':attributes.ATTR_NOT_SPECIFIED,
    'device_id':'',
    'device_owner':'',
}}


class OVSNetworkServerRpcMixin(ovsnetwork_db.OVSNetworkDbMixin):
    
    _tunnelkey = ovsnetwork_db.TunnelKeyDbMixin(
        cfg.CONF.OVSNETWORK.tunnel_key_min, cfg.CONF.OVSNETWORK.tunnel_key_max)

    @property
    def tunnelkey(self):
        return self._tunnelkey
     
    def create_ovs_network(self, context, ovs_network):
        id = None
        with context.session.begin(subtransactions=True):
            network={}
            network['network']={
                'name':'shadow-ovs-network',
                'admin_state_up':True,
                'shared':False,
                'status':'ACTIVE',
            }
            network = self.create_network(context, network)
            id = network.get('id')
            subnet={}
            subnet['subnet']={
                'cidr':'111.111.0.0/16',
                'gateway_ip':'111.111.0.1',
                'allocation_pools':attributes.ATTR_NOT_SPECIFIED,
                'ip_version':4,
                'dns_nameservers':attributes.ATTR_NOT_SPECIFIED,
                'host_routes':attributes.ATTR_NOT_SPECIFIED,
                'enable_dhcp':False,
                'name':'shadow-ovs-subnet',
                'network_id':id
            }
            subnet = self.create_subnet(context, subnet)
            id = subnet.get('network_id')
            ovs_network['ovs_network'].update({'id': id})
            ovs_network = super(OVSNetworkServerRpcMixin, self).create_ovs_network(context, ovs_network)

        if not id:
            return
        self.notifier.ovs_network_created(context, ovs_network)
        return ovs_network

    def update_ovs_network(self, context, id, ovs_network):
        ovs_network = super(OVSNetworkServerRpcMixin, self).update_ovs_network(context, id, ovs_network)
        if not ovs_network:
            return
        self.notifier.ovs_network_updated(context, ovs_network)
        return ovs_network

    def delete_ovs_network(self, context, id):
        host = None
        with context.session.begin(subtransactions=True):
            host = super(OVSNetworkServerRpcMixin, self).delete_ovs_network(context, id)
            filters = {'network_id': [id]}
            subnets = self.get_subnets(context, filters)
            for subnet in subnets:
                self.delete_subnet(context, subnet['id'])
            self.delete_network(context, id)

        if not host:
            return
        self.notifier.ovs_network_deleted(context, id, host)
        return id
    
    def create_ovs_link(self, context, ovs_link):
        with context.session.begin(subtransactions=True):
            left_port = link_port
            left_port['port'].update({'name':'left-ovs-port',
                                      'network_id':ovs_link['ovs_link']['left_ovs_id']})
            left_port = self.create_port(context, left_port)
            right_port = link_port
            right_port['port'].update({'name':'right-ovs-port',
                                      'network_id':ovs_link['ovs_link']['right_ovs_id']})
            right_port = self.create_port(context, right_port)
            ovs_link['ovs_link'].update({'left_port_id':left_port['id'],
                                         'right_port_id':right_port['id']})
            ovs_link = super(OVSNetworkServerRpcMixin, self).create_ovs_link(context, ovs_link)

            ovs_link['left_tunnel_id'] = self.tunnelkey.allocate(context.session, ovs_link['left_port_id'])
            ovs_link['right_tunnel_id'] = self.tunnelkey.allocate(context.session, ovs_link['right_port_id'])
            left_host = self._get_ovs_network_host_by_id(context, ovs_link['left_ovs_id'])
            right_host = self._get_ovs_network_host_by_id(context, ovs_link['right_ovs_id'])
        
        if not ovs_link.get('id'):
            return
        self.notifier.ovs_link_left_endpoint_created(context, ovs_link, left_host)
        self.notifier.ovs_link_right_endpoint_created(context, ovs_link, right_host)
        return ovs_link
    
    def delete_ovs_link(self, context, id):
        ovs_link = None
        with context.session.begin(subtransactions=True):
            ovs_link = super(OVSNetworkServerRpcMixin, self).delete_ovs_link(context, id)
            self.delete_port(context, ovs_link['left_port_id'])
            self.delete_port(context, ovs_link['right_port_id'])

            ovs_link['left_tunnel_id'] = self.tunnelkey.get(context.session, ovs_link['left_port_id'])
            self.tunnelkey.delete(context.session, ovs_link['left_port_id'])
            ovs_link['right_tunnel_id'] = self.tunnelkey.get(context.session, ovs_link['right_port_id'])
            self.tunnelkey.delete(context.session, ovs_link['right_port_id'])

            left_host = self._get_ovs_network_host_by_id(context, ovs_link['left_ovs_id'])
            right_host = self._get_ovs_network_host_by_id(context, ovs_link['right_ovs_id'])

        if not ovs_link.get('id'):
            return
        self.notifier.ovs_link_left_endpoint_deleted(context, ovs_link, left_host)
        self.notifier.ovs_link_right_endpoint_deleted(context, ovs_link, right_host)
    
    def create_vm_link(self, context, vm_link):
        with context.session.begin(subtransactions=True):
            vm_port = link_port
            vm_port['port'].update({'name':'vm_port',
                                    'network_id':vm_link['vm_link']['ovs_network_id']})
            vm_port = self.create_port(context, vm_port)
            ovs_port = link_port
            ovs_port['port'].update({'name':'ovs_port',
                                     'network_id':vm_link['vm_link']['ovs_network_id']})
            ovs_port = self.create_port(context, ovs_port)
            vm_link['vm_link'].update({'vm_port_id':vm_port['id'],
                                       'ovs_port_id':ovs_port['id']})
            vm_link = super(OVSNetworkServerRpcMixin, self).create_vm_link(context, vm_link)

            vm_link['vm_tunnel_id'] = self.tunnelkey.allocate(context.session, vm_link['vm_port_id'])
            vm_link['ovs_tunnel_id'] = self.tunnelkey.allocate(context.session, vm_link['ovs_port_id'])
            ovs_host = self._get_ovs_network_host_by_id(context, vm_link['ovs_network_id'])

        if not vm_link.get('id'):
            return
        self.notifier.vm_link_ovs_endpoint_created(context, vm_link, ovs_host)
        #self.notifier.vm_link_vm_endpoint_created(context, vm_link, vm_link['vm_host'])
        return vm_link
   
    def update_vm_link(self, context, id, vm_link):
        new_ovs_id = None
        with context.session.begin(subtransactions=True):
            new_ovs_id = vm_link['vm_link'].get('ovs_network_id')
            new_status = vm_link['vm_link'].get('status')
	    old_vm_link = super(OVSNetworkServerRpcMixin, self).get_vm_link(context, id)
            old_ovs_id = old_vm_link['ovs_network_id']
            old_status = old_vm_link['status']
            if new_ovs_id and new_ovs_id != old_ovs_id:
                self.delete_port(context, old_vm_link['ovs_port_id'])
                ovs_port = link_port
                ovs_port['port'].update({'name':'ovs_port',
                                         'network_id':new_ovs_id})
                ovs_port = self.create_port(context, ovs_port)
                vm_link['vm_link'].update({'ovs_port_id':ovs_port['id']})
                new_vm_link = super(OVSNetworkServerRpcMixin, self).update_vm_link(context, id, vm_link)
                # when ovs endpoint changed, we should send notifications to the agent.
                new_host = self._get_ovs_network_host_by_id(context, new_ovs_id)
                old_host = self._get_ovs_network_host_by_id(context, old_vm_link['ovs_network_id'])
                new_vm_link['ovs_tunnel_id'] = self.tunnelkey.allocate(context.session, new_vm_link['ovs_port_id'])
                new_vm_link['vm_tunnel_id'] = self.tunnelkey.get(context.session, new_vm_link['vm_port_id'])
                old_vm_link['ovs_tunnel_id'] = self.tunnelkey.get(context.session, old_vm_link['ovs_port_id'])
                self.tunnelkey.delete(context.session, old_vm_link['ovs_port_id'])
            else:
                new_vm_link = super(OVSNetworkServerRpcMixin, self).update_vm_link(context, id, vm_link)
                new_vm_link['ovs_tunnel_id'] = self.tunnelkey.get(context.session, new_vm_link['ovs_port_id'])
                new_vm_link['vm_tunnel_id'] = self.tunnelkey.get(context.session, new_vm_link['vm_port_id'])

        if new_ovs_id  and new_ovs_id != old_ovs_id:
            # Delete old ovs endpoint of this vm link, and create the new one, then update the vm endpoint's flow table.
            self.notifier.vm_link_ovs_endpoint_created(context, new_vm_link, new_host)
            self.notifier.vm_link_ovs_endpoint_deleted(context, old_vm_link, old_host)
        if new_status == 'ACTIVE':
            if old_status == 'PENDING':
                self.notifier.vm_link_vm_endpoint_created(context, new_vm_link, new_vm_link['vm_host'])
            elif old_status == 'ACTIVE':
                new_vm_link['old_ovs_tunnel_id'] = old_vm_link['ovs_tunnel_id']
                self.notifier.vm_link_vm_endpoint_updated(context, new_vm_link, new_vm_link['vm_host'])
        return new_vm_link
   
    def delete_vm_link(self, context, id):
        vm_link = super(OVSNetworkServerRpcMixin, self).delete_vm_link(context, id)
        self.delete_port(context, vm_link['vm_port_id'])
        self.delete_port(context, vm_link['ovs_port_id'])
        ovs_host = None
        with context.session.begin(subtransactions=True):
            vm_link['ovs_tunnel_id'] = self.tunnelkey.get(context.session, vm_link['ovs_port_id'])
            self.tunnelkey.delete(context.session, vm_link['ovs_port_id'])
            vm_link['vm_tunnel_id'] = self.tunnelkey.get(context.session, vm_link['vm_port_id'])
            self.tunnelkey.delete(context.session, vm_link['vm_port_id'])
            ovs_host = self._get_ovs_network_host_by_id(context, vm_link['ovs_network_id'])
        if ovs_host:
            self.notifier.vm_link_ovs_endpoint_deleted(context, vm_link, ovs_host)
        status=vm_link.get('status')
        if status == 'ACTIVE':
            self.notifier.vm_link_vm_endpoint_deleted(context, vm_link, vm_link['vm_host'])
    

class OVSNetworkServerRpcCallbackMixin(object):
    # we should add some function to sync states of ovs_network, vm_link and ovs_link in future
    pass    
