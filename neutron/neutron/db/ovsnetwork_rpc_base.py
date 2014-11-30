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


class OVSNetworkServerRpcMixin(ovsnetwork_db.OVSNetworkDbMixin):
    
    _tunnelkey = ovsnetwork_db.TunnelKeyDbMixin(
        cfg.CONF.OVSNETWORK.tunnel_key_min, cfg.CONF.OVSNETWORK.tunnel_key_max)

    @property
    def tunnelkey(self):
        return self._tunnelkey
     
    def create_ovs_network(self, context, ovs_network):
        ovs_network = super(OVSNetworkServerRpcMixin, self).create_ovs_network(context, ovs_network)
        if not ovs_network:
            return
        self.notifier.ovs_network_created(context, ovs_network)
        return ovs_network

    def update_ovs_network(self, context, id, ovs_network):
        ovs_network = super(OVSNetworkServerRpcMixin, self).update_ovs_network(context, id, ovs_network)
        if not ovs_network:
            return
        self.notifier.ovs_network_updated(context, id, ovs_network)
        return ovs_network

    def delete_ovs_network(self, context, id):
        host = super(OVSNetworkServerRpcMixin, self).delete_ovs_network(context, id)
        if host:
            self.notifier.ovs_network_deleted(context, id, host)
        return id
    
    def create_ovs_link(self, context, ovs_link):
        ovs_link = super(OVSNetworkServerRpcMixin, self).create_ovs_link(context, ovs_link)
        if not ovs_link:
            return
        ovs_link['left_tunnel_key'] = self.tunnelkey.allocate(context.session, ovs_link['left_port_id'])
        ovs_link['right_tunnel_key'] = self.tunnelkey.allocate(context.session, ovs_link['right_port_id'])

        left_host = self._get_ovs_network_host_by_id(context, ovs_link['left_ovs_id'])
        right_host = self._get_ovs_network_host_by_id(context, ovs_link['right_ovs_id'])

        self.notifier.ovs_link_left_endpoint_created(context, ovs_link, left_host)
        self.notifier.ovs_link_right_endpoint_created(context, ovs_link, right_host)
        return ovs_link
    
    def delete_ovs_link(self, context, id):
        ovs_link = super(OVSNetworkServerRpcMixin, self).delete_ovs_link(context, id)
        if not ovs_link:
            return
        ovs_link['left_tunnel_id'] = self.tunnelkey.get(context.session, ovs_link['left_port_id'])
        self.tunnelkey.delete(context.session, ovs_link['left_port_id'])
        ovs_link['right_tunnel_id'] = self.tunnelkey.get(context.session, ovs_link['right_port_id'])
        self.tunnelkey.delete(context.session, ovs_link['right_port_id'])

        left_host = self._get_ovs_network_host_by_id(context, ovs_link['left_ovs_id'])
        right_host = self._get_ovs_network_host_by_id(context, ovs_link['right_ovs_id'])

        self.notifier.ovs_link_left_endpoint_deleted(context, ovs_link, left_host)
        self.notifier.ovs_link_right_endpoint_deleted(context, ovs_link, right_host)
    
    def create_vm_link(self, context, vm_link):
        vm_link = super(OVSNetworkServerRpcMixin, self).create_vm_link(context, vm_link)
        if not vm_link:
            return
        vm_link['vm_tunnel_key'] = self.tunnelkey.allocate(context.session, vm_link['vm_port_id'])
        vm_link['ovs_tunnel_key'] = self.tunnelkey.allocate(context.session, vm_link['ovs_port_id'])

        ovs_host = self._get_ovs_network_host_by_id(context, vm_link['ovs_network_id'])
        self.notifier.vm_link_ovs_endpoint_created(context, vm_link, ovs_host)
        # This part should be done by nova, when creating an VM, according vm_link's information.
        #self.notifier.vm_link_vm_endpoint_created(context, vm_link, vm_link['vm_host'])
        return vm_link
   
    def update_vm_link(self, context, id, vm_link):
        old_vm_link = super(OVSNetworkServerRpcMixin, self).get_vm_link(context, id)
        new_vm_link = super(OVSNetworkServerRpcMixin, self).update_vm_link(context, id, vm_link)
        # Only when ovs endpoint changed, should we send notifications to the agent.
        new_ovs_id = vm_link.get('ovs_network_id')
        if new_ovs_id:
            new_host = self._get_ovs_network_host_by_id(context, new_ovs_id)
            old_host = self._get_ovs_network_host_by_id(context, old_vm_link['ovs_network_id'])
            self.tunnelkey.delete(context.session, old_vm_link['ovs_port_id'])
            new_vm_link['ovs_tunnel_key'] = self.tunnelkey.allocate(context.session, new_vm_link['ovs_port_id'])
            new_vm_link['vm_tunnel_key'] = self.tunnelkey.get(context.session, new_vm_link['vm_port_id'])
            old_vm_link['ovs_tunnel_key'] = self.tunnelkey.get(context.session, old_vm_link['ovs_port_id'])
            old_vm_link['vm_tunnel_key'] = new_vm_link['vm_tunnel_key']

            # Delete old ovs endpoint of this vm link, and create the new one, then update the vm endpoint's flow table.
            self.notifier.vm_link_ovs_endpoint_created(context, new_vm_link, new_host)
            self.notifier.vm_link_ovs_endpoint_deleted(context, old_vm_link, old_host)
            self.notifier.vm_link_vm_endpoint_updated(context, new_vm_link, new_vm_link['vm_host'])
        return new_vm_link
   
    def delete_vm_link(self, context, id):
        old_vm_link = super(OVSNetworkServerRpcMixin, self).delete_vm_link(context, id)
        old_vm_link['ovs_tunnel_key'] = self.tunnelkey.get(context.session, old_vm_link['ovs_port_id'])
        self.tunnelkey.delete(context.session, old_vm_link['ovs_port_id'])
        old_vm_link['vm_tunnel_key'] = self.tunnelkey.get(context.session, old_vm_link['vm_port_id'])
        self.tunnelkey.delete(context.session, old_vm_link['vm_port_id'])
        old_host = self._get_ovs_network_host_by_id(context, old_vm_link['ovs_network_id'])
        self.notifier.vm_link_ovs_endpoint_deleted(context, old_vm_link, old_host)
        #self.notifier.vm_link_vm_endpoint_deleted(context, old_vm_link, old_vm_link['vm_host'])
    

class OVSNetworkServerRpcCallbackMixin(object):
    # we should add some function to sync states of ovs_network, vm_link and ovs_link in future
    pass    
