"""Ryu app: learning switch + prioritised handling of critical monitoring traffic.

Run:  ryu-manager sdn_controller/controller.py
 - UDP 9998 (critical alerts): highest flow priority (300) and marked DSCP 46 (EF)
 - UDP 9999 (normal reports):  priority 200
 - everything else:            plain L2 forwarding, priority 1
"""
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types

REPORT_PORT, ALERT_PORT = 9999, 9998
PRIO_CRIT, PRIO_REPORT, PRIO_L2 = 300, 200, 1


class HealthSDN(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port = {}

    def add_flow(self, dp, prio, match, actions, idle=60):
        p = dp.ofproto_parser
        inst = [p.OFPInstructionActions(dp.ofproto.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(p.OFPFlowMod(datapath=dp, priority=prio, match=match,
                                 instructions=inst, idle_timeout=idle))

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def on_switch_features(self, ev):
        dp = ev.msg.datapath
        p, o = dp.ofproto_parser, dp.ofproto
        self.add_flow(dp, 0, p.OFPMatch(),
                      [p.OFPActionOutput(o.OFPP_CONTROLLER, o.OFPCML_NO_BUFFER)], idle=0)
        self.logger.info("switch s%s connected, table-miss installed", dp.id)

    def install_for_destination(self, dp, dst, out_port):
        p = dp.ofproto_parser
        out = [p.OFPActionOutput(out_port)]
        crit = [p.OFPActionSetField(ip_dscp=46), p.OFPActionOutput(out_port)]
        self.add_flow(dp, PRIO_CRIT, p.OFPMatch(eth_type=0x0800, ip_proto=17,
                      udp_dst=ALERT_PORT, eth_dst=dst), crit)
        self.add_flow(dp, PRIO_REPORT, p.OFPMatch(eth_type=0x0800, ip_proto=17,
                      udp_dst=REPORT_PORT, eth_dst=dst), out)
        self.add_flow(dp, PRIO_L2, p.OFPMatch(eth_dst=dst), out)
        self.logger.info("s%s: flows installed for %s -> port %s (critical UDP %s prioritised)",
                         dp.id, dst, out_port, ALERT_PORT)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def on_packet_in(self, ev):
        msg = ev.msg
        dp = msg.datapath
        p, o = dp.ofproto_parser, dp.ofproto
        in_port = msg.match["in_port"]
        eth = packet.Packet(msg.data).get_protocol(ethernet.ethernet)
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
        self.mac_to_port.setdefault(dp.id, {})[eth.src] = in_port
        out_port = self.mac_to_port[dp.id].get(eth.dst, o.OFPP_FLOOD)
        if out_port != o.OFPP_FLOOD:
            self.install_for_destination(dp, eth.dst, out_port)
        data = msg.data if msg.buffer_id == o.OFP_NO_BUFFER else None
        dp.send_msg(p.OFPPacketOut(datapath=dp, buffer_id=msg.buffer_id, in_port=in_port,
                                   actions=[p.OFPActionOutput(out_port)], data=data))
