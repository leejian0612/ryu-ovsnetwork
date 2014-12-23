from oslo.config import cfg

from neutron.agent.linux import ovs_lib
from neutron.agent.linux import ip_lib
from neutron.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class OVSNetworkDriver(object):
    """The driver for ovs network extension implementation on the agent side."""
    
    NIC_NAME_LEN = 14

    def __init__(self):
        self.root_helper = cfg.CONF.AGENT.root_helper
        self.ip_wrapper = ip_lib.IPWrapper(root_helper=self.root_helper)
        self.bridge = ovs_lib.OVSBridge('br-int', self.root_helper)
        LOG.info(_("OVSNetworkDriver is initialized successfully.\n"))
   
    def get_ovs_network_name_from_id(self, id):
        ovs_network_name = 'ovs' + str(id)
        return ovs_network_name[:self.NIC_NAME_LEN]

    def get_ovs_network_br(self, ovs_network_id):
        ovs_network_name = self.get_ovs_network_name_from_id(ovs_network_id)
        ovs_network_br = ovs_lib.OVSBridge(ovs_network_name, self.root_helper)
        return ovs_network_br

    def get_ovs_network_controller_name(self, ovs_network):
        if ovs_network['controller_ipv4_address'] and ovs_network['controller_port_num']:
            controller_name = str(''.join(['tcp:', ovs_network['controller_ipv4_address'], ':', str(ovs_network['controller_port_num'])]))
        else:
            controller_name = None
        return controller_name

    def ovs_network_created(self, context, ovs_network):
        ovs_network_br = self.get_ovs_network_br(ovs_network['id'])
        ovs_network_br.create()
        controller_name = self.get_ovs_network_controller_name(ovs_network)
        if controller_name:
            ovs_network_br.set_controller([controller_name])
        LOG.info(_("OVS Network %s is created successfully, and it's controller is %s.\n"), ovs_network, controller_name)

    def ovs_network_updated(self, context, ovs_network):
        controller_name = self.get_ovs_network_controller_name(ovs_network)
        if controller_name:
            ovs_network_br = self.get_ovs_network_br(ovs_network['id'])
            try:
                if ovs_network_br.get_controller():
                    ovs_network_br.del_controller()
            finally:
                ovs_network_br.set_controller([controller_name])
            LOG.info(_("OVS Network %s is updated successfully, and it's controller is %s"), id, controller_name)

    def ovs_network_deleted(self, context, id):
        ovs_network_br = self.get_ovs_network_br(id)
        ovs_network_br.destroy()
        LOG.info(_("OVS Network %s is deleted successfully."), id)

    def get_ovs_link_pair_names(self, id):
        # veth pair names for ports of ovs link, 
        # olo is short for ovs link's port on ovs network side
        # olb is short for ovs link's port on br-int side
        return (("olo%s" % id)[:self.NIC_NAME_LEN],
                ("olb%s" % id)[:self.NIC_NAME_LEN])

    def create_veth_pair_ports(self, name1, name2):
        self.ip_wrapper.add_veth(name1, name2)

    def ovs_link_left_endpoint_created(self, context, ovs_link):
        # create veth ports and add them to ovs bridges
        olo_port,olb_port = self.get_ovs_link_pair_names(ovs_link['left_port_id'])
        self.create_veth_pair_ports(olo_port, olb_port)
        ovs_network_br = self.get_ovs_network_br(ovs_link['left_ovs_id'])
        ovs_network_br.add_port(olo_port)
        self.bridge.add_port(olb_port)
        
        # add flows 
        # Improvement is needed to support multi compute nodes -- lijian
        olb_ofport = self.bridge.get_port_ofport(olb_port)
        self.bridge.add_flow(table='0', priority=10, in_port=olb_ofport, actions='set_tunnel:%s,resubmit(,1)'%ovs_link['left_tunnel_id'])
        self.bridge.add_flow(table='1', priority=10, tun_id=ovs_link['right_tunnel_id'], actions='output:%s'%olb_ofport)
        LOG.info(_("Left endpoint of ovs link %s is created successfully.\n"), ovs_link)

    def ovs_link_right_endpoint_created(self, context, ovs_link):
        # create veth ports and add them to ovs bridges
        olo_port,olb_port = self.get_ovs_link_pair_names(ovs_link['right_port_id'])
        self.create_veth_pair_ports(olo_port, olb_port)
        ovs_network_br = self.get_ovs_network_br(ovs_link['right_ovs_id'])
        ovs_network_br.add_port(olo_port)
        self.bridge.add_port(olb_port)
        
        # add flows 
        # Improvement needed to support multi compute nodes -- lijian
        olb_ofport = self.bridge.get_port_ofport(olb_port)
        self.bridge.add_flow(table='0', priority=10, in_port=olb_ofport, actions='set_tunnel:%s,resubmit(,1)'%ovs_link['right_tunnel_id'])
        self.bridge.add_flow(table='1', priority=10, tun_id=ovs_link['left_tunnel_id'], actions='output:%s'%olb_ofport)
        LOG.info(_("Right endpoint of ovs link %s is created successfully.\n"), ovs_link)

    def ovs_link_left_endpoint_deleted(self, context, ovs_link):
        olo_port,olb_port = self.get_ovs_link_pair_names(ovs_link['left_port_id'])
        olb_ofport = self.bridge.get_port_ofport(olb_port)
        ovs_network_br = self.get_ovs_network_br(ovs_link['left_ovs_id'])
        ovs_network_br.delete_port(olo_port)
        self.bridge.delete_port(olb_port)
        ip_link_device = ip_lib.IPDevice(olb_port, root_helper=self.root_helper)
        ip_link_device.link.delete()
       
        #delete flows       
        self.bridge.delete_flows(table='0', in_port=olb_ofport)
        self.bridge.delete_flows(table='1', tun_id=ovs_link['right_tunnel_id'])
        LOG.info(_("Left endpoint of ovs link %s is deleted successfully.\n"), ovs_link)

    def ovs_link_right_endpoint_deleted(self, context, ovs_link):
        olo_port,olb_port = self.get_ovs_link_pair_names(ovs_link['right_port_id'])
        olb_ofport = self.bridge.get_port_ofport(olb_port)
        ovs_network_br = self.get_ovs_network_br(ovs_link['right_ovs_id'])
        ovs_network_br.delete_port(olo_port)
        self.bridge.delete_port(olb_port)
        ip_link_device = ip_lib.IPDevice(olb_port, root_helper=self.root_helper)
        ip_link_device.link.delete()
       
        #delete flows       
        self.bridge.delete_flows(table='0', in_port=olb_ofport)
        self.bridge.delete_flows(table='1', tun_id=ovs_link['left_tunnel_id'])
        LOG.info(_("Right endpoint of ovs link %s is deleted successfully.\n"), ovs_link)
  
    def get_vm_link_ovs_endpoint_pair_names(self, id):
        return (("vlo%s" % id)[:self.NIC_NAME_LEN],
                ("vlb%s" % id)[:self.NIC_NAME_LEN])

    #def get_vm_link_vm_endpoint_ovs_port_name(self, id):
    #    return ("qvo%s" % id)[:self.NIC_NAME_LEN]

    def vm_link_ovs_endpoint_created(self, context, vm_link):
        vlo_port,vlb_port  = self.get_vm_link_ovs_endpoint_pair_names(vm_link['ovs_port_id'])
        self.create_veth_pair_ports(vlo_port, vlb_port)
        ovs_network_br = self.get_ovs_network_br(vm_link['ovs_network_id'])
        ovs_network_br.add_port(vlo_port)
        self.bridge.add_port(vlb_port)

        vlb_ofport = self.bridge.get_port_ofport(vlb_port)
        self.bridge.add_flow(table='0', priority=10, in_port=vlb_ofport, actions='set_tunnel:%s,resubmit(,1)'%vm_link['ovs_tunnel_id'])
        self.bridge.add_flow(table='1', priority=10, tun_id=vm_link['vm_tunnel_id'], actions='output:%s'%vlb_ofport)
        LOG.info(_("OVS endpoint of vm link %s is created successfully.\n"), vm_link)

    def vm_link_ovs_endpoint_deleted(self, context, vm_link):
        vlo_port,vlb_port = self.get_vm_link_ovs_endpoint_pair_names(vm_link['ovs_port_id'])
        vlb_ofport = self.bridge.get_port_ofport(vlb_port)
        ovs_network_br = self.get_ovs_network_br(vm_link['ovs_network_id'])
        ovs_network_br.delete_port(vlo_port)
        self.bridge.delete_port(vlb_port)
        ip_link_device = ip_lib.IPDevice(vlb_port, root_helper=self.root_helper)
        ip_link_device.link.delete()
       
        #delete flows       
        self.bridge.delete_flows(table='0', in_port=vlb_ofport)
        self.bridge.delete_flows(table='1', tun_id=vm_link['vm_tunnel_id'])
        LOG.info(_("OVS endpoint of vm link %s is deleted successfully.\n"), vm_link)

    def vm_link_vm_endpoint_created(self, context, vm_link):
        vlb_ofport = vm_link['vm_ofport']
        self.bridge.add_flow(table='0', priority=10, in_port=vlb_ofport, actions='set_tunnel:%s,resubmit(,1)'%vm_link['vm_tunnel_id'])
        self.bridge.add_flow(table='1', priority=10, tun_id=vm_link['ovs_tunnel_id'], actions='output:%s'%vlb_ofport)
        LOG.info(_("VM endpoint of vm link %s is Created successfully.\n"), vm_link)

    def vm_link_vm_endpoint_updated(self, context, vm_link):
        vlb_ofport = vm_link['vm_ofport']
        self.bridge.delete_flows(table='1', tun_id=vm_link['old_ovs_tunnel_id'])
        self.bridge.add_flow(table='1', tun_id=vm_link['ovs_tunnel_id'], actions='output:%s'%vlb_ofport)
        LOG.info(_("VM endpoint of vm link %s is updated successfully.\n"), vm_link)

    def vm_link_vm_endpoint_deleted(self, context, vm_link):
        vlb_ofport = vm_link['vm_ofport']
        self.bridge.delete_flows(table='0', in_port=vlb_ofport)
        self.bridge.delete_flow(table='1', tun_id=vm_link['ovs_tunnel_id'])
        LOG.info(_("VM endpoint of vm link %s is updated successfully.\n"), vm_link)
