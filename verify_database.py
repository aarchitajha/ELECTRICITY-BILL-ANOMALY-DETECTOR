"""
Verification script for Electricity Anomaly Detector Database Integration.
Validates:
1. Database schema and table creation.
2. Saving electricity readings and sensor measurements.
3. Anomaly detection evaluation on new readings.
4. Duplicate prevention and data integrity.
5. Batch anomaly logging and retrieval.
6. Integration with electricity_anomaly_detector module.
"""

import os
import sqlite3
import pandas as pd
import database
import electricity_anomaly_detector as detector


def run_verification():
    print("=" * 65)
    print("ELECTRICITY ANOMALY DETECTOR - DATABASE VERIFICATION")
    print("=" * 65)

    db_path = database.DEFAULT_DB_PATH
    print(f"\n[Step 1] Initializing database at: {db_path}")
    database.init_db(db_path=db_path)

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file was not created: {db_path}")
    print("[OK] SQLite database file confirmed.")

    # Check tables and columns
    print("\n[Step 2] Inspecting SQLite schema...")
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"[OK] Found tables: {tables}")

        assert "meter_readings" in tables, "Table 'meter_readings' missing!"
        assert "daily_anomalies" in tables, "Table 'daily_anomalies' missing!"

        cursor.execute("PRAGMA table_info(meter_readings);")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"[OK] 'meter_readings' columns: {columns}")

    # Check reading migration & retrieval
    print("\n[Step 3] Checking readings retrieval...")
    readings = database.get_meter_readings(db_path=db_path)
    print(f"[OK] Successfully retrieved {len(readings)} readings from database.")
    if readings:
        print("Sample record from database:")
        sample = dict(readings[0])
        for k, v in sample.items():
            print(f"   {k}: {v}")

    # Test anomaly evaluation and saving
    print("\n[Step 4] Testing anomaly evaluation on simulated Tinkercad reading...")
    # Load sample baseline
    df_sample = pd.DataFrame({
        "LCLid": ["MAC000131"] * 5,
        "day": pd.date_range("2012-01-01", periods=5),
        "energy_sum": [10.0, 11.0, 10.5, 9.5, 10.2]
    })
    
    # Reading within normal range (~300 kWh/month)
    eval_normal = database.evaluate_reading_anomaly("MAC000131", 310.0, df=df_sample, k=2)
    print(f"[OK] Normal test (310 kWh): Anomaly={eval_normal['is_anomaly']}, Type={eval_normal['anomaly_type']}, Score={eval_normal['anomaly_score']}")
    assert eval_normal["is_anomaly"] == 0

    # Reading with anomalous spike (900 kWh/month)
    eval_spike = database.evaluate_reading_anomaly("MAC000131", 900.0, df=df_sample, k=2)
    print(f"[OK] Spike test (900 kWh): Anomaly={eval_spike['is_anomaly']}, Type={eval_spike['anomaly_type']}, Score={eval_spike['anomaly_score']}")
    assert eval_spike["is_anomaly"] == 1
    assert eval_spike["anomaly_type"] == "High Consumption"

    # Save the spike reading to database
    test_ts = "2026-10-10 12:00:00"
    database.save_meter_reading(
        household_id="MAC000131",
        month="2026-10",
        meter_reading_kwh=900.0,
        bill_amount=7500.0,
        appliance="Tinkercad Heavy Load",
        usage_hours_per_day=24.0,
        timestamp=test_ts,
        is_anomaly=eval_spike["is_anomaly"],
        anomaly_type=eval_spike["anomaly_type"],
        anomaly_score=eval_spike["anomaly_score"],
        source="Tinkercad_Simulation",
        db_path=db_path
    )
    print("[OK] Successfully inserted simulated anomalous reading into database.")

    # Test duplicate prevention (Requirement 8)
    print("\n[Step 5] Testing duplicate insertion prevention...")
    count_before = len(database.get_meter_readings(db_path=db_path))
    # Re-insert exact same reading
    database.save_meter_reading(
        household_id="MAC000131",
        month="2026-10",
        meter_reading_kwh=900.0,
        bill_amount=7500.0,
        appliance="Tinkercad Heavy Load",
        usage_hours_per_day=24.0,
        timestamp=test_ts,
        is_anomaly=eval_spike["is_anomaly"],
        anomaly_type=eval_spike["anomaly_type"],
        anomaly_score=eval_spike["anomaly_score"],
        db_path=db_path
    )
    count_after = len(database.get_meter_readings(db_path=db_path))
    assert count_before == count_after, f"Duplicate was not ignored! Before: {count_before}, After: {count_after}"
    print(f"[OK] Duplicate prevented safely (total records remained {count_after}).")

    # Test daily anomalies table
    print("\n[Step 6] Testing batch anomaly persistence to database...")
    test_anomaly_df = pd.DataFrame([{
        "LCLid": "MAC000131",
        "day": "2026-10-09",
        "energy_sum": 45.2,
        "anomaly_type": "High Consumption"
    }])
    stats_dict = {"mean_consumption": 10.2, "std_consumption": 2.1}
    saved_count = database.save_daily_anomalies(test_anomaly_df, household_id="MAC000131", stats=stats_dict, db_path=db_path)
    print(f"[OK] Saved {saved_count} daily anomalies to 'daily_anomalies' table.")

    daily_anoms = database.get_daily_anomalies(household_id="MAC000131", db_path=db_path)
    print(f"[OK] Retrieved {len(daily_anoms)} daily anomaly records for MAC000131.")

    # Test electricity_anomaly_detector module integration
    print("\n[Step 7] Testing electricity_anomaly_detector database loading...")
    df_db_readings = detector.load_readings_from_db(db_path=db_path)
    print(f"[OK] detector.load_readings_from_db() returned DataFrame with shape: {df_db_readings.shape}")
    assert not df_db_readings.empty

    df_db_anoms = detector.load_anomalies_from_db(db_path=db_path)
    print(f"[OK] detector.load_anomalies_from_db() returned DataFrame with shape: {df_db_anoms.shape}")
    assert not df_db_anoms.empty

    print("\n" + "=" * 65)
    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY! [OK]")
    print("=" * 65)


if __name__ == "__main__":
    run_verification()
