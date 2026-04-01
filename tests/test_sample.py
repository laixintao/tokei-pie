import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tokei_pie.main import (
    Sector,
    build_file_tree,
    common_prefix,
    merge_sector_langs,
    merge_sectors,
    pre_parse_data,
    read_reports,
    read_root,
    remove_lang_from_key,
)

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "samples")


class TestBuildFileTree(unittest.TestCase):
    def test_single_file(self):
        reports = [{"name": os.path.join("src", "main.py"), "stats": {}}]
        tree = build_file_tree(reports)
        self.assertIn("src", tree)
        self.assertIn(os.path.join("src", "main.py"), tree["src"])

    def test_nested_files(self):
        reports = [
            {"name": os.path.join("a", "b", "c.py"), "stats": {}},
        ]
        tree = build_file_tree(reports)
        self.assertIn("a", tree)
        self.assertIn(os.path.join("a", "b"), tree["a"])
        self.assertIn(os.path.join("a", "b", "c.py"), tree[os.path.join("a", "b")])


class TestCommonPrefix(unittest.TestCase):
    def test_common_prefix_found(self):
        strings = [
            os.path.join("root", "src", "a.py"),
            os.path.join("root", "src", "b.py"),
        ]
        prefixes = strings[0].split(os.sep)
        result = common_prefix(prefixes, strings)
        self.assertEqual(result, os.path.join("root", "src") + os.sep)

    def test_no_common_prefix(self):
        strings = [
            os.path.join("a", "file.py"),
            os.path.join("b", "file.py"),
        ]
        prefixes = strings[0].split(os.sep)
        result = common_prefix(prefixes, strings)
        self.assertEqual(result, "")


class TestMergeSectors(unittest.TestCase):
    def _make_sector(self, sid, code=10, blanks=2, comments=1, lang="Python"):
        return Sector(
            id=sid,
            label=sid,
            parent_id="",
            lang_type=lang,
            code=code,
            blanks=blanks,
            comments=comments,
        )

    def test_merge_adds_stats(self):
        left = self._make_sector("src/main.py", code=10, blanks=2, comments=1)
        right = self._make_sector("src/main.py", code=5, blanks=1, comments=0)
        merged = merge_sectors(left, right)
        self.assertEqual(merged.code, 15)
        self.assertEqual(merged.blanks, 3)
        self.assertEqual(merged.comments, 1)

    def test_merge_lang_from_dominant(self):
        left = self._make_sector("f", code=20, lang="Python")
        right = self._make_sector("f", code=5, lang="JavaScript")
        merged = merge_sectors(left, right)
        self.assertEqual(merged.lang_type, "Python")


class TestRemoveLangFromKey(unittest.TestCase):
    def test_removes_first_segment(self):
        sector = Sector(
            id=os.path.join("Python", "src", "main.py"),
            label="main.py",
            parent_id=os.path.join("Python", "src"),
            lang_type="Python",
            code=10,
            blanks=1,
            comments=0,
        )
        result = remove_lang_from_key(sector)
        self.assertEqual(result.id, os.path.join("src", "main.py"))
        self.assertEqual(result.parent_id, "src")


class TestMergeSectorLangs(unittest.TestCase):
    def test_merges_duplicate_ids(self):
        sectors = [
            Sector(
                id=os.path.join("Python", "src", "f.py"),
                label="f.py",
                parent_id=os.path.join("Python", "src"),
                lang_type="Python",
                code=10,
                blanks=0,
                comments=0,
            ),
            Sector(
                id=os.path.join("Cython", "src", "f.py"),
                label="f.py",
                parent_id=os.path.join("Cython", "src"),
                lang_type="Cython",
                code=5,
                blanks=0,
                comments=0,
            ),
        ]
        result = merge_sector_langs(sectors)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].code, 15)


class TestReadRootWithSample(unittest.TestCase):
    def setUp(self):
        sample_path = os.path.join(SAMPLES_DIR, "running_page.json")
        with open(sample_path) as f:
            self.data = json.load(f)

    def test_read_root_returns_sectors(self):
        data = pre_parse_data(self.data)
        sectors = read_root(data)
        self.assertIsInstance(sectors, list)
        self.assertGreater(len(sectors), 0)
        for sector in sectors:
            self.assertIsInstance(sector, Sector)

    def test_total_key_excluded(self):
        data = pre_parse_data(self.data)
        sectors = read_root(data)
        ids = [s.id for s in sectors]
        self.assertNotIn("Total", ids)


if __name__ == "__main__":
    unittest.main()
