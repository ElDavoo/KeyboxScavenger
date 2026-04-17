import tempfile
import unittest
from pathlib import Path

from scavenger.storage import KeyboxStorage
from scavenger.xml_normalizer import normalize_xml_payload


class KeyboxStorageTests(unittest.TestCase):
    def test_persist_writes_sha_and_latest_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            storage = KeyboxStorage(output_dir)

            payload_one = b"<keybox>one</keybox>"
            payload_two = b"<keybox>two</keybox>"

            first = storage.persist(payload_one)
            second = storage.persist(payload_one)
            third = storage.persist(payload_two)

            self.assertTrue(first.sha_path.exists())
            self.assertTrue(second.sha_path.exists())
            self.assertEqual(first.sha_path, second.sha_path)
            self.assertTrue(first.wrote_sha_file)
            self.assertFalse(second.wrote_sha_file)

            self.assertTrue(third.sha_path.exists())
            self.assertNotEqual(first.sha_path, third.sha_path)
            self.assertEqual((output_dir / "keybox.xml").read_bytes(), payload_two)

    def test_normalized_xml_avoids_duplicates_from_formatting(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            storage = KeyboxStorage(output_dir)

            payload_one = b"""<AndroidAttestation>
    <!-- comment should not affect hash -->
    <Keybox DeviceID=\"A\" Product=\"B\">
      <Key>
        <CertificateChain>
          <Certificate format=\"pem\">\nABC\n</Certificate>
        </CertificateChain>
      </Key>
    </Keybox>
</AndroidAttestation>"""

            payload_two = b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<AndroidAttestation><Keybox Product=\"B\" DeviceID=\"A\"><Key><CertificateChain><Certificate format=\"pem\">ABC</Certificate></CertificateChain></Key></Keybox></AndroidAttestation>"""

            first_normalized = normalize_xml_payload(payload_one)
            second_normalized = normalize_xml_payload(payload_two)

            self.assertEqual(first_normalized, second_normalized)

            first = storage.persist(first_normalized)
            second = storage.persist(second_normalized)

            self.assertEqual(first.sha_path, second.sha_path)
            self.assertTrue(first.wrote_sha_file)
            self.assertFalse(second.wrote_sha_file)


if __name__ == "__main__":
    unittest.main()
