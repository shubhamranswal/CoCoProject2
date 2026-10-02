"""Command-Line Interface for Canonical Snowflake Ingestion.

Usage:
  # Run canonical source preflight validation:
  python -m ingestion.cli --preflight

  # Run complete dry-run planning (preflight + staging plan + copy plan + transform plan):
  python -m ingestion.cli --dry-run

  # Display the complete 19-dataset source-to-target manifest:
  python -m ingestion.cli --manifest

  # Run dry-run with explicit batch ID:
  python -m ingestion.cli --dry-run --batch-id BATCH_20261002_001
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from ingestion.canonical_source import CanonicalSourceManager
from ingestion.manifest import CANONICAL_MANIFEST, list_all_manifests, get_total_expected_rows
from ingestion.pipeline import CanonicalIngestionPipeline
from ingestion.validator import CanonicalSourceValidator


def print_manifest_table() -> None:
    """Print the exact source-to-target manifest for all 19 canonical datasets."""
    print("=" * 110)
    print("COCO_FACTORY CANONICAL DATASET SOURCE-TO-TARGET INGESTION MANIFEST")
    print("=" * 110)
    print(
        f"{'Entity':<24} | {'Source File':<28} | {'Target RAW Table':<28} | {'Expected Rows':<14} | {'PKs'}"
    )
    print("-" * 110)
    for m in list_all_manifests():
        pks = ", ".join(m.primary_keys)
        print(f"{m.entity_name:<24} | {m.source_filename:<28} | {m.raw_table.replace('COCO_FACTORY.', ''):<28} | {m.expected_rows:<14,d} | {pks}")
    print("-" * 110)
    print(f"Total Canonical Datasets: {len(CANONICAL_MANIFEST)}")
    print(f"Total Expected Rows:     {get_total_expected_rows():,}")
    print("=" * 110)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="COCO_FACTORY Canonical Snowflake Ingestion Pipeline CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Run canonical source preflight validation (presence, schema, counts, invariants)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute dry-run planning for staging, RAW COPY, and CORE conformed transforms",
    )
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="Print the exact 19-dataset source-to-target ingestion manifest",
    )
    parser.add_argument(
        "--batch-id",
        type=str,
        default=None,
        help="Custom batch ID override for RAW ingestion lineage (default: auto-generated timestamp)",
    )
    parser.add_argument(
        "--check-connection",
        action="store_true",
        help="Run read-only pre-deployment metadata validation of Snowflake account, user, role, warehouse, and context",
    )
    parser.add_argument(
        "--execute-live",
        action="store_true",
        help="Execute live ingestion against Snowflake (strictly guarded; requires confirmation)",
    )
    parser.add_argument(
        "--confirm-live-execution",
        action="store_true",
        help="Explicit confirmation required to allow live Snowflake ingestion",
    )

    args = parser.parse_args(argv)

    if args.manifest:
        print_manifest_table()
        return 0

    pipeline = CanonicalIngestionPipeline()

    if args.check_connection:
        print("\nExecuting read-only pre-deployment Snowflake connection check...")
        ok, details, msg = pipeline.verify_pre_deployment_connection()
        print(msg)
        if details:
            print(f"  Account User:      {details.get('user')}")
            print(f"  Active Role:       {details.get('role')}")
            print(f"  Warehouse:         {details.get('warehouse')}")
            db_ctx = details.get('database') or f"[Bootstrap - Target: {details.get('target_database')}]"
            schema_ctx = details.get('schema') or f"[Bootstrap - Target: {details.get('target_schema')}]"
            print(f"  Database Context:  {db_ctx}")
            print(f"  Schema Context:    {schema_ctx}")
            print(f"  Snowflake Version: {details.get('version')}")
        return 0 if ok else 1

    if args.preflight:
        print("\nExecuting canonical source preflight validation...")
        report = pipeline.validator.run_preflight_validation()
        print(report.generate_summary())
        return 0 if report.is_valid else 1

    if args.dry_run or (not args.execute_live):
        print("\nExecuting canonical ingestion dry-run planning...")
        success, plan, output = pipeline.run_dry_run(batch_id=args.batch_id)
        print(output)
        return 0 if success else 1

    if args.execute_live:
        if not args.confirm_live_execution:
            print(
                "\nERROR: Live execution blocked. Live Snowflake mutation requires both "
                "--execute-live AND --confirm-live-execution flags."
            )
            return 1
        print("\nExecuting LIVE Snowflake ingestion pipeline...")
        result = pipeline.execute_live(batch_id=args.batch_id, execute_live=True)
        print(f"Deployment Status: {'SUCCESS' if result.success else 'FAILED'}")
        print(f"Failed Stage:      {result.stage.value}")
        print(f"Batch ID:          {result.batch_id}")
        print(f"Message:           {result.message}")
        if result.error_details:
            print("Errors:")
            for err in result.error_details:
                print(f"  * {err}")
        return 0 if result.success else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
