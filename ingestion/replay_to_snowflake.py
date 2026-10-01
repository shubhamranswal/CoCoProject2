"""Replay the 1-minute sensor sample into Snowflake to simulate a live stream (demo helper / simulation).

Usage:
  python -m ingestion.replay_to_snowflake <sensor_reading_file> --speedup 60
"""

import os
import time
import argparse
import pandas as pd
from typing import Optional

try:
    import snowflake.connector
    from snowflake.connector.pandas_tools import write_pandas
    HAVE_SNOWFLAKE = True
except ImportError:
    HAVE_SNOWFLAKE = False

from config import get_settings


def replay_stream(file_path: str, speedup: float = 60.0, start_ts: Optional[str] = None) -> None:
    if not HAVE_SNOWFLAKE:
        raise RuntimeError("snowflake-connector-python is not installed or available.")

    settings = get_settings()
    sf = settings.snowflake

    conn = snowflake.connector.connect(
        account=sf.account,
        user=sf.user,
        password=sf.password.get_secret_value() if hasattr(sf.password, "get_secret_value") else str(sf.password),
        warehouse=sf.warehouse,
        database=sf.database or "COCO_FACTORY",
        schema=sf.schema_name or "CORE",
    )

    df = pd.read_csv(file_path)
    df.columns = [c.upper() for c in df.columns]
    if start_ts and "TS" in df.columns:
        df = df[df.TS >= start_ts]

    for ts, batch in df.groupby("TS", sort=True):
        write_pandas(conn, batch, "SENSOR_READING", quote_identifiers=False)
        print(f"Sent {ts}: {len(batch)} readings", flush=True)
        time.sleep(60.0 / speedup)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay sensor stream to Snowflake")
    parser.add_argument("file", help="Path to sensor_reading CSV or CSV.GZ file")
    parser.add_argument("--speedup", type=float, default=60.0, help="Replay speed multiplier")
    parser.add_argument("--start", default=None, help="Start timestamp filter")
    args = parser.parse_args()

    replay_stream(args.file, speedup=args.speedup, start_ts=args.start)
