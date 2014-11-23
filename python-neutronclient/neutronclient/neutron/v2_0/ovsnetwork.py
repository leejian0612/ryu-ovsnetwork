# Copyright 2012 OpenStack Foundation.
# All Rights Reserved
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

import argparse
import logging

from neutronclient.common import exceptions
from neutronclient.neutron import v2_0 as neutronV20
from neutronclient.openstack.common.gettextutils import _

_logger = logging.getLogger(__name__)

class ListOVSNetwork(neutronV20.ListCommand):
    """List ovs-networks that belong to a given tenant."""

    resource = 'ovs_network'
    list_columns = ['id', 'name', 'host']
    pagination_support = True
    sorting_support = True


class ShowOVSNetwork(neutronV20.ShowCommand):
    """Show information of a given ovs network."""

    resource = 'ovs_network'
    list_columns = ['id', 'name', 'host', 'controller_ipv4_address', 'controller_port_num']
    allow_names = True


class CreateOVSNetwork(neutronV20.CreateCommand):
    """Create a ovs network."""

    resource = 'ovs_network'

    def add_known_arguments(self, parser):
        parser.add_argument(
            '--name', metavar='NAME',
            help=_('Name of ovs network.'))
        parser.add_argument(
            '--host',
            help=_('Host of ovs network.'))
        parser.add_argument(
            '--controller_ipv4_address', metavar='IPADDR',
            help=_('Controller ipv4 address of the ovs network.'))
        parser.add_argument(
            '--controller_port_num',
            type=int,
            help=_('Controller port num of the ovs network.'))

    def args2body(self, parsed_args):
        body = {'ovs_network': {}}
        if parsed_args.name:
            body['ovs_network'].update(
                {'name': parsed_args.name})
        if parsed_args.host:
            body['ovs_network'].update(
                {'host': parsed_args.host})
        if parsed_args.controller_ipv4_address:
            body['ovs_network'].update(
                {'controller_port_num': parsed_args.controller_ipv4_address})
        if parsed_args.controller_port_num:
            body['ovs_network'].update({'controller_port_num': parsed_args.controller_port_num})
        return body


class DeleteOVSNetwork(neutronV20.DeleteCommand):
    """Delete a given ovs network."""

    resource = 'ovs_network'
    allow_names = True


class UpdateOVSNetwork(neutronV20.UpdateCommand):
    """Update a given ovs network."""

    resource = 'ovs_network'

    def add_known_arguments(self, parser):
        parser.add_argument(
            '--name',
            help=_('Name of ovs network.'))
        parser.add_argument(
            '--controller_ipv4_address', metavar='IPADDR',
            help=_('Controller ipv4 address of the ovs network.'))
        parser.add_argument(
            '--controller_port_num',
            type=int,
            help=_('Controller port num of the ovs network.'))

    def args2body(self, parsed_args):
        body = {'ovs_network': {}}
        if parsed_args.name:
            body['ovs_network'].update(
                {'name': parsed_args.name})
        if parsed_args.controller_ipv4_address:
            body['ovs_network'].update(
                {'controller_ipv4_address': parsed_args.controller_ipv4_address})
        if parsed_args.controller_port_num:
            body['ovs_network'].update(
                {'controller_port_num': parsed_args.controller_port_num})
        return body

class ListOVSLink(neutronV20.ListCommand):
    """List ovs-links that belong to a given tenant or a specified ovs network."""

    resource = 'ovs_link'
    list_columns = ['id', 'name', 'left_ovs_id', 'right_ovs_id']
    pagination_support = True
    sorting_support = True


class ShowOVSLink(neutronV20.ShowCommand):
    """Show information of a given ovs link."""

    resource = 'ovs_link'
    list_columns = ['id', 'name', 'left_ovs_id', 'left_port_id', 'right_ovs_id', 'right_port_id']
    allow_names = True


