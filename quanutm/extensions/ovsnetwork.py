# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Nicira Networks, Inc.
# All rights reserved.
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
# @author: Dan Wendlandt, Nicira, Inc
#
from abc import ABCMeta
from abc import abstractmethod

from oslo.config import cfg

from quantum.api import extensions
from quantum.api.v2 import attributes as attr
from quantum.api.v2 import base
from quantum.common import exceptions as qexception
from quantum import manager

class OVSNetworkNotFound(qexception.NotFound):
    message = _("OVS Network %(id)s could not be found")
    
class InvalidPortNum(qexception.InvalidInput):
    message = _("Invalid value for port %(port)s")
    
def convert_to_validate_port_num(port):
    if port is None:
        return port
    try:
        val = int(port)
    except (ValueError, TypeError):
        raise InvalidPortNum(port=port)

    if val >= 0 and val <= 65535:
        return val
    else:
        raise InvalidPortNum(port=port)
        
OVSNETWORKS = 'ovsnetworks'
RESOURCE_ATTRIBUTE_MAP = {
    OVSNETWORKS : {
    'id': {'allow_post': False, 'allow_put': False,
           'validate': {'type:uuid': None},
           'is_visible': True,
           'primary_key': True},
          
    'tenant_id': {'allow_post': False, 'allow_put': False,
                  'validate': {'type:string': None},
                  'is_visible': True},
          
    'controller_ipv4_address':{'allow_post': True, 
                               'allow_put': True,
                               'validate': {'type:ip_address_or_none': None},
                               'is_visible': True,
                               'default':None},
    'controller_port_num':{'allow_post': True,
                           'allow_put': True,
                           'convert_to': convert_to_validate_port_num,
                           'is_visible': True,
                           'default':None}
    }
}

EXTENDED_ATTRIBUTES_2_0 = {
    'networks': {'is_an_ovs': {'allow_post': True,'allow_put': False,
                               'is_visible': True,
                               'convert_to': attr.convert_to_boolean,
                               'default': False} 
                }
}
#we need extend port resource and add connect_to_ovs action to it
#qovs quantum ovs Capitalize first letter

class Ovsnetwork(extensions.ExtensionDescriptor):
    """OVS Network extension."""

    @classmethod
    def get_name(cls):
        return "OVS Network"

    @classmethod
    def get_alias(cls):
        return "OVSNETWORK"

    @classmethod
    def get_description(cls):
        return "The OVS Network extension."

    @classmethod
    def get_namespace(cls):
        # todo
        return "http://docs.openstack.org/ext/securitygroups/api/v2.0"

    @classmethod
    def get_updated(cls):
        return "2012-10-05T10:00:00-00:00"
        
    @classmethod    
    def get_resources(cls):
        """Returns Ext Resources."""
        #my_plurals = [(key, key[:-1]) for key in RESOURCE_ATTRIBUTE_MAP.keys()]
        my_plurals = [('ovsnetworks','ovsnetwork')]
        attr.PLURALS.update(dict(my_plurals))
        exts = []
        plugin = manager.QuantumManager.get_plugin()
        #for resource_name in ['security_group', 'security_group_rule']:
        #collection_name = resource_name.replace('_', '-') + "s"
        resource_name = 'ovsnetwork'
        collection_name = 'ovsnetworks'
        params = RESOURCE_ATTRIBUTE_MAP.get(collection_name, dict())
        #quota.QUOTAS.register_resource_by_name(resource_name)
        controller = base.create_resource(collection_name,
                                          resource_name,
                                          plugin, params, allow_bulk=True,
                                          allow_pagination=True,
                                          allow_sorting=True)
        
        ex = extensions.ResourceExtension(collection_name,
                                          controller,
                                          attr_map=params)
        exts.append(ex)

        return exts

    def get_extended_resources(self, version):
        if version == "2.0":
            return EXTENDED_ATTRIBUTES_2_0   
        else:
            return {}  

class OVSNetworkPluginBase(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def get_ovsnetworks(self, context, filters=None, fields=None,
                        sorts=None, limit=None, marker=None,
                        page_reverse=False):
        pass    

    @abstractmethod
    def get_ovsnetwork(self, context, id, fields=None):
        pass    
        
    @abstractmethod
    def update_ovsnetwork(self, context, id, ovsnetwork):
        pass   
       
