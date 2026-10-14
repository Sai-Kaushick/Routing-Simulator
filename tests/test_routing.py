import unittest
from topology.graph_manager import default_topology
from routing.rip import rip_shortest_path
from routing.ospf import ospf_shortest_path

class RoutingTests(unittest.TestCase):
    def setUp(self): self.g = default_topology()
    def test_rip_path(self):
        path, hops, _ = rip_shortest_path(self.g, "R0", "R3")
        self.assertEqual((path[0], path[-1], hops), ("R0", "R3", 2))
    def test_ospf_path(self):
        path, cost, _ = ospf_shortest_path(self.g, "R0", "R3")
        self.assertEqual((path[0], path[-1], cost), ("R0", "R3", 2))
    def test_disconnected(self):
        self.g.remove_edge("R1", "R3"); self.g.remove_edge("R2", "R3")
        self.assertEqual(rip_shortest_path(self.g, "R0", "R3")[0], [])
        self.assertEqual(ospf_shortest_path(self.g, "R0", "R3")[0], [])

if __name__ == "__main__": unittest.main()
