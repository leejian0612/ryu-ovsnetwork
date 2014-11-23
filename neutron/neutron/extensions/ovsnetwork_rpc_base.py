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
from neutron.db import models_v2
import ovsnetwork_db
from neutron.extensions import securitygroup as ext_sg
from neutron.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class OVSNetworkServerRpcMixin(ovsnetwork_db.OVSNetworkDbMixin):
     
    def update_ovsnetwork(self, context, id, ovsnetwork):
        ovs_network = super(OVSNetworkServerRpcMixin,self).update_ovsnetwork(context,id,ovsnetwork)
        if not ovs_network:
            return
        self.notifier.ovsnetwork_update(context, id, ovs_network)
        return ovs_network
    

class OVSNetworkServerRpcCallbackMixin(object):
    pass    
