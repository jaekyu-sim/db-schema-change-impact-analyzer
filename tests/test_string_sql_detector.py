import tempfile
import unittest
from pathlib import Path

from src.detectors.string_sql_detector import StringSqlDetector
from src.scanner.project_scanner import ProjectScanner


class StringSqlDetectorTest(unittest.TestCase):
    def test_detects_string_builder_sql(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "SqlFactory.java").write_text('''class SqlFactory {
              String make() {
                StringBuilder sql = new StringBuilder("INSERT INTO target_account ");
                sql.append("(account_id, status) ");
                sql.append("VALUES (?, ?)");
                return sql.toString();
              }
            }''', encoding="utf-8")
            result = StringSqlDetector().detect(ProjectScanner().scan(root))
            self.assertEqual(1, len(result.sql_units))
            self.assertEqual("target_account", result.target_write_operations[0].target_table)
            self.assertEqual(["account_id", "status"], result.target_write_operations[0].target_columns)
            self.assertEqual("string_builder", result.sql_units[0].metadata["construction"])

    def test_detects_concatenated_select(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "SqlFactory.java").write_text('''class SqlFactory {
              String sql = "SELECT s.id, s.code " + "FROM source_status s " + "WHERE s.enabled = true";
            }''', encoding="utf-8")
            result = StringSqlDetector().detect(ProjectScanner().scan(root))
            self.assertEqual(["source_status"], result.source_read_operations[0].tables)
            self.assertEqual(["s.id", "s.code"], result.source_read_operations[0].columns)


if __name__ == "__main__":
    unittest.main()

