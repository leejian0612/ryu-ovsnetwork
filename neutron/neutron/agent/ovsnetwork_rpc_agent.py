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
#
# This is created by Jian LI @ BUPT

from oslo.config import cfg

from neutron.common import topics
from neutron.openstack.common import importutils
from neutron.openstack.common import log as logging
from neutron import manager

#from neutron.agent.linux import ovs_lib

LOG = logging.getLogger(__name__)

ovs_network_opts = [
    cfg.StrOpt(
        'ovs_network_driver',
        default=None,
        help=_('Driver for ovs network implementation on L2 agent')),
]
cfg.CONF.register_opts(ovs_network_opts, 'OVSNETWORK')

OVS_NETWORK_RPC_VERSION = "1.0"

OVS_NETWORK = 'ovs_network'
class OVSNetworkAgentRpcApiMixin(object): 
    """A mix-in class supporting plugins to send message to the ovsnetwork agent."""

    def _get_ovs_network_create_topic(self, host=None):
        return topics.get_topic_name(self.topic,
                                     OVS_NETWORK,                                     
                                     topics.CREATE,
                                     host)
    
    def _get_ovs_network_update_topic(self, host=None):
        return topics.get_topic_name(self.topic,
                                     OVS_NETWORK,                                     
                                     topics.UPDATE,
                                     host)                                 
                                     
    def _get_ovs_network_delete_topic(self, host=None):
        return topics.get_topic_name(self.topic,
                                     OVS_NETWORK,                                     
                                     topics.DELETE,
                                     host) 
                                     
    def ovs_network_created(self, context, ovs_network):
        if not ovs_network:
            return
        self.cast(context,
            self.make_msg('ovs_network_created',ovs_network=ovs_network),
            version=OVS_NETWORK_RPC_VERSION,
            topic=self._get_ovs_network_create_topic(ovs_network['host']))
        
    def ovs_network_updated(self, context, id, ovs_network):
        if not id or not ovs_network:
            return
        self.cast(context,
             self.make_msg('ovs_network_updated', ovs_network=ovs_network),
             version=OVS_NETWORK_RPC_VERSION,
             topic=self._get_ovs_network_update_topic(ovs_network['host']))
    
    def ovs_network_deleted(self, context, id, host):
        if not id:
            return
        self.cast(context,
             self.make_msg('ovs_network_deleted', id=id),
             version=OVS_NETWORK_RPC_VERSION,
             topic=self._get_ovs_network_delete_topic(host))
                                                
                         
class OVSNetworkAgentRpcCallbackMixin(object):
    """A mix-in that enable ovs agent to call ovs network agent."""
    
    ovs_network_agent = None
    def _ovs_network_agent_not_set(self):
        LOG.warning(_("ovs network agent binding currently not set. "
                      "This should be set by the end of the init "
                      "process."))

    def ovs_network_created(self, context, **kwargs):
        """Callback for ovs network create.

        :param ovs_network: new ovs network
        """
        ovs_network = kwargs.get('ovs_network', {})
        LOG.debug(
            _("ovs network %s created on remote: %s"), ovs_network, cfg.CONF.host)
        if not self.ovs_network_agent:
            return self._ovs_network_agent_not_set()
        self.ovs_network_agent.ovs_network_created(context, ovs_network)

    def ovs_network_updated(self, context, **kwargs):
        """Callback for ovs network update.

        :param ovs_network: updated ovs network
        """
        ovs_network = kwargs.get('ovs_network', {})
        LOG.debug(
            _("ovs network %s updated on remote: %s"), ovs_network, cfg.CONF.host)
        if not self.ovs_network_agent:
            return self._ovs_network_agent_not_set()
        self.ovs_network_agent.ovs_network_updated(context, id, ovs_network)

    def ovs_network_deleted(self, context, id):
        """Callback for ovs network update.

        :param id: ovs network's id
        """
        LOG.debug(
            _("ovs network %s deleted on remote: %s"), id, cfg.CONF.host)
        if not self.ovs_network_agent:
            return self._ovs_network_agent_not_set()
        self.ovs_network_agent.ovs_network_deleted(context, id)
 
    
class OVSNetworkAgentRpcMixin(object):
    """A mix-in that enable ovsnetwork agent support in agent implementations"""

    def __init__(self):
        self.ovs_network_driver = cfg.CONF.OVSNETWORK.ovs_network_driver
        if self.ovs_network_driver:
            LOG.debug(_("Loading ovs network driver %s"), self.ovs_network_driver)
            self.ovs_network_driver = importutils.import_object(self.ovs_network_driver)
        else:
            LOG.debug(_("ovs network driver is not defined on %s!"), cfg.CONF.host)

    def ovs_network_created(self, context, ovs_network):
        if self.ovs_network_driver:
            self.ovs_network_driver.ovs_network_created(self, context, ovs_network)
        LOG.info(_("Create ovs network %s by driver %s"), ovs_network, self.ovs_network_driver)
    def ovs_network_updated(self, context, id, ovs_network):
        if self.ovs_network_driver:
            self.ovs_network_driver.ovs_network_updated(self, context, id, ovs_network)
        LOG.info(_("Update ovs network %s by driver %s"), ovs_network, self.ovs_network_driver)
    def ovs_network_deleted(self, context, id):
        if self.ovs_network_driver:
            self.ovs_network_driver.ovs_network_deleted(self, context, id)
        LOG.info(_("Delete ovs network %s by driver %s"), id, self.ovs_network_driver)
