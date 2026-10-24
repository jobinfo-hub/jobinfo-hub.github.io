"""Offline Work24 XML regression tests; no credentials or network needed."""
import unittest
import xml.etree.ElementTree as ET
from scripts.fetch_work24 import normalize, safe_link


class Work24Tests(unittest.TestCase):
    def test_normalize(self):
        xml = """<wantedRoot><total>2</total>
        <wanted><wantedAuthNo>A123</wantedAuthNo><company>Example</company>
        <title>Developer</title><closeDt>20991231</closeDt>
        <wantedInfoUrl>https://www.work24.go.kr/job</wantedInfoUrl></wanted>
        <wanted><wantedAuthNo>A123</wantedAuthNo><company>Example</company>
        <title>Developer</title><closeDt>20991231</closeDt></wanted></wantedRoot>"""
        items = normalize(ET.fromstring(xml))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["deadline"], "2099-12-31")

    def test_reject_untrusted_links(self):
        self.assertEqual(safe_link("https://evil.example/job"), "")
        self.assertEqual(safe_link("javascript:alert(1)"), "")
        self.assertTrue(safe_link("https://www.work24.go.kr/job"))

    def test_invalid_root(self):
        with self.assertRaises(ValueError):
            normalize(ET.fromstring("<error>bad key</error>"))


if __name__ == "__main__":
    unittest.main()
