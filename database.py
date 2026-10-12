"""
Database module for Electricity Anomaly Detector.
Integrates SQLite to persist meter readings, sensor measurements,
and anomaly detection results safely without requiring external servers.
"""

import os
import sqlite3
import csv
from datetime import datetime

DEFAULT_DB_PATH = "electricity_anomaly_detector.db"
CSV_READINGS_FILE = "meter_readings.csv"


def get_connection(db_path=DEFAULT_DB_PATH):
    """
    Safely establish and return a SQLite connection.
    Enables foreign keys and returns rows accessible by column name.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=DEFAULT_DB_PATH, migrate_from_csv=True):
    """
    Initialize SQLite database and tables if they do not exist.
    If database and tables already exist, they are preserved and reused.
    Optionally imports historical readings from meter_readings.csv if table is empty.
    """
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()

            # Table 1: meter_readings
            # Stores meter readings, timestamps, sensor measurements, and anomaly results
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meter_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    household_id TEXT NOT NULL,
                    month TEXT NOT NULL,
                    meter_reading_kwh REAL NOT NULL,
                    bill_amount REAL NOT NULL,
                    appliance TEXT NOT NULL,
                    usage_hours_per_day REAL NOT NULL,
                    is_anomaly INTEGER DEFAULT 0,
                    anomaly_type TEXT DEFAULT 'Normal',
                    anomaly_score REAL DEFAULT 0.0,
                    source TEXT DEFAULT 'Manual/Tinkercad',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(timestamp, household_id, month, appliance)
                );
            """)

            # Table 2: daily_anomalies
            # Stores batch anomaly detection outputs from the detector engine
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_anomalies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    household_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    energy_sum REAL NOT NULL,
                    anomaly_type TEXT NOT NULL,
                    mean_consumption REAL,
                    std_consumption REAL,
                    detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(household_id, date)
                );
            """)

            # Create indices for fast lookup
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_meter_household
                ON meter_readings (household_id);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_daily_household_date
                ON daily_anomalies (household_id, date);
            """)

            conn.commit()

            # Migrate existing meter_readings.csv records if table is brand new or empty
            if migrate_from_csv and os.path.exists(CSV_READINGS_FILE):
                cursor.execute("SELECT COUNT(*) FROM meter_readings;")
                count = cursor.fetchone()[0]
                if count == 0:
                    _migrate_from_csv(conn, CSV_READINGS_FILE)

    except sqlite3.Error as e:
        print(f"[Database Error] Could not initialize database: {e}")
        raise


def _migrate_from_csv(conn, csv_path):
    """Helper to migrate existing rows from meter_readings.csv safely into SQLite."""
    try:
        with open(csv_path, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            cursor = conn.cursor()
            inserted = 0
            for row in reader:
                ts = row.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                hh = row.get("household_id", "").strip()
                month = row.get("month", "").strip()
                try:
                    kwh = float(row.get("meter_reading_kwh", 0))
                    bill = float(row.get("bill_amount", 0))
                    hours = float(row.get("usage_hours_per_day", 0))
                except (ValueError, TypeError):
                    continue

                appliance = row.get("appliance", "Unknown").strip()
                if not hh or not month:
                    continue

                cursor.execute("""
                    INSERT OR IGNORE INTO meter_readings (
                        timestamp, household_id, month, meter_reading_kwh,
                        bill_amount, appliance, usage_hours_per_day,
                        is_anomaly, anomaly_type, anomaly_score, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'Normal', 0.0, 'CSV_Import');
                """, (ts, hh, month, kwh, bill, appliance, hours))
                inserted += cursor.rowcount
            conn.commit()
            if inserted > 0:
                print(f"[Database] Migrated {inserted} historical readings from {csv_path} to SQLite.")
    except Exception as e:
        print(f"[Database Warning] Could not migrate CSV data: {e}")


def evaluate_reading_anomaly(household_id, reading_kwh, df=None, k=2):
    """
    Evaluate whether a given meter reading (kWh) is anomalous for the given household.
    Uses dataset baseline if df is provided; otherwise returns default Normal.
    
    Returns a dict with:
        is_anomaly (int): 0 or 1
        anomaly_type (str): 'Normal', 'High Consumption', or 'Low Consumption'
        anomaly_score (float): absolute deviation z-score
        mean (float or None)
        std (float or None)
    """
    if df is not None and not df.empty and "LCLid" in df.columns:
        hh_data = df[df["LCLid"] == household_id]
        if not hh_data.empty:
            # Use total monthly consumption baseline or scaled daily baseline
            if "energy_sum" in hh_data.columns:
                daily_mean = hh_data["energy_sum"].mean()
                daily_std = hh_data["energy_sum"].std()

                # Scale daily baseline to ~30-day monthly consumption
                mean_monthly = daily_mean * 30.0
                std_monthly = (daily_std if daily_std > 0 else (daily_mean * 0.2)) * (30.0 ** 0.5)

                upper_bound = mean_monthly + (k * std_monthly)
                lower_bound = max(0.0, mean_monthly - (k * std_monthly))

                score = abs(reading_kwh - mean_monthly) / std_monthly if std_monthly > 0 else 0.0

                if reading_kwh > upper_bound:
                    return {
                        "is_anomaly": 1,
                        "anomaly_type": "High Consumption",
                        "anomaly_score": round(score, 2),
                        "mean": round(mean_monthly, 2),
                        "std": round(std_monthly, 2)
                    }
                elif reading_kwh < lower_bound:
                    return {
                        "is_anomaly": 1,
                        "anomaly_type": "Low Consumption",
                        "anomaly_score": round(score, 2),
                        "mean": round(mean_monthly, 2),
                        "std": round(std_monthly, 2)
                    }
                else:
                    return {
                        "is_anomaly": 0,
                        "anomaly_type": "Normal",
                        "anomaly_score": round(score, 2),
                        "mean": round(mean_monthly, 2),
                        "std": round(std_monthly, 2)
                    }

    return {
        "is_anomaly": 0,
        "anomaly_type": "Normal",
        "anomaly_score": 0.0,
        "mean": None,
        "std": None
    }


def save_meter_reading(
    household_id, month, meter_reading_kwh, bill_amount, appliance,
    usage_hours_per_day, timestamp=None, is_anomaly=0, anomaly_type="Normal",
    anomaly_score=0.0, source="Manual/Tinkercad", db_path=DEFAULT_DB_PATH
):
    """
    Save a single meter reading with sensor measurements and anomaly status into the database.
    Handles duplicate prevention and type safety.
    """
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Safe type coercions and validation
    try:
        household_id = str(household_id).strip()
        month = str(month).strip()
        meter_reading_kwh = float(meter_reading_kwh)
        bill_amount = float(bill_amount)
        appliance = str(appliance).strip()
        usage_hours_per_day = float(usage_hours_per_day)
        is_anomaly = int(bool(is_anomaly))
        anomaly_type = str(anomaly_type).strip()
        anomaly_score = float(anomaly_score)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid reading data types: {e}")

    if not household_id or not month or not appliance:
        raise ValueError("Household ID, month, and appliance cannot be empty.")

    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO meter_readings (
                    timestamp, household_id, month, meter_reading_kwh,
                    bill_amount, appliance, usage_hours_per_day,
                    is_anomaly, anomaly_type, anomaly_score, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                timestamp, household_id, month, meter_reading_kwh,
                bill_amount, appliance, usage_hours_per_day,
                is_anomaly, anomaly_type, anomaly_score, source
            ))
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"[Database Error] Failed to save reading: {e}")
        raise


