"""Canonical source dataset locator and metadata manager for COCO_FACTORY.

Connects the application to the authoritative 19-table manufacturing dataset at
C:\\Users\\shubh\\Desktop\\oee_v2 (or configured canonical_source_root).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd

from config import get_settings


CANONICAL_ENTITIES = [
    "machine",
    "component",
    "sensor",
    "sensor_reading",
    "sensor_reading_hourly",
    "production_order",
    "production_run",
    "downtime_event",
    "maintenance_work_order",
    "technician",
    "maintenance_log",
    "wo_part_usage",
    "spare_part",
    "supplier",
    "purchase_order",
    "product",
    "alert",
    "prediction",
    "knowledge_doc",
]


class CanonicalSourceManager:
    """Manages paths and schema verification for the canonical 19 manufacturing entities."""

    def __init__(self, source_root: Optional[str] = None) -> None:
        if source_root:
            self.root = Path(source_root)
        else:
            settings = get_settings()
            self.root = Path(getattr(settings, "canonical_source_root", r"C:\Users\shubh\Desktop\oee_v2"))

    def resolve_entity_path(self, entity_name: str) -> Optional[Path]:
        """Resolves the physical file path for a canonical entity, handling nested directories and gzip."""
        if not self.root.exists():
            return None

        # Direct CSV or CSV.GZ
        direct_csv = self.root / f"{entity_name}.csv"
        direct_gz = self.root / f"{entity_name}.csv.gz"
        if direct_csv.is_file():
            return direct_csv
        if direct_gz.is_file():
            return direct_gz

        # Nested directory case (e.g. sensor_reading.csv/sensor_reading.csv)
        nested_dir = self.root / f"{entity_name}.csv"
        if nested_dir.is_dir():
            nested_file = nested_dir / f"{entity_name}.csv"
            if nested_file.is_file():
                return nested_file
            # Check for any .csv or .csv.gz in the subdirectory
            for child in nested_dir.iterdir():
                if child.name.endswith((".csv", ".csv.gz")):
                    return child

        return None

    def get_all_entity_paths(self) -> Dict[str, Optional[Path]]:
        """Returns a mapping of entity name to resolved Path."""
        return {entity: self.resolve_entity_path(entity) for entity in CANONICAL_ENTITIES}

    def validate_dataset_presence(self) -> Tuple[bool, List[str]]:
        """Checks whether all 19 entities exist. Returns (all_present, missing_list)."""
        missing = []
        for entity in CANONICAL_ENTITIES:
            path = self.resolve_entity_path(entity)
            if not path or not path.exists():
                missing.append(entity)
        return len(missing) == 0, missing

    def read_entity_sample(self, entity_name: str, nrows: int = 5) -> Optional[pd.DataFrame]:
        """Reads a sample DataFrame for an entity."""
        path = self.resolve_entity_path(entity_name)
        if not path or not path.exists():
            return None
        return pd.read_csv(path, nrows=nrows)

    def read_entity_df(self, entity_name: str) -> Optional[pd.DataFrame]:
        """Reads full DataFrame for an entity (use with caution for high-frequency sensor readings)."""
        path = self.resolve_entity_path(entity_name)
        if not path or not path.exists():
            return None
        return pd.read_csv(path)