class CreateOVSLink(neutronV20.CreateCommand):
    """Create a ovs link."""

    resource = 'ovs_link'

    def add_known_arguments(self, parser):
        parser.add_argument(
            '--name', metavar='NAME',
            help=_('Name of ovs network.'))
        parser.add_argument(
            'left_ovs_id', metavar='OVS_NETWORK_ID',
            help=_("Left ovs network's id of the ovs link."))
        parser.add_argument(
            'right_ovs_id', metavar='OVS_NETWORK_ID',
            help=_("Right ovs network's id of the ovs link."))

    def args2body(self, parsed_args):
        body = {'ovs_link': {
            'left_ovs_id': parsed_args.left_ovs_id,
            'right_ovs_id':parsed_args.right_ovs_id}}
        if parsed_args.name:
            body['ovs_link'].update(
                {'name': parsed_args.name})
        return body


class DeleteOVSLink(neutronV20.DeleteCommand):
    """Delete a given ovs link."""

    resource = 'ovs_link'
    allow_names = True


class UpdateOVSLink(neutronV20.UpdateCommand):
    """Update a given ovs link."""

    resource = 'ovs_link'

    def add_known_arguments(self, parser):
        parser.add_argument(
            '--name',
            help=_('Name of ovs link.'))
        parser.add_argument(
            '--left_ovs_id', metavar='OVS_NETWORK_ID',
            help=_("Left ovs network's id of the ovs link."))
        parser.add_argument(
            '--right_ovs_id', metavar='OVS_NETWORK_ID',
            help=_("Right ovs network's id of the ovs link."))

    def args2body(self, parsed_args):
        body = {'ovs_link': {}}
        if parsed_args.name:
            body['ovs_link'].update(
                {'name': parsed_args.name})
        if parsed_args.left_ovs_id:
            body['ovs_link'].update(
                {'left_ovs_link': parsed_args.left_ovs_link})
        if parsed_args.right_ovs_id:
            body['ovs_link'].update(
                {'right_ovs_link': parsed_args.right_ovs_link})

class ListVMLink(neutronV20.ListCommand):
    """List vm-links that belong to a given tenant or a specified ovs network."""

    resource = 'vm_link'
    list_columns = ['id', 'name', 'ovs_network_id']
    pagination_support = True
    sorting_support = True


class ShowVMLink(neutronV20.ShowCommand):
    """Show information of a given vm link."""

    resource = 'vm_link'
    list_columns = ['id', 'name', 'vm_host', 'vm_port_id', 'ovs_network_id', 'ovs_port_id']
    allow_names = True


class CreateVMLink(neutronV20.CreateCommand):
    """Create a vm link."""

    resource = 'vm_link'

    def add_known_arguments(self, parser):
        parser.add_argument(
            '--name', metavar='NAME',
            help=_('Name of ovs network.'))
        parser.add_argument(
            '--vm_host', metavar='VM_HOST',
            help=_("vm's host for this vm link."))
        parser.add_argument(
            'ovs_network_id', metavar='OVS_NETWORK_ID',
            help=_("ovs network's id of the ovs link."))

    def args2body(self, parsed_args):
        body = {'vm_link': {
            'ovs_network_id':parsed_args.ovs_network_id}}
        if parsed_args.name:
            body['vm_link'].update(
                {'name': parsed_args.name})
        if parsed_args.vm_host:
            body['vm_link'].update(
                {'vm_host': parsed_args.vm_host})
        return body


class DeleteVMLink(neutronV20.DeleteCommand):
    """Delete a given vm link."""

    resource = 'vm_link'
    allow_names = True


class UpdateVMLink(neutronV20.UpdateCommand):
    """Update a given vm link."""

    resource = 'vm_link'

    def add_known_arguments(self, parser):
        parser.add_argument(
            '--name',
            help=_('Name of vm link.'))
        parser.add_argument(
            '--ovs_network_id', metavar='OVS_NETWORK_ID',
            help=_("ovs network's id of the ovs link."))

    def args2body(self, parsed_args):
        body = {'vm_link': {}}
        if parsed_args.name:
            body['vm_link'].update(
                {'name': parsed_args.name})
        if parsed_args.ovs_network_id:
            body['vm_link'].update(
                {'ovs_network_id': parsed_args.ovs_network_id})
        return body
