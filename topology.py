"""Mininet topology: h1,h2,h3 (agents) -- s2 -- s1 -- srv (collector), remote Ryu controller.
Run:  sudo python3 topology.py
"""
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.topo import Topo
from mininet.cli import CLI
from mininet.log import setLogLevel


class HealthTopo(Topo):
    def build(self):
        s1 = self.addSwitch("s1", protocols="OpenFlow13")
        s2 = self.addSwitch("s2", protocols="OpenFlow13")
        srv = self.addHost("srv", ip="10.0.0.100/24")
        self.addLink(srv, s1)
        self.addLink(s1, s2)
        for i in (1, 2, 3):
            self.addLink(self.addHost(f"h{i}", ip=f"10.0.0.{i}/24"), s2)


if __name__ == "__main__":
    setLogLevel("info")
    net = Mininet(topo=HealthTopo(), switch=OVSSwitch, controller=None, autoSetMacs=True)
    net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6653)
    net.start()
    CLI(net)
    net.stop()
