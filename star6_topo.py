from mininet.topo import Topo

class starTopology(Topo):
    def build(self):

# Add switches
switches = [self.addSwitch(f"s{i+1}") for i in range(6)]

# Add hosts and connect to switches
for i, switch in enumerate(switches):
    for j in range(20):
        host_id = i * 20 + j + 1
        host = self.addHost(f"h{host_id}")
        self.addLink(host, switch)

# Fully connect all switches to each other (full mesh)
for i in range(len(switches)):
    for j in range(i + 1, len(switches)):
        self.addLink(switches[i], switches[j])

topo = {"custom": "starTopology}
