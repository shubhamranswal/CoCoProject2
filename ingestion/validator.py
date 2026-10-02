"""Canonical Source and Preflight Validation Engine.

Provides thorough validation of canonical source CSV files prior to Snowflake ingestion:
1. Physical file existence
2. Schema structure (column names, column count, order)
3. Cardinality / row count checks
4. Data quality sanity checks (non-negative stock, non-negative downtime, run fraction bounds)
5. Crucial canonical invariant validations (M21 identity, PRED-000322 failure risk, SP-002 stockout)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from ingestion.canonical_source import CanonicalSourceManager
from ingestion.manifest import CANONICAL_MANIFEST, CanonicalEntityManifest


@dataclass
class PreflightValidationReport:
    """Structured report detailing results of canonical source preflight validation."""

    source_root: str
    is_valid: bool = True
    total_datasets_checked: int = 0
    total_expected_rows: int = 0
    total_actual_rows: int = 0
    files_present: Dict[str, bool] = field(default_factory=dict)
    schema_matches: Dict[str, bool] = field(default_factory=dict)
    row_counts: Dict[str, int] = field(default_factory=dict)
    row_count_matches: Dict[str, bool] = field(default_factory=dict)
    invariant_checks: Dict[str, bool] = field(default_factory=dict)
    data_quality_checks: Dict[str, bool] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def generate_summary(self) -> str:
        """Render a readable summary table of the preflight validation results."""
        lines = []
        lines.append("=" * 80)
        lines.append(f"CANONICAL SOURCE PREFLIGHT VALIDATION REPORT: {'PASSED' if self.is_valid else 'FAILED'}")
        lines.append(f"Source Directory: {self.source_root}")
        lines.append(f"Datasets Audited: {self.total_datasets_checked} / 19")
        lines.append(f"Total Rows Verified: {self.total_actual_rows:,} (Expected: {self.total_expected_rows:,})")
        lines.append("-" * 80)
        lines.append(f"{'Entity':<24} | {'Present':<8} | {'Schema':<8} | {'Actual Rows':<12} | {'Expected Rows':<12} | {'Status'}")
        lines.append("-" * 80)

        for entity, manifest in CANONICAL_MANIFEST.items():
            pres = "OK" if self.files_present.get(entity, False) else "MISSING"
            sch = "OK" if self.schema_matches.get(entity, False) else "MISMATCH"
            act_rows = self.row_counts.get(entity, 0)
            exp_rows = manifest.expected_rows
            row_st = "OK" if self.row_count_matches.get(entity, False) else "DIFF"
            overall = "PASS" if (pres == "OK" and sch == "OK" and row_st == "OK") else "FAIL"
            lines.append(f"{entity:<24} | {pres:<8} | {sch:<8} | {act_rows:<12,d} | {exp_rows:<12,d} | {overall}")

        lines.append("-" * 80)
        lines.append("CANONICAL INVARIANT CHECKS:")
        for inv_name, passed in self.invariant_checks.items():
            st = "PASS" if passed else "FAIL"
            lines.append(f"  [{st}] {inv_name}")

        lines.append("-" * 80)
        lines.append("DATA QUALITY / SANITY CHECKS:")
        for dq_name, passed in self.data_quality_checks.items():
            st = "PASS" if passed else "FAIL"
            lines.append(f"  [{st}] {dq_name}")

        if self.errors:
            lines.append("-" * 80)
            lines.append(f"ERRORS ({len(self.errors)}):")
            for err in self.errors:
                lines.append(f"  * {err}")

        lines.append("=" * 80)
        return "\n".join(lines)


class CanonicalSourceValidator:
    """Validates the canonical source dataset against manifest and domain contracts."""

    def __init__(self, source_mgr: Optional[CanonicalSourceManager] = None) -> None:
        self.source_mgr = source_mgr or CanonicalSourceManager()

    def count_file_rows(self, file_path: Path) -> int:
        """Fast newline count for CSV files excluding header."""
        with open(file_path, "rb") as f:
            total_lines = sum(1 for _ in f)
        return max(0, total_lines - 1)

    def validate_file_presence(self) -> Tuple[Dict[str, bool], List[str]]:
        """Verify presence of all 19 canonical CSV files."""
        presence = {}
        missing = []
        for entity, manifest in CANONICAL_MANIFEST.items():
            path = self.source_mgr.resolve_entity_path(entity)
            if path and path.is_file():
                presence[entity] = True
            else:
                presence[entity] = False
                missing.append(f"Missing canonical file for entity '{entity}': expected '{manifest.source_filename}'")
        return presence, missing

    def validate_schemas(self) -> Tuple[Dict[str, bool], List[str]]:
        """Verify headers and column orders of all canonical CSV files against manifest.
        
        Reads raw file headers directly using csv.reader (independent of pandas).
        Fails on any missing, extra, or misordered columns.
        """
        import csv
        schema_matches = {}
        errors = []
        for entity, manifest in CANONICAL_MANIFEST.items():
            path = self.source_mgr.resolve_entity_path(entity)
            if not path or not path.is_file():
                schema_matches[entity] = False
                continue

            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    reader = csv.reader(f)
                    raw_header = next(reader, None)

                if not raw_header:
                    schema_matches[entity] = False
                    errors.append(f"Empty or unreadable header in '{entity}': {path}")
                    continue

                actual_cols = [c.strip().lower() for c in raw_header]
                expected_cols = [c.strip().lower() for c in manifest.expected_columns]

                missing_cols = set(expected_cols) - set(actual_cols)
                extra_cols = set(actual_cols) - set(expected_cols)

                if missing_cols:
                    errors.append(f"Entity '{entity}' missing expected columns: {sorted(missing_cols)}")
                if extra_cols:
                    errors.append(f"Entity '{entity}' contains unexpected columns: {sorted(extra_cols)}")

                if actual_cols == expected_cols:
                    schema_matches[entity] = True
                else:
                    schema_matches[entity] = False
                    errors.append(
                        f"Schema mismatch for entity '{entity}': expected {len(expected_cols)} columns "
                        f"{expected_cols}, got {len(actual_cols)} columns {actual_cols}"
                    )
            except Exception as e:
                schema_matches[entity] = False
                errors.append(f"Failed to read header for '{entity}': {e}")

        return schema_matches, errors

    def validate_cardinalities(self) -> Tuple[Dict[str, int], Dict[str, bool], List[str]]:
        """Verify row counts of all 19 datasets against manifest expected rows."""
        row_counts = {}
        matches = {}
        errors = []

        for entity, manifest in CANONICAL_MANIFEST.items():
            path = self.source_mgr.resolve_entity_path(entity)
            if not path or not path.is_file():
                row_counts[entity] = 0
                matches[entity] = False
                continue

            actual_rows = self.count_file_rows(path)
            row_counts[entity] = actual_rows

            if actual_rows == manifest.expected_rows:
                matches[entity] = True
            else:
                matches[entity] = False
                errors.append(
                    f"Row count mismatch for '{entity}': expected exactly {manifest.expected_rows:,} rows, "
                    f"found {actual_rows:,} rows"
                )

        return row_counts, matches, errors

    def validate_canonical_invariants(self) -> Tuple[Dict[str, bool], List[str]]:
        """Verify the crucial domain and scenario invariants."""
        invariants = {}
        errors = []

        # 1. Machine M21 Identity
        try:
            df_m = self.source_mgr.read_entity_df("machine")
            m21 = df_m[df_m["machine_id"] == "M21"] if df_m is not None else pd.DataFrame()
            if len(m21) == 1:
                r = m21.iloc[0]
                m21_ok = (
                    r["machine_name"] == "Grinder 3"
                    and r["line_id"] == "L5"
                    and r["model"] == "GR-600"
                    and r["machine_type"] == "Grinder"
                )
                invariants["M21_IDENTITY (Grinder 3, L5, GR-600, Grinder)"] = m21_ok
                if not m21_ok:
                    errors.append(f"M21 identity invariant failed: {r.to_dict()}")
            else:
                invariants["M21_IDENTITY (Grinder 3, L5, GR-600, Grinder)"] = False
                errors.append(f"M21 not found or multiple instances: count={len(m21)}")
        except Exception as e:
            invariants["M21_IDENTITY (Grinder 3, L5, GR-600, Grinder)"] = False
            errors.append(f"Error checking M21 identity: {e}")

        # 2. Component C-M21-BRG
        try:
            df_c = self.source_mgr.read_entity_df("component")
            comp = df_c[df_c["component_id"] == "C-M21-BRG"] if df_c is not None else pd.DataFrame()
            if len(comp) == 1:
                r = comp.iloc[0]
                comp_ok = (
                    r["machine_id"] == "M21"
                    and r["component_type"] == "Drive-End Bearing"
                    and r["model"] == "6206-2RS"
                )
                invariants["C-M21-BRG_COMPONENT (Drive-End Bearing 6206-2RS)"] = comp_ok
                if not comp_ok:
                    errors.append(f"C-M21-BRG invariant failed: {r.to_dict()}")
            else:
                invariants["C-M21-BRG_COMPONENT (Drive-End Bearing 6206-2RS)"] = False
                errors.append(f"C-M21-BRG not found: count={len(comp)}")
        except Exception as e:
            invariants["C-M21-BRG_COMPONENT (Drive-End Bearing 6206-2RS)"] = False
            errors.append(f"Error checking C-M21-BRG: {e}")

        # 3. M21 Sensors (S-M21-VIB and S-M21-BTMP)
        try:
            df_s = self.source_mgr.read_entity_df("sensor")
            s_m21 = df_s[df_s["machine_id"] == "M21"] if df_s is not None else pd.DataFrame()
            vib = s_m21[s_m21["sensor_id"] == "S-M21-VIB"]
            btmp = s_m21[s_m21["sensor_id"] == "S-M21-BTMP"]
            sensors_ok = (
                len(vib) == 1
                and vib.iloc[0]["component_id"] == "C-M21-BRG"
                and vib.iloc[0]["sensor_type"] == "vibration_rms"
                and len(btmp) == 1
                and btmp.iloc[0]["component_id"] == "C-M21-BRG"
                and btmp.iloc[0]["sensor_type"] == "bearing_temperature"
            )
            invariants["M21_SENSORS (S-M21-VIB and S-M21-BTMP on C-M21-BRG)"] = sensors_ok
            if not sensors_ok:
                errors.append("M21 sensor invariant failed.")
        except Exception as e:
            invariants["M21_SENSORS (S-M21-VIB and S-M21-BTMP on C-M21-BRG)"] = False
            errors.append(f"Error checking M21 sensors: {e}")

        # 4. SP-002 Stockout Invariant
        try:
            df_sp = self.source_mgr.read_entity_df("spare_part")
            sp = df_sp[df_sp["part_id"] == "SP-002"] if df_sp is not None else pd.DataFrame()
            if len(sp) == 1:
                r = sp.iloc[0]
                sp_ok = (
                    r["compatible_model"] == "6206-2RS"
                    and int(r["stock_qty"]) == 0
                    and r["supplier_id"] == "SUP-12"
                    and int(r["lead_time_days"]) == 5
                )
                invariants["SP-002_STOCKOUT (6206-2RS, stock_qty=0, SUP-12, lead_time=5d)"] = sp_ok
                if not sp_ok:
                    errors.append(f"SP-002 stockout invariant failed: {r.to_dict()}")
            else:
                invariants["SP-002_STOCKOUT (6206-2RS, stock_qty=0, SUP-12, lead_time=5d)"] = False
                errors.append(f"SP-002 not found: count={len(sp)}")
        except Exception as e:
            invariants["SP-002_STOCKOUT (6206-2RS, stock_qty=0, SUP-12, lead_time=5d)"] = False
            errors.append(f"Error checking SP-002: {e}")

        # 5. PRED-000322 High Failure Probability
        try:
            df_pred = self.source_mgr.read_entity_df("prediction")
            pred = df_pred[df_pred["prediction_id"] == "PRED-000322"] if df_pred is not None else pd.DataFrame()
            if len(pred) == 1:
                r = pred.iloc[0]
                pred_ok = (
                    r["machine_id"] == "M21"
                    and r["suspected_component_id"] == "C-M21-BRG"
                    and float(r["failure_prob"]) == 0.95
                    and r["risk_level"] == "high"
                    and r["model_name"] == "hgb_failure_7d_v1"
                    and int(r["horizon_days"]) == 7
                )
                invariants["PRED-000322_PREDICTION (M21, C-M21-BRG, prob=0.95, risk=high, horizon=7d)"] = pred_ok
                if not pred_ok:
                    errors.append(f"PRED-000322 invariant failed: {r.to_dict()}")
            else:
                invariants["PRED-000322_PREDICTION (M21, C-M21-BRG, prob=0.95, risk=high, horizon=7d)"] = False
                errors.append(f"PRED-000322 not found: count={len(pred)}")
        except Exception as e:
            invariants["PRED-000322_PREDICTION (M21, C-M21-BRG, prob=0.95, risk=high, horizon=7d)"] = False
            errors.append(f"Error checking PRED-000322: {e}")

        # 6. Customer Order PRD-01278 Keystone Hydraulics
        try:
            df_po = self.source_mgr.read_entity_df("production_order")
            po = df_po[df_po["production_order_id"] == "PRD-01278"] if df_po is not None else pd.DataFrame()
            if len(po) == 1:
                r = po.iloc[0]
                po_ok = r["machine_id"] == "M21" and r["customer"] == "Keystone Hydraulics"
                invariants["PRD-01278_CUSTOMER (M21, customer=Keystone Hydraulics)"] = po_ok
                if not po_ok:
                    errors.append(f"PRD-01278 invariant failed: {r.to_dict()}")
            else:
                invariants["PRD-01278_CUSTOMER (M21, customer=Keystone Hydraulics)"] = False
                errors.append(f"PRD-01278 not found: count={len(po)}")
        except Exception as e:
            invariants["PRD-01278_CUSTOMER (M21, customer=Keystone Hydraulics)"] = False
            errors.append(f"Error checking PRD-01278: {e}")

        return invariants, errors

    def validate_column_types_and_nullability(self) -> Tuple[Dict[str, bool], List[str]]:
        """Verify type compatibility and primary key nullability across canonical entities."""
        type_checks = {}
        errors = []

        try:
            df_m = self.source_mgr.read_entity_df("machine")
            pk_ok = bool(df_m["machine_id"].notna().all() and (df_m["machine_id"] != "").all())
            type_checks["PK_NOT_NULL_MACHINE"] = pk_ok
            shifts_ok = bool(pd.to_numeric(df_m["shifts_per_day"], errors="coerce").notna().all())
            type_checks["NUMERIC_MACHINE_SHIFTS"] = shifts_ok
        except Exception as e:
            type_checks["PK_NOT_NULL_MACHINE"] = False
            errors.append(f"Type check failed for machine: {e}")

        try:
            df_c = self.source_mgr.read_entity_df("component")
            pk_ok = bool(df_c["component_id"].notna().all() and (df_c["component_id"] != "").all())
            type_checks["PK_NOT_NULL_COMPONENT"] = pk_ok
        except Exception as e:
            type_checks["PK_NOT_NULL_COMPONENT"] = False
            errors.append(f"Type check failed for component: {e}")

        try:
            df_sp = self.source_mgr.read_entity_df("spare_part")
            pk_ok = bool(df_sp["part_id"].notna().all() and (df_sp["part_id"] != "").all())
            type_checks["PK_NOT_NULL_SPARE_PART"] = pk_ok
            cost_ok = bool(pd.to_numeric(df_sp["unit_cost_inr"], errors="coerce").notna().all())
            type_checks["NUMERIC_SPARE_PART_COST"] = cost_ok
        except Exception as e:
            type_checks["PK_NOT_NULL_SPARE_PART"] = False
            errors.append(f"Type check failed for spare_part: {e}")

        try:
            df_pred = self.source_mgr.read_entity_df("prediction")
            pk_ok = bool(df_pred["prediction_id"].notna().all() and (df_pred["prediction_id"] != "").all())
            type_checks["PK_NOT_NULL_PREDICTION"] = pk_ok
            prob_num = pd.to_numeric(df_pred["failure_prob"], errors="coerce")
            prob_ok = bool(prob_num.notna().all() and (prob_num >= 0.0).all() and (prob_num <= 1.0).all())
            type_checks["NUMERIC_PROBABILITY_BOUNDS_0_1"] = prob_ok
        except Exception as e:
            type_checks["PK_NOT_NULL_PREDICTION"] = False
            errors.append(f"Type check failed for prediction: {e}")

        return type_checks, errors

    def validate_data_quality_rules(self) -> Tuple[Dict[str, bool], List[str]]:
        """Validate core domain constraints and referential integrity."""
        dq_results = {}
        errors = []

        try:
            df_sp = self.source_mgr.read_entity_df("spare_part")
            stock_non_neg = bool((df_sp["stock_qty"] >= 0).all()) if df_sp is not None else False
            dq_results["NON_NEGATIVE_STOCK_QTY"] = stock_non_neg
            if not stock_non_neg:
                errors.append("Found negative stock_qty in spare_part")
        except Exception as e:
            dq_results["NON_NEGATIVE_STOCK_QTY"] = False
            errors.append(f"Failed checking stock_qty: {e}")

        try:
            df_dt = self.source_mgr.read_entity_df("downtime_event")
            dt_non_neg = bool((df_dt["duration_min"] >= 0).all()) if df_dt is not None else False
            dq_results["NON_NEGATIVE_DOWNTIME_DURATION"] = dt_non_neg
            if not dt_non_neg:
                errors.append("Found negative duration_min in downtime_event")
        except Exception as e:
            dq_results["NON_NEGATIVE_DOWNTIME_DURATION"] = False
            errors.append(f"Failed checking downtime_event: {e}")

        try:
            hourly_path = self.source_mgr.resolve_entity_path("sensor_reading_hourly")
            if hourly_path and hourly_path.is_file():
                df_hrly_sample = pd.read_csv(hourly_path, nrows=5000)
                run_frac_ok = bool(((df_hrly_sample["run_fraction"] >= 0.0) & (df_hrly_sample["run_fraction"] <= 1.0)).all())
                dq_results["RUN_FRACTION_BOUNDS_0_1"] = run_frac_ok
                if not run_frac_ok:
                    errors.append("Sensor run_fraction out of bounds [0.0, 1.0]")
            else:
                dq_results["RUN_FRACTION_BOUNDS_0_1"] = False
                errors.append("Missing sensor_reading_hourly file")
        except Exception as e:
            dq_results["RUN_FRACTION_BOUNDS_0_1"] = False
            errors.append(f"Failed checking run_fraction bounds: {e}")

        return dq_results, errors

    def run_preflight_validation(self) -> PreflightValidationReport:
        """Execute complete suite of preflight validations."""
        report = PreflightValidationReport(
            source_root=str(self.source_mgr.root),
            total_datasets_checked=len(CANONICAL_MANIFEST),
            total_expected_rows=sum(m.expected_rows for m in CANONICAL_MANIFEST.values()),
        )

        # 1. Presence
        presence, pres_errs = self.validate_file_presence()
        report.files_present = presence
        report.errors.extend(pres_errs)

        # 2. Schema
        schemas, sch_errs = self.validate_schemas()
        report.schema_matches = schemas
        report.errors.extend(sch_errs)

        # 3. Cardinalities
        row_counts, count_matches, cnt_errs = self.validate_cardinalities()
        report.row_counts = row_counts
        report.row_count_matches = count_matches
        report.total_actual_rows = sum(row_counts.values())
        report.errors.extend(cnt_errs)

        # 4. Canonical Invariants
        invariants, inv_errs = self.validate_canonical_invariants()
        report.invariant_checks = invariants
        report.errors.extend(inv_errs)

        # 5. Type and Nullability Checks
        type_checks, type_errs = self.validate_column_types_and_nullability()
        report.data_quality_checks.update(type_checks)
        report.errors.extend(type_errs)

        # 6. Data Quality
        dq, dq_errs = self.validate_data_quality_rules()
        report.data_quality_checks.update(dq)
        report.errors.extend(dq_errs)

        # Determine overall validity
        all_pres = all(presence.values()) if presence else False
        all_sch = all(schemas.values()) if schemas else False
        all_cnt = all(count_matches.values()) if count_matches else False
        all_inv = all(invariants.values()) if invariants else False
        all_types = all(type_checks.values()) if type_checks else False
        all_dq = all(dq.values()) if dq else False

        report.is_valid = bool(all_pres and all_sch and all_cnt and all_inv and all_types and all_dq and len(report.errors) == 0)
        return report
