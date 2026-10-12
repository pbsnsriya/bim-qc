from io import BytesIO
import unittest
from uuid import UUID
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from ifcqc.bcf import build_bcfzip


class BcfExportTests(unittest.TestCase):
    def test_archive_contains_version_topic_and_linked_viewpoint(self):
        issue = {
            "rule_id": "ids:wall-name",
            "severity": "error",
            "title": "Missing required Name",
            "message": "IFCWALL #73 requires a Name.",
            "entity_id": 73,
            "entity_type": "IFCWALL",
            "global_id": "2WallDemoGuid000000003",
        }
        with ZipFile(BytesIO(build_bcfzip([issue]))) as archive:
            names = archive.namelist()
            self.assertIn("bcf.version", names)
            topic_folder = next(name.split("/")[0] for name in names if name.endswith("markup.bcf"))
            UUID(topic_folder)
            markup = ET.fromstring(archive.read(f"{topic_folder}/markup.bcf"))
            viewpoint = ET.fromstring(archive.read(f"{topic_folder}/viewpoint.bcfv"))

        self.assertEqual("2.1", ET.fromstring(ZipFile(BytesIO(build_bcfzip([]))).read("bcf.version")).attrib["VersionId"])
        self.assertEqual("Missing required Name", markup.findtext("./Topic/Title"))
        self.assertEqual("2WallDemoGuid000000003", viewpoint.find("./Components/Selection/Component").attrib["IfcGuid"])
        self.assertEqual(
            markup.find("./Viewpoints/ViewPoint").attrib["Guid"],
            viewpoint.attrib["Guid"],
        )

    def test_empty_issue_list_is_a_valid_empty_archive(self):
        with ZipFile(BytesIO(build_bcfzip([]))) as archive:
            self.assertEqual(["bcf.version"], archive.namelist())


if __name__ == "__main__":
    unittest.main()
