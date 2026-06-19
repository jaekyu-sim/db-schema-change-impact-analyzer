import csv
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from src.application import analyze, discover_projects


class ApplicationTest(unittest.TestCase):
    def test_discovers_project_and_writes_all_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "test" / "sample-migration"
            project.mkdir(parents=True)
            (project / "pom.xml").write_text("<project><dependency>mybatis</dependency></project>", encoding="utf-8")
            (project / "MigrationMapper.xml").write_text('''<mapper namespace="MigrationMapper">
              <insert id="migrate">
                INSERT INTO target_customer (customer_id, display_name)
                SELECT s.id, UPPER(s.name) FROM source_customer s
              </insert>
            </mapper>''', encoding="utf-8")

            self.assertEqual([project.resolve()], discover_projects(root / "test"))
            results = analyze(root / "test", root / "output")

            self.assertEqual(2, results[0].target_column_count)
            self.assertTrue(all(path.is_file() for path in results[0].reports))
            with results[0].reports[1].open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual("source_customer", rows[0]["source_table"])
            self.assertEqual("id", rows[0]["source_column"])
            self.assertEqual("UPPER(s.name)", rows[1]["source_expression"])
            with ZipFile(results[0].reports[2]) as archive:
                self.assertIn("xl/worksheets/sheet1.xml", archive.namelist())

    def test_requires_a_spring_project_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                discover_projects(directory)


if __name__ == "__main__":
    unittest.main()
