# ⚡ Electricity Bill Anomaly Detector

An end-to-end intelligent electricity consumption monitoring and anomaly detection system. This project analyzes smart meter energy records to detect abnormal consumption patterns—such as unexpected spikes, excessive appliance loads, meter faults, or sudden drops—using statistical thresholding ($k$-sigma), IQR outlier analysis, and z-score deviation scoring.

The system features a **desktop GUI (Tkinter + Matplotlib)**, a local **SQLite database**, automated **data cleaning and preprocessing pipelines**, and comprehensive **visualizations**.

---

## 📌 Table of Contents

- [Overview](#-overview)
- [System Architecture](#-system-architecture)
- [Key Features](#-key-features)
- [Statistical & Detection Methodology](#-statistical--detection-methodology)
- [Database Schema](#-database-schema)
- [Repository Structure](#-repository-structure)
- [Visualizations & Plots](#-visualizations--plots)
- [Installation & Setup](#-installation--setup)
- [How to Run](#-how-to-run)
  - [1. Running Database Verification](#1-running-database-verification)
  - [2. Running the Core Detector Engine](#2-running-the-core-detector-engine)
  - [3. Launching the Desktop GUI](#3-launching-the-desktop-gui)
- [GUI Walkthrough & Credentials](#-gui-walkthrough--credentials)
- [Supplementary Assets](#-supplementary-assets)
- [License](#-license)

---

## 🔍 Overview

Electricity consumers and utility providers frequently face challenges with erroneous billing, undetected appliance malfunctions, power leakage, and sudden consumption surges. 

This repository provides a self-contained data analysis and desktop management application that:
1. **Cleans and standardizes smart meter time series data** (handling missing values, invalid dates, duplicates, and outliers).
2. **Computes per-household consumption baselines** ($\mu$, $\sigma$, min, max).
3. **Flags daily and monthly consumption anomalies** using $k$-sigma bounds and anomaly scoring.
4. **Persists records safely in SQLite** with duplicate prevention.
5. **Provides a graphical user interface** with interactive KPI dashboards, manual meter reading loggers, historical tables, household analysis filters, and dynamic visualization charts.

---

## 🏗️ System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        Data Source Layer                               │
│  - daily_dataset.csv (Smart meter records: LCLid, day, energy metrics) │
│  - meter_readings.csv (Logged monthly readings & appliance usage)      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Core Processing Engine                               │
│                   (electricity_anomaly_detector.py)                    │
│  - Data Cleaning & Imputation (Median / Mode)                          │
│  - Outlier Detection (IQR Method)                                      │
│  - Baseline Statistics (Mean, Std Dev, Min, Max, Count)                │
│  - k-Sigma Anomaly Bounds [μ - k·σ, μ + k·σ]                           │
│  - Aggregations (Weekly & Monthly Resampling)                          │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │                                │
                    ▼                                ▼
┌──────────────────────────────────────┐   ┌─────────────────────────────┐
│          Storage Layer               │   │      Presentation Layer     │
│          (database.py)               │   │           (gui.py)          │
│  - SQLite: electricity_anomaly_      │   │  - Tkinter Desktop App      │
│    detector.db                       │   │  - Authentication System    │
│  - Tables:                           │   │  - Overview KPI Dashboard   │
│    * meter_readings                  │   │  - Meter Reading Logger     │
│    * daily_anomalies                 │   │  - Reading History Table    │
│  - Duplicate Prevention Constraints  │   │  - Household Analyzer       │
│  - Automated CSV Migration           │   │  - Embedded Matplotlib Viz  │
└──────────────────────────────────────┘   └─────────────────────────────┘
```

---

## ✨ Key Features

- **Statistical Anomaly Detection Engine**:
  - $k$-sigma thresholding ($k=2$ by default) to identify consumption above and below expected variance.
  - Z-score deviation scoring ($\frac{|x - \mu|}{\sigma}$) to rank the severity of anomalies.
  - Per-household baselines that account for individual consumer consumption habits.

- **Automated Data Cleaning Pipeline**:
  - Handles missing numeric values via median imputation and categorical values via mode imputation.
  - Formats and cleans dates (`YYYY-MM-DD`).
  - Filters exact row duplicates and `[LCLid, day]` duplicate pairs.
  - Generates `processed_daily_dataset.csv`.

- **Interactive Desktop GUI (`gui.py`)**:
  - **Login Authentication**: Secure login system with role validation.
  - **Overview Dashboard**: Displays total records, unique households, date range coverage, and total anomalies detected.
  - **Meter Reading Entry**: Form for logging monthly readings, bill amounts (₹), appliances, and daily hours of usage. Real-time baseline anomaly checking flags spikes immediately upon entry.
  - **Reading History**: Paginated Treeview table of stored readings with instant refresh and database clear options.
  - **Household Analysis**: Granular inspection per household ID (`LCLid`) with custom date-range selection and tabular anomaly breakdown.
  - **Visualizations Tab**: Interactive viewer for 8 distinct Matplotlib/Seaborn analytical plots.

- **Zero-Setup Embedded SQLite Storage (`database.py`)**:
  - Automatically initializes `electricity_anomaly_detector.db` on startup.
  - Seamless fallback and migration from legacy `meter_readings.csv`.
  - Enforces `UNIQUE` constraints and indexing for fast query performance and duplicate prevention.

---

## 📐 Statistical & Detection Methodology

### 1. Data Cleaning & IQR Filtering
- **Interquartile Range (IQR)**:
  $$\text{IQR} = Q_3 - Q_1$$
  $$\text{Lower Outlier Bound} = Q_1 - 1.5 \times \text{IQR}, \quad \text{Upper Outlier Bound} = Q_3 + 1.5 \times \text{IQR}$$

### 2. Household Baseline Metrics
For each household $h$, the engine computes:
- Mean daily consumption: $\mu_h = \frac{1}{N} \sum_{i=1}^{N} x_i$
- Standard deviation: $\sigma_h = \sqrt{\frac{1}{N-1} \sum_{i=1}^{N} (x_i - \mu_h)^2}$

### 3. $k$-Sigma Anomaly Boundaries
Anomalies are detected by establishing statistical confidence bands:
$$\text{Lower Bound} = \max(0, \, \mu_h - k \cdot \sigma_h)$$
$$\text{Upper Bound} = \mu_h + k \cdot \sigma_h$$

- **High Consumption Anomaly**: $x_i > \text{Upper Bound}$ (Potential leakage, heavy load, faulty meter)
- **Low Consumption Anomaly**: $x_i < \text{Lower Bound}$ (Meter disconnection, power outage, unoccupied premise)
- **Normal**: $\text{Lower Bound} \le x_i \le \text{Upper Bound}$

### 4. Anomaly Severity Score
$$\text{Score} = \begin{cases} \dfrac{|x_i - \mu_h|}{\sigma_h}, & \text{if } \sigma_h > 0 \\ 0, & \text{otherwise} \end{cases}$$

### 5. Monthly Reading Evaluation (Logger Mode)
When logging single-month manual meter readings, daily baselines are scaled to an equivalent 30-day billing cycle:
$$\mu_{\text{monthly}} = 30 \times \mu_h$$
$$\sigma_{\text{monthly}} = \sigma_h \times \sqrt{30}$$

---

## 🗄️ Database Schema

The application uses an embedded SQLite database (`electricity_anomaly_detector.db`):

### Table: `meter_readings`
| Column | Type | Constraints / Description |
|---|---|---|
| `id` | `INTEGER` | Primary Key, Autoincrement |
| `timestamp` | `TEXT` | Record creation timestamp (`YYYY-MM-DD HH:MM:SS`) |
| `household_id`| `TEXT` | Household identifier (e.g., `MAC000131`) |
| `month` | `TEXT` | Billing month (`YYYY-MM`) |
| `meter_reading_kwh` | `REAL` | Total consumption reading in kWh |
| `bill_amount` | `REAL` | Total bill amount in ₹ |
| `appliance` | `TEXT` | Monitored appliance name |
| `usage_hours_per_day` | `REAL` | Operating hours per day ($0 - 24$) |
| `is_anomaly` | `INTEGER` | `1` if anomalous, `0` if normal |
| `anomaly_type` | `TEXT` | `'Normal'`, `'High Consumption'`, or `'Low Consumption'` |
| `anomaly_score`| `REAL` | Z-score absolute deviation |
| `source` | `TEXT` | Source flag (`'Manual/Tinkercad'`, `'CSV_Import'`) |
| `created_at` | `TEXT` | Default `CURRENT_TIMESTAMP` |
| *Constraints* | — | `UNIQUE(timestamp, household_id, month, appliance)` |

### Table: `daily_anomalies`
| Column | Type | Constraints / Description |
|---|---|---|
| `id` | `INTEGER` | Primary Key, Autoincrement |
| `household_id`| `TEXT` | Household identifier (`LCLid`) |
| `date` | `TEXT` | Date of anomaly (`YYYY-MM-DD`) |
| `energy_sum` | `REAL` | Daily energy consumption sum in kWh |
| `anomaly_type` | `TEXT` | `'High Consumption'` or `'Low Consumption'` |
| `mean_consumption` | `REAL` | Household baseline mean |
| `std_consumption` | `REAL` | Household baseline standard deviation |
| `detected_at` | `TEXT` | Default `CURRENT_TIMESTAMP` |
| *Constraints* | — | `UNIQUE(household_id, date)` |

---

## 📁 Repository Structure

```text
ELECTRICITY-BILL-ANOMALY-DETECTOR/
├── .gitignore                                 # Git ignore file (cache, virtualenvs)
├── requirements.txt                           # Python project dependencies
├── README.md                                  # Comprehensive documentation
│
├── electricity_anomaly_detector.py            # Core analytics, cleaning & anomaly detection module
├── database.py                                # SQLite storage, migrations & query interface
├── gui.py                                     # Tkinter desktop user interface with embedded charts
├── verify_database.py                         # Test suite verifying schema, inserts, & detection
│
├── daily_dataset.csv                          # Primary smart meter energy dataset
├── processed_daily_dataset.csv                # Cleaned and imputed dataset output
├── meter_readings.csv                         # Historical logged readings & appliance measurements
├── electricity_anomaly_detector.db            # SQLite database file
│
├── plots/                                     # Saved visual charts (PNG, 150 DPI)
│   ├── anomalies_scatter_plot.png
│   ├── average_consumption_by_day_of_week.png
│   ├── average_daily_consumption_trend.png
│   ├── correlation_heatmap.png
│   ├── energy_consumption_distribution.png
│   ├── monthly_consumption_distribution.png
│   ├── top_10_households_by_anomaly_rate.png
│   └── weekly_consumption_trend.png
│
├── Electricity_Anomaly_Detector_Dashboard (2).xlsx # Excel analytical dashboard
└── electricity_anomaly_detector.pptx          # Project presentation slide deck
```

---

## 📊 Visualizations & Plots

The analytics module exports high-resolution visual plots to the `plots/` folder and renders them directly inside the GUI:

1. **Energy Consumption Distribution** (`energy_consumption_distribution.png`): Histogram with KDE showing overall distribution of daily energy usage.
2. **Average Daily Consumption Trend** (`average_daily_consumption_trend.png`): Longitudinal time-series tracking daily mean consumption across all households.
3. **Monthly Consumption Distribution** (`monthly_consumption_distribution.png`): Boxplots detailing seasonal shifts and month-by-month consumption variability.
4. **Correlation Heatmap** (`correlation_heatmap.png`): Matrix highlighting Pearson correlation between metrics (`energy_mean`, `energy_median`, `energy_std`, `energy_sum`, etc.).
5. **Top 10 Households by Anomaly Rate** (`top_10_households_by_anomaly_rate.png`): Ranking of households with the highest percentage of anomalous days.
6. **Average Consumption by Day of Week** (`average_consumption_by_day_of_week.png`): Bar plot identifying weekday vs. weekend consumption peaks.
7. **Weekly Consumption Trend** (`weekly_consumption_trend.png`): Resampled weekly aggregate consumption trend.
8. **Anomalies Scatter Plot** (`anomalies_scatter_plot.png`): Multi-colored scatter plot mapping daily energy vs. household mean, with anomalies highlighted.

---

## 💻 Installation & Setup

### Prerequisites
- **Python**: Version 3.8 or higher
- **Git**: Installed and available in your environment

### 1. Clone the Repository
```bash
git clone https://github.com/aarchitajha/ELECTRICITY-BILL-ANOMALY-DETECTOR.git
cd ELECTRICITY-BILL-ANOMALY-DETECTOR
```

### 2. Create and Activate a Virtual Environment (Optional but Recommended)
**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🚀 How to Run

### 1. Running Database Verification
Run the verification script to test SQLite initialization, data insertion, duplicate handling, and anomaly scoring:
```bash
python verify_database.py
```
*Expected output: All 7 verification checks passing with `[OK]` status.*

### 2. Running the Core Detector Engine
Run the core detector script to clean raw data, generate statistical summaries, and export all 8 visualization charts to `plots/`:
```bash
python electricity_anomaly_detector.py
```

### 3. Launching the Desktop GUI
To launch the interactive Tkinter application:
```bash
python gui.py
```

---

## 🖥️ GUI Walkthrough & Credentials

### Default Login Credentials
- **Username**: `admin`
- **Password**: `admin123`

### Application Navigation Tabs:
1. **Dashboard Tab**: Displays overview metrics (Total Records, Unique Households, Date Coverage, Anomaly Counts).
2. **Meter Readings Tab**: Input form to record household readings, billing values, appliances, and daily hours. Flags anomalies in real time.
3. **History Tab**: Displays all saved meter readings stored in the database.
4. **Household Analysis Tab**: Select any household (`LCLid`) and specify start/end dates to inspect consumption statistics and view anomalous days.
5. **Visualizations Tab**: Choose any of the 8 charts from the dropdown to render interactive plots on demand.

---

## 📦 Supplementary Assets

- **Presentation Deck**: [electricity_anomaly_detector.pptx](electricity_anomaly_detector.pptx) — Comprehensive presentation summarizing project problem statement, methodology, architecture, and findings.
- **Spreadsheet Dashboard**: [Electricity_Anomaly_Detector_Dashboard (2).xlsx](Electricity_Anomaly_Detector_Dashboard%20(2).xlsx) — Interactive Excel workbook for tabular reporting and supplementary pivot analyses.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE) .
