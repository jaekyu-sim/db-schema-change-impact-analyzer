import tempfile
import unittest
from pathlib import Path

from src.detectors.querydsl_detector import QueryDslDetector
from src.scanner.project_scanner import ProjectScanner


class QueryDslDetectorTest(unittest.TestCase):
    def test_detects_select_and_update_chains(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Customer.java").write_text('''
                @Entity @Table(name = "target_customer")
                class Customer {
                  @Column(name = "customer_id") private Long id;
                  @Column(name = "display_name") private String name;
                }
            ''', encoding="utf-8")
            (root / "Migration.java").write_text('''
                class Migration {
                  QCustomer customer = QCustomer.customer;
                  void run() {
                    queryFactory.select(customer.id, customer.name).from(customer).fetch();
                    queryFactory.update(customer).set(customer.name, "migrated").execute();
                  }
                }
            ''', encoding="utf-8")

            result = QueryDslDetector().detect(ProjectScanner().scan(root))

            self.assertEqual(["target_customer"], result.source_read_operations[0].tables)
            self.assertEqual("target_customer", result.target_write_operations[0].target_table)
            self.assertEqual(["display_name"], result.target_write_operations[0].target_columns)


if __name__ == "__main__":
    unittest.main()
