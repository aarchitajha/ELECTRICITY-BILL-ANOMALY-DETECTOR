import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_style("whitegrid")
plt.rcParams["figure.figsize"] = (10, 6)

DEFAULT_CSV_PATH = "daily_dataset.csv"
DEFAULT_PLOT_DIR = "plots"

def load_and_clean_data(csv_path=DEFAULT_CSV_PATH, save_path=None, verbose=True):
    

    def log(*args):
        if verbose:
            print(*args)

    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            raise ValueError("The dataset is empty.")
    except FileNotFoundError:
        raise FileNotFoundError(f"Could not find file: {csv_path}")
    except pd.errors.EmptyDataError:
        raise pd.errors.EmptyDataError("The CSV file is empty.")
    except pd.errors.ParserError:
        raise pd.errors.ParserError("The CSV contains corrupt or improperly formatted rows.")

    log("Dataset loaded successfully!")
    log("Shape:", df.shape)
    log(df.head())
    log("\nColumn names:")
    log(df.columns.tolist())
    log("\nData types:")
    log(df.dtypes)

    missing_data = pd.DataFrame({
        "Missing Values": df.isnull().sum(),
        "Percentage Missing": (df.isnull().sum() / len(df)) * 100
    })
    missing_data = missing_data[missing_data["Missing Values"] > 0]
    log(missing_data.sort_values(by="Percentage Missing", ascending=False))

    log("Exact duplicate rows:", df.duplicated().sum())

    if "LCLid" in df.columns and "day" in df.columns:
        log("Duplicate LCLid + day records:",
            df.duplicated(subset=["LCLid", "day"]).sum())

    df = df.drop_duplicates()
    log("Duplicates after cleaning:", df.duplicated().sum())

    if "day" in df.columns:
        df["day"] = pd.to_datetime(df["day"], errors="coerce")
        log("Invalid dates:", df["day"].isnull().sum())
        df = df.dropna(subset=["day"])

    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    for col in numeric_cols:
        if df[col].isnull().sum() > 0:
            median_value = df[col].median()
            df[col] = df[col].fillna(median_value)
            log(f"Missing values in '{col}' filled using median: {median_value}")

    categorical_cols = df.select_dtypes(include="object").columns.tolist()
    for col in categorical_cols:
        if df[col].isnull().sum() > 0:
            mode_value = df[col].mode()
            if not mode_value.empty:
                df[col] = df[col].fillna(mode_value[0])
                log(f"Missing values in '{col}' filled using mode: {mode_value[0]}")
            else:
                df[col] = df[col].fillna("Unknown")

    log(df[numeric_cols].describe())

    for col in numeric_cols:
        negative_count = (df[col] < 0).sum()
        if negative_count > 0:
            log(f"{col}: {negative_count} negative values")

    Q1 = df[numeric_cols].quantile(0.25)
    Q3 = df[numeric_cols].quantile(0.75)
    IQR = Q3 - Q1
    outlier_counts = (
        ((df[numeric_cols] < (Q1 - 1.5 * IQR)) | (df[numeric_cols] > (Q3 + 1.5 * IQR)))
    ).sum()
    log(outlier_counts)

    log("Final Dataset Shape:", df.shape)

    if save_path:
        if df.empty:
            raise ValueError("Cannot save an empty dataset.")
        df.to_csv(save_path, index=False)
        log(f"Processed dataset saved to {save_path}")

    return df

def filter_household(df, LCLid):
    if "LCLid" not in df.columns:
        raise ValueError("LCLid column not found.")

    filtered_df = df[df["LCLid"] == LCLid].copy()
    return filtered_df


