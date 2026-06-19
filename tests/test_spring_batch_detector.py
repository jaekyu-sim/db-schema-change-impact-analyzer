import tempfile
import unittest
from pathlib import Path

from src.detectors.spring_batch_detector import SpringBatchDetector
from src.scanner.project_scanner import ProjectScanner


class SpringBatchDetectorTest(unittest.TestCase):
    def test_jdbc_batch_writer_sql_is_target_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "BatchConfig.java").write_text('''
                class BatchConfig {
                    JdbcBatchItemWriter<Customer> writer() {
                        return new JdbcBatchItemWriterBuilder<Customer>()
                            .sql("INSERT INTO target_customer (customer_id, name) VALUES (:id, :name)")
                            .build();
                    }
                }
            ''', encoding="utf-8")

            result = SpringBatchDetector().detect(ProjectScanner().scan(root))

            self.assertEqual("target_customer", result.target_write_operations[0].target_table)
            self.assertEqual(["customer_id", "name"], result.target_write_operations[0].target_columns)


if __name__ == "__main__":
    unittest.main()
