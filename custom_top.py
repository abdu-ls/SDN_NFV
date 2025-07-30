from mininet.topo import Topo

class LinearTopology(Topo):
    def build(self):

     # Add switches
        s1 = self.addSwitch("s1")
        s2 = self.addSwitch("s2")
        s3 = self.addSwitch("s3")
        # Add hosts
        h1 = self.addHost('h1') # switch 1 nodes
        h2 = self.addHost('h2')
        h3 = self.addHost('h3')
        h4 = self.addHost('h4')
        h5 = self.addHost('h5')
        h6 = self.addHost('h6')
        h7 = self.addHost('h7')  # switch 2 nodes
        h8 = self.addHost('h8')
        h9 = self.addHost('h9')
        h10 = self.addHost('h10')
        h11 = self.addHost('h11')
        h12 = self.addHost('h12')
        h13 = self.addHost('h13')  # witch 3 nodes
        h14 = self.addHost('h14')
        h15 = self.addHost('h15')
        h16 = self.addHost('h16')
        h17 = self.addHost('h17')
        h18= self.addHost('h18')

        # Connect hosts to switches     
        self.addLink(h1, s1) # BCD 1
        self.addLink(h2, s1)
        self.addLink(h3, s1)
        self.addLink(h4, s1)
        self.addLink(h5, s1)
        self.addLink(h6, s1)

        self.addLink(h7, s2) # BCD 2
        self.addLink(h8, s2)
        self.addLink(h9, s2)
        self.addLink(h10, s2)
        self.addLink(h11, s2) 
        self.addLink(h12, s2)

        self.addLink(h13, s3) # BCD 3
        self.addLink(h14, s3)
        self.addLink(h15, s3)
        self.addLink(h16, s3)
        self.addLink(h17, s3) 
        self.addLink(h18, s3)

        # Connect switches together
        self.addLink(s1, s2)
        self.addLink(s2, s3)


topos = {"custom": LinearTopology}
