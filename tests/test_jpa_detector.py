import tempfile
import unittest
from pathlib import Path

from src.detectors.jpa_detector import JpaDetector
from src.scanner.project_scanner import ProjectScanner


class JpaDetectorTest(unittest.TestCase):
    def test_repository_save_uses_entity_table_and_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "TargetCustomer.java").write_text('''
                @Entity
                @Table(name = "target_customer")
                class TargetCustomer {
                    @Column(name = "customer_id") private Long id;
                    @Column(name = "display_name") private String name;
                }
            ''', encoding="utf-8")
            (root / "TargetCustomerRepository.java").write_text('''
                interface TargetCustomerRepository extends JpaRepository<TargetCustomer, Long> {}
            ''', encoding="utf-8")
            (root / "MigrationService.java").write_text('''
                class MigrationService {
                    TargetCustomerRepository targetRepository;
                    void migrate(TargetCustomer customer) { targetRepository.save(customer); }
                }
            ''', encoding="utf-8")

            result = JpaDetector().detect(ProjectScanner().scan(root))

            self.assertEqual("target_customer", result.target_write_operations[0].target_table)
            self.assertEqual(["customer_id", "display_name"], result.target_write_operations[0].target_columns)


if __name__ == "__main__":
    unittest.main()
