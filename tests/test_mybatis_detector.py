import tempfile
import unittest
from pathlib import Path

from src.detectors.mybatis_detector import MyBatisDetector
from src.scanner.project_scanner import ProjectScanner


class MyBatisDetectorTest(unittest.TestCase):
    def test_detects_mybatis_xml_reads_writes_and_bind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "OrderMapper.xml").write_text('''<?xml version="1.0" encoding="UTF-8"?>
<mapper namespace="sample.OrderMapper">
  <select id="readOrders" resultType="OrderDto">
    SELECT o.id, o.amount * 100 AS amount_cents FROM source_order o JOIN customer c ON c.id=o.customer_id
  </select>
  <insert id="writeOrders" parameterType="OrderDto">
    <bind name="normalized" value="amount / 100"/>
    INSERT INTO target_order (order_id, amount) VALUES (#{id}, #{normalized})
  </insert>
</mapper>''', encoding="utf-8")

            result = MyBatisDetector().detect(ProjectScanner().scan(root))

            self.assertEqual(2, len(result.sql_units))
            self.assertEqual(["source_order", "customer"], result.source_read_operations[0].tables)
            self.assertEqual(["o.id", "o.amount * 100 AS amount_cents"], result.source_read_operations[0].columns)
            self.assertEqual("target_order", result.target_write_operations[0].target_table)
            self.assertEqual(["order_id", "amount"], result.target_write_operations[0].target_columns)
            self.assertEqual("normalized", result.variable_assignments[0].variable)

    def test_invalid_mapper_xml_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Broken.xml").write_text("<mapper><select", encoding="utf-8")
            self.assertEqual([], MyBatisDetector().detect(ProjectScanner().scan(root)).sql_units)


if __name__ == "__main__":
    unittest.main()

