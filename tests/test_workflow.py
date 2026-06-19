import tempfile
import unittest
from pathlib import Path

from src.detectors.mybatis_detector import MyBatisDetector
from src.index.project_index import ProjectIndex
from src.llm.mapping_agent import MappingAgent
from src.scanner.project_scanner import ProjectScanner
from src.workflow.langgraph_workflow import MappingWorkflow


class RetryModel:
    def __init__(self) -> None:
        self.calls = 0

    def infer(self, prompt: str):
        self.calls += 1
        if self.calls == 1:
            return {"source_table": None, "source_column": None, "source_expression": None, "evidence": None}
        return {"source_table": "source_customer", "source_column": "id", "source_expression": "s.id", "evidence": "expanded context"}


class MappingWorkflowTest(unittest.TestCase):
    def test_unresolved_column_retries_with_expanded_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Mapper.xml").write_text('''<mapper namespace="M">
              <insert id="write">INSERT INTO target_customer (customer_id) VALUES (#{id})</insert>
            </mapper>''', encoding="utf-8")
            project = ProjectScanner().scan(root)
            index = ProjectIndex.build(project, [MyBatisDetector()])
            model = RetryModel()

            mappings = MappingWorkflow(MappingAgent(model)).run(project, index)

            self.assertEqual(2, model.calls)
            self.assertEqual("source_customer", mappings[0].source_table)
            self.assertEqual("MAPPED", mappings[0].mapping_status)


if __name__ == "__main__":
    unittest.main()
