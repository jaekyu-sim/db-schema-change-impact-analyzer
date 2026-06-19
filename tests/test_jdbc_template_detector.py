import tempfile
import unittest
from pathlib import Path

from src.detectors.jdbc_template_detector import JdbcTemplateDetector
from src.scanner.project_scanner import ProjectScanner


class JdbcTemplateDetectorTest(unittest.TestCase):
    def test_detects_named_and_plain_jdbc_template_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "MigrationService.java").write_text('''
class MigrationService {
  JdbcTemplate jdbcTemplate;
  NamedParameterJdbcTemplate namedParameterJdbcTemplate;
  void migrate() {
    String readSql = "SELECT id, price FROM source_product WHERE active = true";
    jdbcTemplate.query(readSql, rowMapper);
    namedParameterJdbcTemplate.update(
      "INSERT INTO target_product (product_id, product_price) VALUES (:id, :price)", params);
  }
}
''', encoding="utf-8")

            result = JdbcTemplateDetector().detect(ProjectScanner().scan(root))

            self.assertEqual(2, len(result.method_calls))
            self.assertEqual(["source_product"], result.source_read_operations[0].tables)
            self.assertEqual("target_product", result.target_write_operations[0].target_table)
            self.assertEqual(["product_id", "product_price"], result.target_write_operations[0].target_columns)
            self.assertTrue(any(item.variable == "readSql" for item in result.variable_assignments))

    def test_detects_update_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Writer.java").write_text('''class Writer {
              JdbcTemplate jdbcTemplate;
              void run() { jdbcTemplate.update("UPDATE target_user SET name=?, updated_at=? WHERE id=?", values); }
            }''', encoding="utf-8")
            result = JdbcTemplateDetector().detect(ProjectScanner().scan(root))
            self.assertEqual(["name", "updated_at"], result.target_write_operations[0].target_columns)


if __name__ == "__main__":
    unittest.main()

