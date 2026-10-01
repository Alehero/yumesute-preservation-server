import tempfile
import unittest
from pathlib import Path
from certificate_store import prepare_ca

class CertificateStoreTest(unittest.TestCase):
    def test_new_store_is_stable_and_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a"; a.mkdir()
            b = Path(tmp) / "b"; b.mkdir()
            first = prepare_ca(a)
            self.assertEqual(first, prepare_ca(a))
            self.assertTrue(first[1].startswith("Yumesute Local "))
            self.assertNotEqual(first[1:], prepare_ca(b)[1:])

    def test_reuse_is_persisted_without_copying_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a"; a.mkdir()
            b = Path(tmp) / "b"; b.mkdir()
            original = prepare_ca(a)
            before = (original[0] / "mitmproxy-ca.pem").read_bytes()
            self.assertEqual(original, prepare_ca(b, original[0]))
            self.assertEqual(original, prepare_ca(b))
            self.assertFalse((b / "mitmproxy").exists())
            self.assertEqual(before, (original[0] / "mitmproxy-ca.pem").read_bytes())

    def test_mismatched_download_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a"; a.mkdir()
            b = Path(tmp) / "b"; b.mkdir()
            ca, *_ = prepare_ca(a); cb, *_ = prepare_ca(b)
            (ca / "mitmproxy-ca-cert.cer").write_bytes((cb / "mitmproxy-ca-cert.cer").read_bytes())
            with self.assertRaisesRegex(ValueError, "do not match"): prepare_ca(a)

    def test_missing_explicit_store_is_not_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            with self.assertRaises(ValueError): prepare_ca(p, p / "missing")
            self.assertFalse((p / "missing").exists())
