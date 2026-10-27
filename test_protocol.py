import sys, unittest
sys.path.insert(0, ".")
from protocol import encode, decode

GOOD = {"host_id": "h1", "seq": 0, "timestamp": 1.0, "cpu_percent": 10.0,
        "memory_percent": 20.0, "process_count": 100, "network_rx_bytes": 1, "network_tx_bytes": 2}


class T(unittest.TestCase):
    def test_roundtrip(self):
        self.assertEqual(decode(encode(GOOD)), GOOD)

    def test_garbage(self):
        for bad in (b"\xff\xfe", b"hello", b"[1,2]", b"{}"):
            with self.assertRaises(ValueError):
                decode(bad)

    def test_range_and_type(self):
        with self.assertRaises(ValueError):
            decode(encode({**GOOD, "cpu_percent": 150}))
        with self.assertRaises(ValueError):
            decode(encode({**GOOD, "seq": "x"}))

    def test_too_large(self):
        with self.assertRaises(ValueError):
            decode(b"x" * 2000)


if __name__ == "__main__":
    unittest.main()
