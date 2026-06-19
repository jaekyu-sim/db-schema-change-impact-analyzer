from __future__ import annotations

import csv
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from src.llm.mapping_agent import ColumnMapping


HEADERS = ["target_table", "target_column", "source_table", "source_column", "source_expression", "mapping_status", "evidence"]


class ReportWriter:
    def write_markdown(self, path: str | Path, mappings: list[ColumnMapping]) -> None:
        rows = ["| " + " | ".join(HEADERS) + " |", "| " + " | ".join(["---"] * len(HEADERS)) + " |"]
        rows.extend("| " + " | ".join(value.replace("|", "\\|") for value in self._values(item)) + " |" for item in mappings)
        Path(path).write_text("\n".join(rows) + "\n", encoding="utf-8")

    def write_csv(self, path: str | Path, mappings: list[ColumnMapping]) -> None:
        with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADERS)
            writer.writerows(self._values(item) for item in mappings)

    def write_excel(self, path: str | Path, mappings: list[ColumnMapping]) -> None:
        rows = [HEADERS, *(self._values(item) for item in mappings)]
        sheet_rows = []
        for row_number, row in enumerate(rows, start=1):
            cells = []
            for column_number, value in enumerate(row, start=1):
                reference = f"{self._excel_column(column_number)}{row_number}"
                cells.append(f'<c r="{reference}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
            sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
        sheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews>'
            f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
        )
        with ZipFile(path, "w", ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", self._content_types())
            archive.writestr("_rels/.rels", self._root_relationships())
            archive.writestr("xl/workbook.xml", self._workbook())
            archive.writestr("xl/_rels/workbook.xml.rels", self._workbook_relationships())
            archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    @staticmethod
    def _values(item: ColumnMapping) -> list[str]:
        return [str(getattr(item, key) or "").replace("\n", " ") for key in HEADERS]

    @staticmethod
    def _excel_column(number: int) -> str:
        value = ""
        while number:
            number, remainder = divmod(number - 1, 26)
            value = chr(65 + remainder) + value
        return value

    @staticmethod
    def _content_types() -> str:
        return ('<?xml version="1.0" encoding="UTF-8"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                '</Types>')

    @staticmethod
    def _root_relationships() -> str:
        return ('<?xml version="1.0" encoding="UTF-8"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                '</Relationships>')

    @staticmethod
    def _workbook() -> str:
        return ('<?xml version="1.0" encoding="UTF-8"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Gap Mapping" sheetId="1" r:id="rId1"/></sheets></workbook>')

    @staticmethod
    def _workbook_relationships() -> str:
        return ('<?xml version="1.0" encoding="UTF-8"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                '</Relationships>')
