import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from scavenger.xml_normalizer import XmlNormalizationError, normalize_xml_payload


class XmlNormalizerTests(unittest.TestCase):
    def test_normalize_all_well_formed_fixture_keyboxes(self):
        fixtures_dir = Path(__file__).resolve().parent.parent / "test_keyboxes"
        fixtures = sorted(fixtures_dir.glob("*.xml"))
        self.assertGreater(len(fixtures), 0)
        malformed = []

        for fixture in fixtures:
            raw_payload = fixture.read_bytes()
            try:
                ET.fromstring(raw_payload)
            except ET.ParseError:
                malformed.append(fixture.name)
                continue

            with self.subTest(fixture=fixture.name):
                normalized = normalize_xml_payload(raw_payload)
                self.assertTrue(normalized.startswith(b"<?xml"))
                self.assertNotIn(b"<!--", normalized)

                root = ET.fromstring(normalized)
                for node in root.iter():
                    self.assertFalse(
                        any(key.lower() == "deviceid" for key in node.attrib),
                        msg=f"DeviceID attribute still present in {fixture.name}",
                    )

                for tag in ("Certificate", "PrivateKey"):
                    for block in root.findall(f".//{tag}"):
                        content = block.text or ""
                        lines = [line for line in content.splitlines() if line.strip()]
                        self.assertTrue(
                            lines,
                            msg=f"{tag} block unexpectedly empty in {fixture.name}",
                        )
                        self.assertEqual(
                            lines,
                            [line.strip() for line in lines],
                            msg=f"{tag} lines contain extra spaces in {fixture.name}",
                        )

        self.assertIn("keybox (8).xml", malformed)

    def test_removes_deviceid_attribute_before_processing(self):
        payload = (
            b"<AndroidAttestation><Keybox DeviceID='abc123' Product='foo'>"
            b"<Key/></Keybox></AndroidAttestation>"
        )

        normalized = normalize_xml_payload(payload)
        root = ET.fromstring(normalized)

        keybox = root.find(".//Keybox")
        self.assertIsNotNone(keybox)
        self.assertNotIn("DeviceID", keybox.attrib)
        self.assertEqual(keybox.attrib.get("Product"), "foo")

    def test_raises_on_malformed_orphan_deviceid_keybox_wrapper(self):
        payload = b"""<?xml version='1.0' encoding='utf-8'?>
<AndroidAttestation>
  <Keybox DeviceID='orphan'>
  <Keybox>
    <Key algorithm='ecdsa'>
      <CertificateChain>
        <NumberOfCertificates>3</NumberOfCertificates>
      </CertificateChain>
    </Key>
  </Keybox>
</AndroidAttestation>
"""

        with self.assertRaises(XmlNormalizationError):
            normalize_xml_payload(payload)

    def test_known_malformed_fixture_raises(self):
        fixture = Path(__file__).resolve().parent.parent / "test_keyboxes" / "keybox (8).xml"

        with self.assertRaises(XmlNormalizationError):
            normalize_xml_payload(fixture.read_bytes())

    def test_raises_on_unrecoverable_xml(self):
        payload = b"<AndroidAttestation><Keybox><Key></AndroidAttestation>"

        with self.assertRaises(XmlNormalizationError):
            normalize_xml_payload(payload)


if __name__ == "__main__":
    unittest.main()
