#from oslo.config import cfg

from quantum.common import topics
from quantum.openstack.common import importutils
from quantum.openstack.common import log as logging
from quantum.openstack.common.rpc import proxy
from quantum.agent.linux import ovs_lib

LOG = logging.getLogger(__name__)

OVSNETWORK_RPC_VERSION = "1.0"

OVSNETWORK = 'ovsnetwork'
class OVSNetworkAgentRpcApiMixin(object): 
    
    def _get_ovsnetwork_create_topic(self):
        return topics.get_topic_name(self.topic,
                                     OVSNETWORK,                                     
                                     topics.CREATE)
    
    def _get_ovsnetwork_update_topic(self):
        return topics.get_topic_name(self.topic,
                                     OVSNETWORK,                                     
                                     topics.UPDATE)                                 
                                     
    def _get_ovsnetwork_delete_topic(self):
        return topics.get_topic_name(self.topic,
                                     OVSNETWORK,                                     
                                     topics.DELETE) 
                                     
    def ovsnetwork_create(self, context, ovsnetwork):
        if not ovsnetwork:
            return
        self.fanout_cast(context,
                         self.make_msg('ovsnetwork_created',ovsnetwork=ovsnetwork),
                         version=OVSNETWORK_RPC_VERSION,
                         topic=self._get_ovsnetwork_create_topic())    
        print "fanout success!"                                               
        
    def ovsnetwork_update(self, context, id, ovsnetwork):
        if not id or not ovsnetwork:
            return
        self.fanout_cast(context,
                         self.make_msg('ovsnetwork_updated',ovsnetwork=ovsnetwork),
                         version=OVSNETWORK_RPC_VERSION,
                         topic=self._get_ovsnetwork_update_topic())
    
    def ovsnetwork_delete(self, context, id):
        if not id:
            return
        self.fanout_cast(context,
                         self.make_msg('ovsnetwork_deleted',id=id),
                         version=OVSNETWORK_RPC_VERSION,
                         topic=self._get_ovsnetwork_delete_topic())  
                         
                         
                                                
                         
class OVSNetworkAgentRpcCallbackApiMixin(object):
    NIC_NAME_LEN = 14
    
    def get_veth_pair_names(self, id):
        #vpl veth  pair in ovs-link,vpo veth pair in ovs
        return (("vpb%s" % id)[:self.NIC_NAME_LEN],
                ("vpo%s" % id)[:self.NIC_NAME_LEN])
    
    def ovsnetwork_created(self, context, **kwargs):
        
        '''
        #if ovs-link bridge don't exist then create it,and link it to br-int
        bridges=ovs_lib.get_bridges(self.root_helper)
        if 'ovs-link' not in bridges:
            ovs_link = ovs_lib.OVSBridge('ovs-link',self.root_helper)
            ovs_link = ovs_link.run_vsctl(["add-br",'ovs-link'])
            ovs_lib._create_veth_pair('veth-br-int','veth-ovs-link',self.root_helper)
            ovs_lib.create_ovs_vif_port('br-int','veth-br-int',self.root_helper)
            ovs_lib.create_ovs_vif_port('ovs-link','veth-ovs-link',self.root_helper)
        '''
        
        ovsnetwork = kwargs.get('ovsnetwork', {}) 
        ovs_id = ovsnetwork.get('id',None) 
        if not ovs_id:
           return            
        ovs_name = 'ovs' + ovs_id
        ovs_name = ovs_name[:self.NIC_NAME_LEN]
        
        #controller_ipv4_address = ovsnetwork.get('controller_ipv4_address',None)
        #controller_port_num = ovsnetwork.get('controller_port_num',None)
        #root_helper come from ovs_quantum_agent
        ovs_br = ovs_lib.OVSBridge(ovs_name,self.root_helper)                  
        ovs_br.run_vsctl(["add-br",ovs_name])
        v1_name,v2_name = self.get_veth_pair_names(ovs_id)
        #print 'v1_name,v2_name',v1_name,v2_name
        ovs_lib._create_veth_pair(v1_name,v2_name,self.root_helper) 
                     
        ovs_lib.create_ovs_vif_port('br-int',v1_name,self.root_helper)
        ovs_lib.create_ovs_vif_port(ovs_name,v2_name,self.root_helper)
        #if controller_ipv4_address and controller_port_num:
        #    ovs_br.run_vsctl(['set-controller',ovs_name,'tcp:'+controller_ipv4_address+':'+str(controller_port_num)])
        LOG.info(_("OVS Network Created Successfully: %s"),ovs_name)

    def ovsnetwork_updated(self, context, **kwargs):
        ovsnetwork = kwargs.get('ovsnetwork', {})  
        ovsid = ovsnetwork.get('id',None)
        #print kwargs,'\n',"hello"
        if not ovsid:
            return
        ovs_name = 'ovs'+ovsid
        ovs_name = ovs_name[:self.NIC_NAME_LEN]    
        controller_ipv4_address = ovsnetwork.get('controller_ipv4_address',None)
        controller_port_num = ovsnetwork.get('controller_port_num',None)
        ovs_br = ovs_lib.OVSBridge(ovs_name,self.root_helper)
        if not controller_ipv4_address and not controller_port_num:            
            ovs_br.run_vsctl(['del-controller',ovs_name])
            LOG.info(_("OVS Network Delete Controller Successfully: %s"),ovs_name)
        elif controller_ipv4_address and controller_port_num:
            ovs_br.run_vsctl(['set-controller',ovs_name,'tcp:'+controller_ipv4_address+':'+str(controller_port_num)])
            LOG.info(_("OVS Network Set Controller Successfully: %s"),ovs_name)
        else: 
            pass
            
    def ovsnetwork_deleted(self, context, **kwargs):
        ovs_id = kwargs.get('id',None)              
        if not ovs_id:
            return 
        #root_helper come from ovs_quantum_agent
        ovs_name = 'ovs'+ovs_id
        ovs_name = ovs_name[:self.NIC_NAME_LEN]  
        ovs_br = ovs_lib.OVSBridge(ovs_name,self.root_helper)
        ovs_br.run_vsctl(["del-br",ovs_name])
        v1_name,v2_name = self.get_veth_pair_names(ovs_id)
        ovs_lib._delete_veth_pair(v1_name,v2_name,self.root_helper)
        #ovs_link = ovs_lib.OVSBridge('ovs-link',self.root_helper)
        #ovs_link.delete_port(v1_name)
        br_int = ovs_lib.OVSBridge('br-int',self.root_helper)
        br_int.delete_port(v1_name)
        '''
        bridges=ovs_lib.get_bridges(self.root_helper)
        last_ovs_bridge = True
        for bridge in bridges:
            if bridge[:3] == 'ovs' and bridge != 'ovs-link':
                last_ovs_bridge = False
                break
        
        if last_ovs_bridge:
            ovs_link.run_vsctl(["del-br",'ovs-link'])
            ovs_lib._delete_veth_pair('veth-br-int','veth-ovs-link',self.root_helper)
            br_int = ovs_lib.OVSBridge('br-int',self.root_helper)
            br_int.delete_port('veth-br-int') 
        '''           
        LOG.info(_("OVS Network Deleted Successfully: %s"),ovs_name)        

