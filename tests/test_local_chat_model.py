import unittest
from unittest.mock import patch

from src.llm.mapping_agent import LocalChatOpenAIMappingModel


class FakeMessage:
    content = '''```json
    {"source_table":"source_customer","source_column":"id","source_expression":"s.id","evidence":"mapper select"}
    ```'''


class FakeChatModel:
    def invoke(self, prompt):
        return FakeMessage()


class LocalChatOpenAIMappingModelTest(unittest.TestCase):
    def test_raw_mode_parses_openai_compatible_chat_response(self) -> None:
        model = LocalChatOpenAIMappingModel(
            model="local-model",
            base_url="http://localhost:8000/v1",
            structured_output_method="raw",
            chat_model=FakeChatModel(),
        )
        result = model.infer("Target: target_customer.customer_id")
        self.assertEqual("source_customer", result["source_table"])
        self.assertEqual("id", result["source_column"])

    def test_requires_local_model_name(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "SLLM_MODEL"):
                LocalChatOpenAIMappingModel(model=None, structured_output_method="raw", chat_model=FakeChatModel())


if __name__ == "__main__":
    unittest.main()
