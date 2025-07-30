from mininet.topo import Topo

class Meshtopology(Topo):
    def build(self):

        # Adding switches
        switches = [self.addSwitch(f"s{k+1}") for k in range(6)]

        # Adding hosts and connecting to switches
        for k, switch in enumerate(switches):
            for n in range(20):
                host_id = k * 20 + n + 1
                host = self.addHost(f"h{host_id}")
                self.addLink(host, switch)

        # Fully connecting all switches to each other (full meshing)
        for k in range(len(switches)):
            for n in range(k + 1, len(switches)):
                self.addLink(switches[k], switches[n])

topos = {"custom": Meshtopology}

# sudo mn --custom mesh_topo.py --topo custom --controller=remote,ip=127.0.0.1,port=6653 --switch ovs,protocols=OpenFlow13
