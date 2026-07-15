from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Any

import pandas as pd

from app.services.files import load_column_descriptions, load_dataframe, save_upload


@dataclass
class IngestedDataset:
    dataset_id: str
    dataframe: pd.DataFrame
    source_path: Path
    working_path: Path
    original_name: str
    source_type: str
    file_type: str
    column_descriptions: dict[str, str] = field(default_factory=dict)
    lineage: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return Path(self.original_name).stem

    def source_metadata(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "file_type": self.file_type,
            "original_name": self.original_name,
            "source_path": str(self.source_path),
            "working_path": str(self.working_path),
            "lineage": self.lineage,
            "warnings": self.warnings,
        }


class FileConnector:
    source_type = "file"

    def ingest_upload(self, file_obj: BinaryIO, filename: str) -> IngestedDataset:
        dataset_id, source_path, file_type = save_upload(file_obj, filename)
        df = load_dataframe(source_path)
        if df.empty:
            raise ValueError("Dataset is empty.")

        working_path = Path(source_path).with_suffix(".working.csv")
        df.to_csv(working_path, index=False)
        column_descriptions = load_column_descriptions(source_path)

        return IngestedDataset(
            dataset_id=dataset_id,
            dataframe=df,
            source_path=source_path,
            working_path=working_path,
            original_name=filename,
            source_type=self.source_type,
            file_type=file_type,
            column_descriptions=column_descriptions,
            lineage={
                "read_path": str(source_path),
                "working_path": str(working_path),
                "mode": "uploaded file import",
                "refreshable": False,
            },
        )
