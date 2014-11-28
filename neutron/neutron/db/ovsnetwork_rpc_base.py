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

from neutron.common import constants as q_const
from neutron.common import utils
from neutron.db import ovsnetwork_db
from neutron.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class OVSNetworkServerRpcMixin(ovsnetwork_db.OVSNetworkDbMixin):
     
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
    

class OVSNetworkServerRpcCallbackMixin(object):
    # we should add some function to sync states of ovs_network, vm_link and ovs_link in future
    pass    
