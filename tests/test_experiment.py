import unittest
import networkx as nx
from events.failure_simulator import make_failure_event, apply_link_failure
from ns2.trace_parser import measure_recovery_time

class ExperimentTests(unittest.TestCase):
    def test_failure_event(self):
        event = make_failure_event("R0", "R1", 4.0)
        self.assertEqual(event["type"], "link_failure")
        self.assertEqual(event["time"], 4.0)

    def test_remove_link_copy_only(self):
        g = nx.Graph()
        g.add_edge("R0", "R1")
        h = apply_link_failure(g, "R0", "R1")
        self.assertTrue(g.has_edge("R0", "R1"))
        self.assertFalse(h.has_edge("R0", "R1"))

    def test_recovery(self):
        self.assertAlmostEqual(measure_recovery_time(5.0, 5.8), 0.8)
        self.assertIsNone(measure_recovery_time(5.0, None))

if __name__ == "__main__":
    unittest.main()
