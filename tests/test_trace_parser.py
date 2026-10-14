import tempfile, unittest
from pathlib import Path
from ns2.trace_parser import parse_trace

class TraceTests(unittest.TestCase):
    def test_basic(self):
        data = "+ 0.10 0 1 cbr 512 ------- 1 0.0 3.0 0 1\nr 0.20 2 3 cbr 512 ------- 1 0.0 3.0 0 1\n+ 0.30 0 1 cbr 512 ------- 1 0.0 3.0 1 2\nd 0.40 1 2 cbr 512 ------- 1 0.0 3.0 1 2\n"
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.tr"; p.write_text(data)
            m = parse_trace(p, sim_end=1.0)
        self.assertEqual((m["sent_packets"], m["received_packets"], m["lost_packets"]), (2, 1, 1))

    def test_parse_failure_trace_cohort(self):
        from ns2.trace_parser import parse_failure_trace
        data = (
            "+ 4.90 0 1 cbr 512 ------- 1 0.0 3.0 0 10\n"
            "- 4.90 0 1 cbr 512 ------- 1 0.0 3.0 0 10\n"
            "+ 4.95 0 1 rtProtoDV 4 ------- 0 0.2 1.1 -1 99\n"
            "r 4.98 0 1 rtProtoDV 4 ------- 0 0.2 1.1 -1 99\n"
            "r 5.05 1 3 cbr 512 ------- 1 0.0 3.0 0 10\n"
            "+ 5.10 0 2 cbr 512 ------- 1 0.0 3.0 0 11\n"
            "- 5.10 0 2 cbr 512 ------- 1 0.0 3.0 0 11\n"
            "r 5.18 2 3 cbr 512 ------- 1 0.0 3.0 0 11\n"
        )
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "fail.tr"
            p.write_text(data)
            res = parse_failure_trace(p, failure_time=5.0, sim_end=6.0)
        self.assertEqual(res["before"]["sent_packets"], 1)
        self.assertEqual(res["before"]["received_packets"], 1)
        self.assertEqual(res["after"]["sent_packets"], 1)
        self.assertEqual(res["after"]["received_packets"], 1)
        self.assertAlmostEqual(res["recovery_time_s"], 0.18)

if __name__ == "__main__": unittest.main()
