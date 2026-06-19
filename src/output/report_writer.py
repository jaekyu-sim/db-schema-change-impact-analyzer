from __future__ import annotations

import csv
from pathlib import Path

from src.llm.mapping_agent import ColumnMapping


HEADERS = ["target_table", "target_column", "source_table", "source_column", "source_expression", "evidence"]


class ReportWriter:
    def write_markdown(self, path: str | Path, mappings: list[ColumnMapping]) -> None:
        rows = ["| " + " | ".join(HEADERS) + " |", "| " + " | ".join(["---"] * len(HEADERS)) + " |"]
        rows.extend("| " + " | ".join(self._values(item)) + " |" for item in mappings)
        Path(path).write_text("\n".join(rows) + "\n", encoding="utf-8")

    def write_csv(self, path: str | Path, mappings: list[ColumnMapping]) -> None:
        with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADERS)
            writer.writerows(self._values(item) for item in mappings)

    def write_excel(self, path: str | Path, mappings: list[ColumnMapping]) -> None:
        try:
            from openpyxl import Workbook
        except ImportError as exc:
            raise RuntimeError("Excel output requires: pip install '.[excel]'") from exc
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Gap Mapping"
        sheet.append(HEADERS)
        for item in mappings:
            sheet.append(self._values(item))
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        workbook.save(path)

    @staticmethod
    def _values(item: ColumnMapping) -> list[str]:
        return [str(getattr(item, key) or "").replace("|", "\\|").replace("\n", " ") for key in HEADERS]

