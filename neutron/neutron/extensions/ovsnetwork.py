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
# @author: Jian LI, BUPT
#
from abc import ABCMeta
from abc import abstractmethod

from oslo.config import cfg
import six

from neutron.api import extensions
from neutron.api.v2 import attributes as attr
from neutron.api.v2 import base
from neutron.common import exceptions as qexception
from neutron import manager

class OVSNetworkNotFound(qexception.NotFound):
    message = _("OVS Network %(id)s could not be found")

class InvalidPortNum(qexception.InvalidInput):
    message = _("Invalid value for port %(port)s")

class OVSNetworkHasLinks(qexception.InUse):
    message = _("OVS Network %(id)s has links")

class VMLinkNotFound(qexception.NotFound):
    message = _("VM Link %(id)s could not be found")

class HostNotSetInVMLink(qexception.NotFound):
    message = _("can not find vm_host in VMLink")

class OVSLinkNotFound(qexception.NotFound):
    message = _("OVS Link %(id)s could not be found")
    
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
        
RESOURCE_ATTRIBUTE_MAP = {
    'ovs_networks' : {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:uuid': None},
               'is_visible': True,
               'primary_key': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'validate': {'type:string': None},
                 'is_visible': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'validate': {'type:string': None},
                      'is_visible': True},
        'host': {'allow_post': True, 'allow_put': False,
                 'validate': {'type:string': None},
                 'is_visible': True,
                 'default': ''},
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
    },
    'vm_links' : {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:uuid': None},
               'is_visible': True,
               'primary_key': True},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'validate': {'type:string': None},
                      'is_visible': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'validate': {'type:string': None},
                 'is_visible': True,
                 'default': ''},
        'vm_host': {'allow_post': True, 'allow_put': False,
                    'validate': {'type:string': None},
                    'is_visible': True,
                    'default': ''},
        'ovs_network_id': {'allow_post': True, 'allow_put': True,
                           'validate': {'type:string': None},
                           'is_visible': True},
        'ovs_network_name': {'allow_post': True, 'allow_put': True,
                             'validate': {'type:string': None},
                             'is_visible': True,
                             'default': ''}
    },
    'ovs_links' : {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:uuid': None},
               'is_visible': True,
               'primary_key': True},
          
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'validate': {'type:string': None},
                      'is_visible': True},
        'name': {'allow_post': True, 'allow_put': True,
                 'validate': {'type:string': None},
                 'is_visible': True,
                 'default': ''},
        'left_ovs_id': {'allow_post': True, 'allow_put': False,
                        'validate': {'type:string': None},
                        'is_visible': True},
        'left_ovs_name': {'allow_post': True, 'allow_put': True,
                          'validate': {'type:string': None},
                          'is_visible': True,
                          'default': ''},
        'right_ovs_id': {'allow_post': True, 'allow_put': False,
                         'validate': {'type:string': None},
                         'is_visible': True},
        'right_ovs_name': {'allow_post': True, 'allow_put': True,
                           'validate': {'type:string': None},
                           'is_visible': True,
                           'default': ''}
    }
}

#we need extend port resource and add connect_to_ovs action to it

class Ovsnetwork(extensions.ExtensionDescriptor):
    """OVS Network extension."""

    @classmethod
    def get_name(cls):
        return "ovs-network"

    @classmethod
    def get_alias(cls):
        return "ovs-network"

    @classmethod
    def get_description(cls):
        return "The OVS Network extension."

    @classmethod
    def get_namespace(cls):
        # todo
        return "https://github.com/leejian0612/ryu-ovsnetwork/blob/master/README.md"

    @classmethod
    def get_updated(cls):
        return "2014-10-08T19:55:00-00:00"
        
    @classmethod    
    def get_resources(cls):
        """Returns Ext Resources."""
        my_plurals = [(key, key[:-1]) for key in RESOURCE_ATTRIBUTE_MAP.keys()]
        attr.PLURALS.update(dict(my_plurals))
        exts = []
        plugin = manager.NeutronManager.get_plugin()
        for resource_name in ['ovs_network', 'ovs_link', 'vm_link']:
            collection_name = resource_name.replace('_', '-') + "s"
            params = RESOURCE_ATTRIBUTE_MAP.get(resource_name + "s", dict())
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
            #return dict(EXTENDED_ATTRIBUTES_2_0.items() +
            #            RESOURCE_ATTRIBUTE_MAP.items())
            return dict(RESOURCE_ATTRIBUTE_MAP.items())
        else:
            return {}  


@six.add_metaclass(ABCMeta)
class OVSNetworkPluginBase(object):

    @abstractmethod
    def get_ovs_networks(self, context, filters=None, fields=None,
                        sorts=None, limit=None, marker=None,
                        page_reverse=False):
        pass    

    @abstractmethod
    def get_ovs_network(self, context, id, fields=None):
        pass    

    @abstractmethod
    def create_ovs_network(self, context, ovs_network):
        pass    
        
    @abstractmethod
    def update_ovs_network(self, context, id, ovs_network):
        pass   

    @abstractmethod
    def delete_ovs_network(self, context, id):
        pass    

    @abstractmethod
    def get_vm_links(self, context, filters=None, fields=None,
                     sorts=None, limit=None, marker=None,
                     page_reverse=False):
        pass    

    @abstractmethod
    def get_vm_link(self, context, id, fields=None):
        pass    

    @abstractmethod
    def create_vm_link(self, context, vm_link):
        pass    

    @abstractmethod
    def update_vm_link(self, context, id, vm_link):
        pass   

    @abstractmethod
    def delete_vm_link(self, context, id):
        pass    

    @abstractmethod
    def get_ovs_links(self, context, filters=None, fields=None,
                      sorts=None, limit=None, marker=None,
                      page_reverse=False):
        pass    

    @abstractmethod
    def get_ovs_link(self, context, id, fields=None):
        pass    

    @abstractmethod
    def create_ovs_link(self, context, ovs_link):
        pass    

    #@abstractmethod
    #def update_ovs_link(self, context, id, ovs_link):
    #    pass   

    @abstractmethod
    def delete_ovs_link(self, context, id):
        pass    
