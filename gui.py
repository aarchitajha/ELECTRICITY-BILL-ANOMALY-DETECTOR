
import os
import csv
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import electricity_anomaly_detector as detector
import database



COLOR_PRIMARY = "#607456"   
COLOR_BG = "#EEE0CC"        
COLOR_ACCENT = "#9B3E1D"    
COLOR_DANGER = "#7B2525"   
COLOR_CARD = "#FBF6EC"
COLOR_TEXT = "#3A3226"      

FONT_TITLE = ("Segoe UI", 22, "bold")
FONT_SUBTITLE = ("Segoe UI", 11)
FONT_HEADER = ("Segoe UI", 15, "bold")
FONT_LABEL = ("Segoe UI", 10, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_BUTTON = ("Segoe UI", 10, "bold")

DATA_FILE = "daily_dataset.csv"
READINGS_FILE = "meter_readings.csv"
READINGS_COLUMNS = [
    "timestamp", "household_id", "month", "meter_reading_kwh",
    "bill_amount", "appliance", "usage_hours_per_day"
]

CREDENTIALS = {"admin": "admin123"}


def ensure_readings_file():
    if not os.path.exists(READINGS_FILE):
        with open(READINGS_FILE, "w", newline="") as f:
            csv.writer(f).writerow(READINGS_COLUMNS)


def read_readings():
    try:
        db_rows = database.get_meter_readings()
        if db_rows:
            return db_rows
    except Exception:
        pass
    ensure_readings_file()
    with open(READINGS_FILE, newline="") as f:
        return list(csv.DictReader(f))


def style_button(btn, bg=COLOR_PRIMARY, fg="white", hover=COLOR_ACCENT):
    btn.configure(
        bg=bg, fg=fg, activebackground=hover, activeforeground="white",
        font=FONT_BUTTON, relief="flat", bd=0, padx=14, pady=8, cursor="hand2"
    )
    btn.bind("<Enter>", lambda e: btn.configure(bg=hover))
    btn.bind("<Leave>", lambda e: btn.configure(bg=bg))


def labeled_entry(parent, label_text, row, column=0, width=28, show=None):
    tk.Label(parent, text=label_text, font=FONT_LABEL, bg=COLOR_CARD, fg=COLOR_TEXT) \
        .grid(row=row, column=column, sticky="w", padx=10, pady=(10, 2))
    entry = tk.Entry(parent, font=FONT_BODY, width=width, relief="solid", bd=1, show=show)
    entry.grid(row=row + 1, column=column, sticky="we", padx=10, pady=(0, 4))
    return entry


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Energy Anomaly Detector")
        self.geometry("1150x720")
        self.minsize(980, 640)
        self.configure(bg=COLOR_BG)

        self.current_user = None
        self.df = None  # loaded lazily after login

        # Initialize SQLite database
        try:
            database.init_db()
        except Exception as e:
            print(f"[Warning] Database initialization error: {e}")

        self._setup_style()

        self.container = tk.Frame(self, bg=COLOR_BG)
        self.container.pack(fill="both", expand=True)

        self.frames = {}
        for F in (LoginPage, MainPage):
            frame = F(self.container, self)
            self.frames[F] = frame
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.show_frame(LoginPage)

    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        style.configure(
            "TNotebook.Tab", background=COLOR_ACCENT, foreground="white",
            font=FONT_BUTTON, padding=[16, 10], borderwidth=0
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", COLOR_PRIMARY)],
            foreground=[("selected", "white")],
        )

        style.configure(
            "Treeview", background=COLOR_CARD, fieldbackground=COLOR_CARD,
            foreground=COLOR_TEXT, rowheight=26, font=FONT_BODY, borderwidth=0
        )
        style.configure(
            "Treeview.Heading", background=COLOR_PRIMARY, foreground="white",
            font=FONT_BUTTON, relief="flat"
        )
        style.map("Treeview.Heading", background=[("active", COLOR_ACCENT)])

        style.configure("TCombobox", fieldbackground="white", background="white")

    def show_frame(self, page_class):
        frame = self.frames[page_class]
        frame.tkraise()
        if hasattr(frame, "on_show"):
            frame.on_show()

    def load_dataset(self):
        """Load and clean the dataset once, after a successful login."""
        if self.df is not None:
            return self.df
        if not os.path.exists(DATA_FILE):
            raise FileNotFoundError(
                f"Could not find '{DATA_FILE}'. Place it in the same folder as gui.py."
            )
        self.df = detector.load_and_clean_data(csv_path=DATA_FILE, save_path=None, verbose=False)
        return self.df

    def logout(self):
        self.current_user = None
        self.df = None
        login_page = self.frames[LoginPage]
        login_page.reset()
        self.show_frame(LoginPage)


class LoginPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLOR_BG)
        self.controller = controller

        card = tk.Frame(self, bg=COLOR_CARD, padx=50, pady=40)
        card.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(card, text="Energy Anomaly Detector", font=FONT_TITLE,
                 bg=COLOR_CARD, fg=COLOR_PRIMARY).pack(pady=(0, 4))
        tk.Label(card, text="Please sign in to continue", font=FONT_SUBTITLE,
                 bg=COLOR_CARD, fg=COLOR_TEXT).pack(pady=(0, 20))

        tk.Label(card, text="Username", font=FONT_LABEL, bg=COLOR_CARD, fg=COLOR_TEXT) \
            .pack(anchor="w")
        self.username_entry = tk.Entry(card, font=FONT_BODY, width=30, relief="solid", bd=1)
        self.username_entry.pack(pady=(2, 12), ipady=4)

        tk.Label(card, text="Password", font=FONT_LABEL, bg=COLOR_CARD, fg=COLOR_TEXT) \
            .pack(anchor="w")
        self.password_entry = tk.Entry(card, font=FONT_BODY, width=30, relief="solid", bd=1, show="*")
        self.password_entry.pack(pady=(2, 6), ipady=4)
        self.password_entry.bind("<Return>", lambda e: self.attempt_login())

        self.error_label = tk.Label(card, text="", font=FONT_BODY, bg=COLOR_CARD, fg=COLOR_DANGER)
        self.error_label.pack(pady=(4, 10))

        login_btn = tk.Button(card, text="Log In", command=self.attempt_login)
        style_button(login_btn)
        login_btn.pack(fill="x", pady=(6, 0))

        tk.Label(card, text="Demo login:  admin / admin123", font=("Segoe UI", 8),
                 bg=COLOR_CARD, fg=COLOR_ACCENT).pack(pady=(16, 0))

    def attempt_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            self.error_label.config(text="Please enter both username and password.")
            return

        if CREDENTIALS.get(username) != password:
            self.error_label.config(text="Invalid username or password.")
            self.password_entry.delete(0, tk.END)
            return

        self.error_label.config(text="")
        self.controller.current_user = username

        try:
            self.controller.load_dataset()
        except Exception as e:
            messagebox.showerror("Data Load Error", str(e))
            return

        self.controller.show_frame(MainPage)

    def reset(self):
        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)
        self.error_label.config(text="")



class MainPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLOR_BG)
        self.controller = controller

        self._build_topbar()

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self.dashboard_tab = DashboardTab(notebook, controller)
        self.readings_tab = MeterReadingsTab(notebook, controller)
        self.history_tab = HistoryTab(notebook, controller)
        self.analysis_tab = HouseholdAnalysisTab(notebook, controller)
        self.viz_tab = VisualizationsTab(notebook, controller)

        notebook.add(self.dashboard_tab, text="  Dashboard  ")
        notebook.add(self.readings_tab, text="  Meter Readings  ")
        notebook.add(self.history_tab, text="  History  ")
        notebook.add(self.analysis_tab, text="  Household Analysis  ")
        notebook.add(self.viz_tab, text="  Visualizations  ")

        self.notebook = notebook

    def _build_topbar(self):
        bar = tk.Frame(self, bg=COLOR_PRIMARY, height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(bar, text="⚡ Energy Anomaly Detector", font=FONT_HEADER,
                 bg=COLOR_PRIMARY, fg="white").pack(side="left", padx=18)

        self.user_label = tk.Label(bar, text="", font=FONT_BODY, bg=COLOR_PRIMARY, fg="white")
        self.user_label.pack(side="right", padx=(0, 10))

        logout_btn = tk.Button(bar, text="Logout", command=self.controller.logout)
        style_button(logout_btn, bg=COLOR_DANGER, hover="#5c1c1c")
        logout_btn.pack(side="right", padx=12, pady=10)

    def on_show(self):
        self.user_label.config(text=f"Logged in as: {self.controller.current_user}")
        self.dashboard_tab.on_show()
        self.history_tab.on_show()
        self.analysis_tab.on_show()
        self.viz_tab.on_show()


class DashboardTab(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLOR_BG)
        self.controller = controller

        tk.Label(self, text="Overview", font=FONT_HEADER, bg=COLOR_BG, fg=COLOR_PRIMARY) \
            .pack(anchor="w", padx=20, pady=(20, 10))

        self.cards_frame = tk.Frame(self, bg=COLOR_BG)
        self.cards_frame.pack(fill="x", padx=20)

        self.card_widgets = []

    def on_show(self):
        for w in self.cards_frame.winfo_children():
            w.destroy()
        self.card_widgets = []

        df = self.controller.df
        if df is None:
            return

        total_records = len(df)
        total_households = df["LCLid"].nunique()
        date_min = df["day"].min().date()
        date_max = df["day"].max().date()

        try:
            anomalies = detector.detect_anomalies(df, k=2)
            anomaly_count = int(anomalies["anomaly"].sum())
        except Exception:
            anomaly_count = "N/A"

        stats = [
            ("Total Records", f"{total_records:,}"),
            ("Households", f"{total_households:,}"),
            ("Date Range", f"{date_min} → {date_max}"),
            ("Anomalies Detected (k=2)", f"{anomaly_count:,}" if isinstance(anomaly_count, int) else anomaly_count),
        ]

        for i, (title, value) in enumerate(stats):
            card = tk.Frame(self.cards_frame, bg=COLOR_CARD, padx=18, pady=16)
            card.grid(row=0, column=i, padx=8, sticky="nsew")
            self.cards_frame.grid_columnconfigure(i, weight=1)
            tk.Label(card, text=title, font=FONT_LABEL, bg=COLOR_CARD, fg=COLOR_ACCENT).pack(anchor="w")
            tk.Label(card, text=value, font=("Segoe UI", 16, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT).pack(anchor="w", pady=(6, 0))
            self.card_widgets.append(card)

        tk.Label(
            self,
            text="Use the tabs above to log meter readings, review history, "
                 "run per-household analysis, or explore visualizations.",
            font=FONT_BODY, bg=COLOR_BG, fg=COLOR_TEXT, wraplength=900, justify="left"
        ).pack(anchor="w", padx=20, pady=24)


class MeterReadingsTab(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLOR_BG)
        self.controller = controller

        tk.Label(self, text="Enter Monthly Meter Reading & Appliance Usage",
                 font=FONT_HEADER, bg=COLOR_BG, fg=COLOR_PRIMARY).pack(anchor="w", padx=20, pady=(20, 10))

        card = tk.Frame(self, bg=COLOR_CARD, padx=10, pady=10)
        card.pack(padx=20, pady=6, fill="x")
        for c in range(2):
            card.grid_columnconfigure(c, weight=1)

        self.household_entry = labeled_entry(card, "Household ID (e.g. MAC000131)", 0, column=0)
        self.month_entry = labeled_entry(card, "Month (YYYY-MM)", 0, column=1)

        self.reading_entry = labeled_entry(card, "Meter Reading (kWh)", 2, column=0)
        self.bill_entry = labeled_entry(card, "Bill Amount (₹)", 2, column=1)

        self.appliance_entry = labeled_entry(card, "Appliance", 4, column=0)
        self.hours_entry = labeled_entry(card, "Usage Hours / Day", 4, column=1)

        btn_row = tk.Frame(self, bg=COLOR_BG)
        btn_row.pack(anchor="w", padx=20, pady=16)

        save_btn = tk.Button(btn_row, text="Save Entry", command=self.save_entry)
        style_button(save_btn)
        save_btn.pack(side="left", padx=(0, 10))

        clear_btn = tk.Button(btn_row, text="Clear Form", command=self.clear_form)
        style_button(clear_btn, bg=COLOR_ACCENT, hover=COLOR_PRIMARY)
        clear_btn.pack(side="left")

        self.status_label = tk.Label(self, text="", font=FONT_BODY, bg=COLOR_BG, fg=COLOR_TEXT)
        self.status_label.pack(anchor="w", padx=20)

    def save_entry(self):
        household = self.household_entry.get().strip()
        month = self.month_entry.get().strip()
        reading = self.reading_entry.get().strip()
        bill = self.bill_entry.get().strip()
        appliance = self.appliance_entry.get().strip()
        hours = self.hours_entry.get().strip()

        if not household:
            self._error("Household ID cannot be empty.")
            return
        if not month:
            self._error("Please enter a month (format YYYY-MM).")
            return

        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError:
            self._error("Month must be in YYYY-MM format, e.g. 2024-06.")
            return

        try:
            reading_val = float(reading)
            if reading_val < 0:
                raise ValueError
        except ValueError:
            self._error("Meter reading must be a positive number.")
            return

        try:
            bill_val = float(bill)
            if bill_val < 0:
                raise ValueError
        except ValueError:
            self._error("Bill amount must be a positive number.")
            return

        if not appliance:
            self._error("Please enter an appliance name.")
            return

        try:
            hours_val = float(hours)
            if not (0 <= hours_val <= 24):
                raise ValueError
        except ValueError:
            self._error("Usage hours must be a number between 0 and 24.")
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Evaluate reading for anomalies using household baseline
        anomaly_info = database.evaluate_reading_anomaly(
            household, reading_val, df=self.controller.df, k=2
        )

        try:
            # 1. Save directly into SQLite database
            database.save_meter_reading(
                household_id=household,
                month=month,
                meter_reading_kwh=reading_val,
                bill_amount=bill_val,
                appliance=appliance,
                usage_hours_per_day=hours_val,
                timestamp=timestamp,
                is_anomaly=anomaly_info["is_anomaly"],
                anomaly_type=anomaly_info["anomaly_type"],
                anomaly_score=anomaly_info["anomaly_score"],
                source="Manual/Tinkercad"
            )

            # 2. Maintain CSV backup for full compatibility
            ensure_readings_file()
            with open(READINGS_FILE, "a", newline="") as f:
                csv.writer(f).writerow([
                    timestamp, household, month, reading_val, bill_val, appliance, hours_val
                ])
        except Exception as e:
            self._error(f"Could not save entry: {e}")
            return

        if anomaly_info["is_anomaly"]:
            self.status_label.config(
                text=f"Saved to DB. Anomaly Flagged: {anomaly_info['anomaly_type']} (Score: {anomaly_info['anomaly_score']})",
                fg=COLOR_DANGER
            )
        else:
            self.status_label.config(
                text="Entry saved to database successfully (Normal consumption).",
                fg=COLOR_PRIMARY
            )
        self.clear_form()

    def _error(self, message):
        self.status_label.config(text=message, fg=COLOR_DANGER)
        messagebox.showerror("Invalid Input", message)

    def clear_form(self):
        for entry in (self.household_entry, self.month_entry, self.reading_entry,
                      self.bill_entry, self.appliance_entry, self.hours_entry):
            entry.delete(0, tk.END)


class HistoryTab(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLOR_BG)
        self.controller = controller

        header = tk.Frame(self, bg=COLOR_BG)
        header.pack(fill="x", padx=20, pady=(20, 10))
        tk.Label(header, text="Meter Reading History", font=FONT_HEADER,
                 bg=COLOR_BG, fg=COLOR_PRIMARY).pack(side="left")

        refresh_btn = tk.Button(header, text="Refresh", command=self.refresh)
        style_button(refresh_btn)
        refresh_btn.pack(side="right")

        clear_btn = tk.Button(header, text="Clear All", command=self.clear_all)
        style_button(clear_btn, bg=COLOR_DANGER, hover="#5c1c1c")
        clear_btn.pack(side="right", padx=8)

        columns = ["timestamp", "household_id", "month", "meter_reading_kwh",
                   "bill_amount", "appliance", "usage_hours_per_day", "anomaly_type"]
        headers = ["Saved At", "Household", "Month", "Reading (kWh)",
                   "Bill (₹)", "Appliance", "Hours/Day", "Anomaly Status"]

        tree_frame = tk.Frame(self, bg=COLOR_BG)
        tree_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        for col, head in zip(columns, headers):
            self.tree.heading(col, text=head)
            self.tree.column(col, width=130, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.empty_label = tk.Label(self, text="No meter readings saved yet.",
                                     font=FONT_BODY, bg=COLOR_BG, fg=COLOR_TEXT)

    def on_show(self):
        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        rows = database.get_meter_readings()
        if not rows:
            self.empty_label.pack(anchor="w", padx=20)
            return
        self.empty_label.pack_forget()

        for row in rows:
            self.tree.insert("", "end", values=[
                row.get("timestamp", ""),
                row.get("household_id", ""),
                row.get("month", ""),
                row.get("meter_reading_kwh", ""),
                row.get("bill_amount", ""),
                row.get("appliance", ""),
                row.get("usage_hours_per_day", ""),
                row.get("anomaly_type", "Normal")
            ])

    def clear_all(self):
        if messagebox.askyesno("Clear History", "This will permanently delete all saved readings from the database. Continue?"):
            try:
                database.clear_meter_readings()
            except Exception as e:
                messagebox.showerror("Database Error", f"Could not clear database: {e}")
                return
            if os.path.exists(READINGS_FILE):
                os.remove(READINGS_FILE)
                ensure_readings_file()
            self.refresh()



class HouseholdAnalysisTab(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLOR_BG)
        self.controller = controller

        tk.Label(self, text="Household Analysis", font=FONT_HEADER,
                 bg=COLOR_BG, fg=COLOR_PRIMARY).pack(anchor="w", padx=20, pady=(20, 10))

        controls = tk.Frame(self, bg=COLOR_CARD, padx=16, pady=14)
        controls.pack(fill="x", padx=20)

        tk.Label(controls, text="Household (LCLid)", font=FONT_LABEL,
                 bg=COLOR_CARD, fg=COLOR_TEXT).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.household_combo = ttk.Combobox(controls, width=18, state="readonly")
        self.household_combo.grid(row=1, column=0, sticky="w", padx=(0, 20), pady=(2, 0))

        tk.Label(controls, text="Start Date (YYYY-MM-DD)", font=FONT_LABEL,
                 bg=COLOR_CARD, fg=COLOR_TEXT).grid(row=0, column=1, sticky="w", padx=(0, 8))
        self.start_entry = tk.Entry(controls, width=16, relief="solid", bd=1)
        self.start_entry.grid(row=1, column=1, sticky="w", padx=(0, 20), pady=(2, 0))

        tk.Label(controls, text="End Date (YYYY-MM-DD)", font=FONT_LABEL,
                 bg=COLOR_CARD, fg=COLOR_TEXT).grid(row=0, column=2, sticky="w", padx=(0, 8))
        self.end_entry = tk.Entry(controls, width=16, relief="solid", bd=1)
        self.end_entry.grid(row=1, column=2, sticky="w", padx=(0, 20), pady=(2, 0))

        run_btn = tk.Button(controls, text="Run Analysis", command=self.run_analysis)
        style_button(run_btn)
        run_btn.grid(row=1, column=3, sticky="w", pady=(2, 0))

        # Results area
        results_frame = tk.Frame(self, bg=COLOR_BG)
        results_frame.pack(fill="both", expand=True, padx=20, pady=16)

        self.summary_text = tk.Text(
            results_frame, height=8, font=("Consolas", 10), bg=COLOR_CARD,
            fg=COLOR_TEXT, relief="flat", wrap="word", state="disabled"
        )
        self.summary_text.pack(fill="x", pady=(0, 10))

        tk.Label(results_frame, text="Detected anomalies in range:", font=FONT_LABEL,
                 bg=COLOR_BG, fg=COLOR_PRIMARY).pack(anchor="w")

        columns = ["day", "energy_sum", "anomaly_type"]
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=8)
        for col, head in zip(columns, ["Date", "Energy Sum (kWh)", "Anomaly Type"]):
            self.results_tree.heading(col, text=head)
            self.results_tree.column(col, width=160, anchor="center")
        self.results_tree.pack(fill="both", expand=True, pady=(4, 0))

    def on_show(self):
        df = self.controller.df
        if df is None:
            return
        households = sorted(df["LCLid"].unique().tolist())
        self.household_combo["values"] = households
        if households and not self.household_combo.get():
            self.household_combo.set(households[0])

    def run_analysis(self):
        df = self.controller.df
        if df is None:
            messagebox.showerror("No Data", "Dataset is not loaded.")
            return

        household = self.household_combo.get().strip()
        start_date = self.start_entry.get().strip()
        end_date = self.end_entry.get().strip()

        if not household:
            messagebox.showerror("Invalid Input", "Please select a household ID.")
            return

        if household not in df["LCLid"].values:
            messagebox.showerror("Invalid Household", f"Household '{household}' was not found in the dataset.")
            return

        if not start_date or not end_date:
            messagebox.showerror("Invalid Input", "Please enter both a start date and an end date.")
            return

        try:
            household_df = detector.filter_household(df, household)
            ranged_df = detector.filter_date_range(household_df, start_date, end_date)
        except ValueError as e:
            messagebox.showerror("Invalid Date Range", str(e))
            return
        except Exception as e:
            messagebox.showerror("Error", f"Could not run analysis: {e}")
            return

        if ranged_df.empty:
            messagebox.showwarning(
                "No Records",
                f"No records found for household '{household}' between {start_date} and {end_date}."
            )
            self._clear_results()
            return

        stats = detector.calculate_stats(ranged_df).iloc[0]
        anomalies = detector.detect_anomalies(ranged_df, k=2)
        anomaly_rows = anomalies[anomalies["anomaly"]]

        # Persist detected anomalies into SQLite database
        try:
            database.save_daily_anomalies(anomaly_rows, household_id=household, stats=stats)
        except Exception as e:
            print(f"[Database Warning] Could not persist daily anomalies: {e}")

        summary = (
            f"Household:        {household}\n"
            f"Date range:       {start_date} to {end_date}\n"
            f"Records found:    {len(ranged_df)}\n"
            f"Mean consumption: {stats['mean_consumption']:.3f} kWh\n"
            f"Std deviation:    {stats['std_consumption']:.3f} kWh\n"
            f"Min / Max:        {stats['min_consumption']:.3f} / {stats['max_consumption']:.3f} kWh\n"
            f"Total consumption:{stats['total_consumption']:.3f} kWh\n"
            f"Anomalies found:  {len(anomaly_rows)} "
            f"({(len(anomaly_rows) / len(ranged_df) * 100):.1f}% of records) — Synced to database"
        )
        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", tk.END)
        self.summary_text.insert(tk.END, summary)
        self.summary_text.configure(state="disabled")

        for row in self.results_tree.get_children():
            self.results_tree.delete(row)
        for _, r in anomaly_rows.iterrows():
            self.results_tree.insert("", "end", values=[
                r["day"].date(), f"{r['energy_sum']:.3f}", r["anomaly_type"]
            ])

    def _clear_results(self):
        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", tk.END)
        self.summary_text.configure(state="disabled")
        for row in self.results_tree.get_children():
            self.results_tree.delete(row)


class VisualizationsTab(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLOR_BG)
        self.controller = controller
        self.canvas = None

        tk.Label(self, text="Visualizations", font=FONT_HEADER,
                 bg=COLOR_BG, fg=COLOR_PRIMARY).pack(anchor="w", padx=20, pady=(20, 10))

        controls = tk.Frame(self, bg=COLOR_BG)
        controls.pack(fill="x", padx=20)

        tk.Label(controls, text="Chart type:", font=FONT_LABEL,
                 bg=COLOR_BG, fg=COLOR_TEXT).pack(side="left", padx=(0, 8))
        self.chart_combo = ttk.Combobox(
            controls, width=32, state="readonly",
            values=list(detector.PLOT_REGISTRY.keys())
        )
        self.chart_combo.pack(side="left", padx=(0, 12))

        generate_btn = tk.Button(controls, text="Generate", command=self.generate_chart)
        style_button(generate_btn)
        generate_btn.pack(side="left")

        self.chart_frame = tk.Frame(self, bg=COLOR_CARD)
        self.chart_frame.pack(fill="both", expand=True, padx=20, pady=16)

    def on_show(self):
        if not self.chart_combo.get():
            values = list(detector.PLOT_REGISTRY.keys())
            if values:
                self.chart_combo.set(values[0])

    def generate_chart(self):
        df = self.controller.df
        if df is None:
            messagebox.showerror("No Data", "Dataset is not loaded.")
            return

        chart_name = self.chart_combo.get()
        if not chart_name:
            messagebox.showerror("Invalid Input", "Please select a chart type.")
            return

        plot_fn = detector.PLOT_REGISTRY.get(chart_name)
        if plot_fn is None:
            messagebox.showerror("Error", "Unknown chart type selected.")
            return

        for widget in self.chart_frame.winfo_children():
            widget.destroy()

        try:
            fig = Figure(figsize=(10, 6), dpi=100)
            ax = fig.add_subplot(111)
            plot_fn(df, ax=ax)
        except Exception as e:
            messagebox.showerror("Chart Error", f"Could not generate chart: {e}")
            return

        self.canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)



if __name__ == "__main__":
    app = App()
    app.mainloop()