def get_meter_readings(household_id=None, db_path=DEFAULT_DB_PATH):
    """
    Retrieve meter readings from the database.
    Optionally filters by household_id. Returns list of dicts.
    """
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            if household_id:
                cursor.execute("""
                    SELECT id, timestamp, household_id, month, meter_reading_kwh,
                           bill_amount, appliance, usage_hours_per_day,
                           is_anomaly, anomaly_type, anomaly_score, source, created_at
                    FROM meter_readings
                    WHERE household_id = ?
                    ORDER BY id DESC;
                """, (household_id,))
            else:
                cursor.execute("""
                    SELECT id, timestamp, household_id, month, meter_reading_kwh,
                           bill_amount, appliance, usage_hours_per_day,
                           is_anomaly, anomaly_type, anomaly_score, source, created_at
                    FROM meter_readings
                    ORDER BY id DESC;
                """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"[Database Error] Failed to retrieve readings: {e}")
        return []


def clear_meter_readings(db_path=DEFAULT_DB_PATH):
    """Safely clear all records from meter_readings table."""
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM meter_readings;")
            conn.commit()
            return True
    except sqlite3.Error as e:
        print(f"[Database Error] Failed to clear readings: {e}")
        raise


def save_daily_anomalies(anomaly_df, household_id=None, stats=None, db_path=DEFAULT_DB_PATH):
    """
    Batch persist detected anomalous days from detect_anomalies() into daily_anomalies table.
    """
    if anomaly_df is None or anomaly_df.empty:
        return 0

    mean_val = stats.get("mean_consumption") if isinstance(stats, dict) else (
        stats["mean_consumption"] if hasattr(stats, "__getitem__") and "mean_consumption" in stats else None
    )
    std_val = stats.get("std_consumption") if isinstance(stats, dict) else (
        stats["std_consumption"] if hasattr(stats, "__getitem__") and "std_consumption" in stats else None
    )

    inserted_count = 0
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            for _, row in anomaly_df.iterrows():
                hh = str(row.get("LCLid", household_id or "")).strip()
                day_val = str(row.get("day", ""))
                if hasattr(row.get("day"), "strftime"):
                    day_val = row["day"].strftime("%Y-%m-%d")
                elif " " in day_val:
                    day_val = day_val.split(" ")[0]

                energy = float(row.get("energy_sum", 0.0))
                anom_type = str(row.get("anomaly_type", "Anomaly"))

                cursor.execute("""
                    INSERT OR IGNORE INTO daily_anomalies (
                        household_id, date, energy_sum, anomaly_type,
                        mean_consumption, std_consumption
                    ) VALUES (?, ?, ?, ?, ?, ?);
                """, (hh, day_val, energy, anom_type, mean_val, std_val))
                inserted_count += cursor.rowcount
            conn.commit()
            return inserted_count
    except sqlite3.Error as e:
        print(f"[Database Error] Failed to save daily anomalies: {e}")
        return 0


def get_daily_anomalies(household_id=None, db_path=DEFAULT_DB_PATH):
    """Retrieve saved daily anomalies from the database."""
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            if household_id:
                cursor.execute("""
                    SELECT id, household_id, date, energy_sum, anomaly_type,
                           mean_consumption, std_consumption, detected_at
                    FROM daily_anomalies
                    WHERE household_id = ?
                    ORDER BY date DESC;
                """, (household_id,))
            else:
                cursor.execute("""
                    SELECT id, household_id, date, energy_sum, anomaly_type,
                           mean_consumption, std_consumption, detected_at
                    FROM daily_anomalies
                    ORDER BY date DESC;
                """)
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"[Database Error] Failed to retrieve daily anomalies: {e}")
        return []