def prepare_data(df):
    required = {"LCLid", "day", "energy_sum"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    data = df.copy()
    data["day"] = pd.to_datetime(data["day"], errors="coerce")
    data["energy_sum"] = pd.to_numeric(data["energy_sum"], errors="coerce")
    data = data.dropna(subset=["LCLid", "day", "energy_sum"])
    data = data.sort_values(["LCLid", "day"]).reset_index(drop=True)

    return data


def calculate_stats(df):
    data = prepare_data(df)

    stats = (
        data.groupby("LCLid")["energy_sum"]
        .agg(
            mean_consumption="mean",
            std_consumption="std",
            min_consumption="min",
            max_consumption="max",
            total_consumption="sum",
            number_of_days="count"
        )
        .reset_index()
    )

    stats["std_consumption"] = stats["std_consumption"].fillna(0)

    return stats


def calculate_anomaly_thresholds(df, k=2):
    if k < 0:
        raise ValueError("k must be non-negative")

    stats = calculate_stats(df)

    stats["lower_bound"] = np.maximum(0, stats["mean_consumption"] - k * stats["std_consumption"])
    stats["upper_bound"] = stats["mean_consumption"] + k * stats["std_consumption"]

    return stats[["LCLid", "mean_consumption", "std_consumption", "lower_bound", "upper_bound"]]


def detect_anomalies(df, k=2):
    data = prepare_data(df)
    thresholds = calculate_anomaly_thresholds(data, k=k)

    result = data.merge(thresholds, on="LCLid", how="left")

    result["anomaly"] = (
        (result["energy_sum"] > result["upper_bound"])
        | (result["energy_sum"] < result["lower_bound"])
    )

    result["anomaly_type"] = np.select(
        [result["energy_sum"] > result["upper_bound"],
         result["energy_sum"] < result["lower_bound"]],
        ["High Consumption", "Low Consumption"],
        default="Normal"
    )

    return result


def weekly_summary(df):
    data = prepare_data(df)

    result = (
        data.set_index("day")
        .groupby("LCLid")["energy_sum"]
        .resample("W")
        .sum()
        .reset_index(name="weekly_consumption")
    )

    return result


def monthly_summary(df):
    data = prepare_data(df)

    result = (
        data.set_index("day")
        .groupby("LCLid")["energy_sum"]
        .resample("ME")
        .sum()
        .reset_index(name="monthly_consumption")
    )

    return result


def monthly_household_summary(df):
    data = prepare_data(df)
    data["month"] = data["day"].dt.to_period("M").astype(str)

    result = (
        data.groupby(["LCLid", "month"])["energy_sum"]
        .agg(
            total_consumption="sum",
            mean_consumption="mean",
            std_consumption="std",
            min_consumption="min",
            max_consumption="max"
        )
        .reset_index()
    )

    result["std_consumption"] = result["std_consumption"].fillna(0)

    return result


def top_anomalies(df, k=2, n=10):
    if n <= 0:
        raise ValueError("n must be greater than 0")

    result = detect_anomalies(df, k=k)

    result["anomaly_score"] = np.where(
        result["std_consumption"] > 0,
        np.abs(result["energy_sum"] - result["mean_consumption"]) / result["std_consumption"],
        0
    )

    return (
        result[result["anomaly"]]
        .sort_values("anomaly_score", ascending=False)
        .head(n)
        .reset_index(drop=True)
    )


def household_anomaly_summary(df, k=2):
    result = detect_anomalies(df, k=k)

    summary = (
        result.groupby("LCLid")
        .agg(
            total_days=("day", "count"),
            anomaly_days=("anomaly", "sum"),
            mean_consumption=("energy_sum", "mean"),
            std_consumption=("energy_sum", "std")
        )
        .reset_index()
    )

    summary["std_consumption"] = summary["std_consumption"].fillna(0)

    summary["anomaly_rate_percent"] = np.where(
        summary["total_days"] > 0,
        (summary["anomaly_days"] / summary["total_days"]) * 100,
        0
    )

    return summary.sort_values("anomaly_days", ascending=False).reset_index(drop=True)


def filter_date_range(df, start_date=None, end_date=None):
    if start_date is not None and end_date is not None:
        if pd.to_datetime(start_date) > pd.to_datetime(end_date):
            raise ValueError("start_date cannot be after end_date")

    data = prepare_data(df)

    if start_date is not None:
        data = data[data["day"] >= pd.to_datetime(start_date)]

    if end_date is not None:
        data = data[data["day"] <= pd.to_datetime(end_date)]

    return data.reset_index(drop=True)




def plot_energy_distribution(df, ax=None):
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(10, 6))

    sns.histplot(df["energy_sum"], bins=50, kde=True, color="steelblue", ax=ax)
    ax.set_title("Distribution of Daily Total Energy Consumption")
    ax.set_xlabel("Energy Sum (kWh)")
    ax.set_ylabel("Frequency")

    if standalone:
        fig.tight_layout()
        return fig
    return None


def plot_daily_trend(df, ax=None):
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(14, 6))

    daily_trend = df.groupby("day")["energy_sum"].mean().reset_index()
    ax.plot(daily_trend["day"], daily_trend["energy_sum"], color="darkorange", linewidth=1)
    ax.set_title("Average Daily Energy Consumption Over Time (All Households)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Average Energy Sum (kWh)")

    if standalone:
        fig.tight_layout()
        return fig
    return None


MONTH_ORDER = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

DOW_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def plot_monthly_distribution(df, ax=None):
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(14, 6))

    data = df.copy()
    data["month"] = data["day"].dt.month_name()

    sns.boxplot(
        data=data, x="month", y="energy_sum",
        order=MONTH_ORDER, showfliers=False,
        hue="month", palette="coolwarm", legend=False, ax=ax
    )
    ax.set_title("Monthly Distribution of Daily Energy Consumption")
    ax.set_xlabel("Month")
    ax.set_ylabel("Energy Sum (kWh)")
    ax.tick_params(axis="x", rotation=45)

    if standalone:
        fig.tight_layout()
        return fig
    return None


def plot_correlation_heatmap(df, ax=None):
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(8, 6))

    numeric_metrics = [
        "energy_median", "energy_mean", "energy_max",
        "energy_count", "energy_std", "energy_sum", "energy_min"
    ]
    available = [c for c in numeric_metrics if c in df.columns]

    corr = df[available].corr()
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="viridis", square=True, ax=ax)
    ax.set_title("Correlation Heatmap of Energy Metrics")

    if standalone:
        fig.tight_layout()
        return fig
    return None


