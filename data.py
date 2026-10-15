from pathlib import Path
import numpy as np
import pandas as pd

def make_demo_data(days=120, seed=21):
    """Create plausible hourly building electricity data for a reproducible demo."""
    rng = np.random.default_rng(seed)
    index = pd.date_range(end=pd.Timestamp.now().floor("h"), periods=days * 24, freq="h")
    hour = index.hour.to_numpy()
    dow = index.dayofweek.to_numpy()
    day_of_year = index.dayofyear.to_numpy()
    business = np.where((dow < 5) & (hour >= 7) & (hour <= 19), 1.0, 0.0)
    daily = 18 + 7 * np.sin((hour - 7) * 2 * np.pi / 24) + 5 * business
    weekly = np.where(dow < 5, 5.5, -2.5)
    seasonal = 3 * np.sin(day_of_year * 2 * np.pi / 365)
    noise = rng.normal(0, 1.8, len(index))
    energy = np.clip(daily + weekly + seasonal + noise, 5, None)
    return pd.DataFrame({"energy_kwh": energy}, index=index).rename_axis("timestamp")

def load_energy_data(path):
    """Accept CSV with timestamp/Datetime/date and energy_kwh/Energy/energy/consumption columns."""
    df = pd.read_csv(path)
    if df.empty:
        raise ValueError("The CSV file is empty.")
    cols = {c.strip().lower(): c for c in df.columns}
    time_col = next((cols[c] for c in ("timestamp","datetime","date","time") if c in cols), None)
    energy_col = next((cols[c] for c in ("energy_kwh","energy","consumption","usage","kwh","load") if c in cols), None)
    if time_col is None or energy_col is None:
        raise ValueError("CSV needs a timestamp column (timestamp/Datetime/date) and an energy column (energy_kwh/Energy/consumption).")
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df[energy_col] = pd.to_numeric(df[energy_col], errors="coerce")
    df = df.dropna(subset=[time_col, energy_col]).sort_values(time_col)
    if len(df) < 240:
        raise ValueError("Please provide at least 240 valid hourly observations (10 days) for lag-based forecasting.")
    df = df.drop_duplicates(subset=[time_col]).set_index(time_col)
    df = df[[energy_col]].rename(columns={energy_col:"energy_kwh"})
    df = df.resample("h").mean().interpolate("time").ffill().bfill()
    if df["energy_kwh"].isna().any():
        raise ValueError("Energy values could not be cleaned. Check your CSV.")
    df.index.name = "timestamp"
    return df