def plot_top_anomaly_households(df, ax=None, k=2):
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(12, 6))

    anomaly_summary = household_anomaly_summary(df, k=k)
    top10 = anomaly_summary.head(10)

    sns.barplot(
        data=top10, x="anomaly_rate_percent", y="LCLid",
        hue="LCLid", palette="rocket", legend=False, ax=ax
    )
    ax.set_title("Top 10 Households by Anomaly Rate (%)")
    ax.set_xlabel("Anomaly Rate (%)")
    ax.set_ylabel("Household (LCLid)")

    if standalone:
        fig.tight_layout()
        return fig
    return None


def plot_day_of_week(df, ax=None):
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(10, 6))

    data = df.copy()
    data["day_of_week"] = data["day"].dt.day_name()

    sns.barplot(
        data=data, x="day_of_week", y="energy_sum",
        order=DOW_ORDER, hue="day_of_week", palette="mako", legend=False,
        errorbar=None, ax=ax
    )
    ax.set_title("Average Energy Consumption by Day of Week")
    ax.set_xlabel("Day of Week")
    ax.set_ylabel("Average Energy Sum (kWh)")

    if standalone:
        fig.tight_layout()
        return fig
    return None


def plot_weekly_trend(df, ax=None):
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(14, 6))

    overall_weekly = (
        df.set_index("day")["energy_sum"]
        .resample("W")
        .sum()
        .reset_index(name="weekly_consumption")
    )

    ax.plot(overall_weekly["day"], overall_weekly["weekly_consumption"],
            color="seagreen", linewidth=1.5)
    ax.set_title("Total Weekly Energy Consumption Trend (All Households)")
    ax.set_xlabel("Week")
    ax.set_ylabel("Total Energy Sum (kWh)")

    if standalone:
        fig.tight_layout()
        return fig
    return None


def plot_anomaly_scatter(df, ax=None, k=2):
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(10, 6))

    anomaly_data = detect_anomalies(df, k=k)
    x_col = "energy_mean" if "energy_mean" in anomaly_data.columns else "mean_consumption"

    sns.scatterplot(
        data=anomaly_data, x=x_col,
        y="energy_sum", hue="anomaly_type",
        palette={"Normal": "steelblue", "High Consumption": "crimson", "Low Consumption": "gold"},
        alpha=0.5, s=20, ax=ax
    )
    ax.set_title("Daily Energy Sum vs Household Mean Consumption (Anomalies Highlighted)")
    ax.set_xlabel("Household Mean Consumption (kWh)")
    ax.set_ylabel("Daily Energy Sum (kWh)")

    if standalone:
        fig.tight_layout()
        return fig
    return None


PLOT_REGISTRY = {
    "Energy Consumption Distribution": plot_energy_distribution,
    "Average Daily Consumption Trend": plot_daily_trend,
    "Monthly Consumption Distribution": plot_monthly_distribution,
    "Correlation Heatmap": plot_correlation_heatmap,
    "Top 10 Households by Anomaly Rate": plot_top_anomaly_households,
    "Average Consumption by Day of Week": plot_day_of_week,
    "Weekly Consumption Trend": plot_weekly_trend,
    "Anomalies Scatter Plot": plot_anomaly_scatter,
}


def load_readings_from_db(household_id=None, db_path="electricity_anomaly_detector.db"):
    """
    Load meter readings and anomaly detection results from the SQLite database into a pandas DataFrame.
    """
    import database
    readings = database.get_meter_readings(household_id=household_id, db_path=db_path)
    if not readings:
        return pd.DataFrame()
    return pd.DataFrame(readings)


def save_anomalies_to_db(anomaly_df, household_id=None, stats=None, db_path="electricity_anomaly_detector.db"):
    """
    Persist detected anomalies into the SQLite database.
    """
    import database
    return database.save_daily_anomalies(anomaly_df, household_id=household_id, stats=stats, db_path=db_path)


def load_anomalies_from_db(household_id=None, db_path="electricity_anomaly_detector.db"):
    """
    Load detected daily anomalies from the SQLite database into a pandas DataFrame.
    """
    import database
    anomalies = database.get_daily_anomalies(household_id=household_id, db_path=db_path)
    if not anomalies:
        return pd.DataFrame()
    return pd.DataFrame(anomalies)


if __name__ == "__main__":
    df = load_and_clean_data(csv_path=DEFAULT_CSV_PATH, save_path="processed_daily_dataset.csv", verbose=True)

    sample_id = df["LCLid"].iloc[0]
    household_data = filter_household(df, sample_id)
    print(f"\nFound {len(household_data)} records for {sample_id}")
    print(household_data.head())

    os.makedirs(DEFAULT_PLOT_DIR, exist_ok=True)

    for name, plot_fn in PLOT_REGISTRY.items():
        fig = plot_fn(df)
        safe_name = name.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("%", "pct")
        out_path = os.path.join(DEFAULT_PLOT_DIR, f"{safe_name}.png")
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        print(f"Saved: {out_path}")

    print(f"\nAll charts saved to '{DEFAULT_PLOT_DIR}/' - no windows were opened.")
