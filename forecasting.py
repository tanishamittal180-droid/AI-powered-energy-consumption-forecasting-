"""Time-aware energy forecasting with validation-based model selection."""
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

FEATURES = [
    "hour", "day_of_week", "day_of_year", "is_weekend",
    "hour_sin", "hour_cos", "week_sin", "week_cos",
    "lag_1", "lag_2", "lag_24", "lag_48", "lag_168",
    "rolling_6", "rolling_24", "rolling_168"
]

def make_features(data):
    frame = data.copy().sort_index()
    idx = frame.index
    frame["hour"] = idx.hour
    frame["day_of_week"] = idx.dayofweek
    frame["day_of_year"] = idx.dayofyear
    frame["is_weekend"] = (idx.dayofweek >= 5).astype(int)
    frame["hour_sin"] = np.sin(2 * np.pi * idx.hour / 24)
    frame["hour_cos"] = np.cos(2 * np.pi * idx.hour / 24)
    frame["week_sin"] = np.sin(2 * np.pi * (idx.dayofweek * 24 + idx.hour) / 168)
    frame["week_cos"] = np.cos(2 * np.pi * (idx.dayofweek * 24 + idx.hour) / 168)
    for lag in (1, 2, 24, 48, 168):
        frame[f"lag_{lag}"] = frame["energy_kwh"].shift(lag)
    prior = frame["energy_kwh"].shift(1)
    frame["rolling_6"] = prior.rolling(6, min_periods=6).mean()
    frame["rolling_24"] = prior.rolling(24, min_periods=24).mean()
    frame["rolling_168"] = prior.rolling(168, min_periods=168).mean()
    return frame.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURES + ["energy_kwh"])


def _new_candidates():
    return {
        "Random Forest": RandomForestRegressor(n_estimators=240, max_depth=16, min_samples_leaf=2, max_features=0.9, random_state=42, n_jobs=-1),
        "Extra Trees": ExtraTreesRegressor(n_estimators=240, max_depth=18, min_samples_leaf=2, max_features=0.9, random_state=42, n_jobs=-1),
        "Gradient Boosting": HistGradientBoostingRegressor(max_iter=180, learning_rate=0.07, max_leaf_nodes=20, l2_regularization=1.0, random_state=42),
    }

class EnergyForecaster:
    def __init__(self):
        self.model = None
        self.model_name = "Not trained"
        self.data = None
        self.metrics = None

    def fit(self, data):
        data = data.sort_index().copy()
        if len(data) < 24 * 10:
            raise ValueError("For reliable lag-based forecasting, provide at least 10 days of hourly data (240 rows).")
        featured = make_features(data)
        if len(featured) < 48:
            raise ValueError("Not enough usable history after feature engineering. Provide at least 10 days of hourly readings.")
        split = max(int(len(featured) * 0.8), 1)
        train, test = featured.iloc[:split], featured.iloc[split:]
        if len(test) < 24 and len(featured) >= 100:
            split = len(featured) - min(24, max(1, len(featured)//5))
            train, test = featured.iloc[:split], featured.iloc[split:]
        if train.empty or test.empty:
            raise ValueError("Not enough rows for chronological train/test validation.")

        results = []
        candidates = _new_candidates()
        for name, candidate in candidates.items():
            candidate.fit(train[FEATURES], train["energy_kwh"])
            pred = np.maximum(0, candidate.predict(test[FEATURES]))
            mae = float(mean_absolute_error(test["energy_kwh"], pred))
            rmse = float(np.sqrt(mean_squared_error(test["energy_kwh"], pred)))
            r2 = float(r2_score(test["energy_kwh"], pred)) if len(test) > 1 else 0.0
            results.append({"name": name, "model": candidate, "mae": mae, "rmse": rmse, "r2": r2})
        # Choose by chronological holdout MAE, a directly interpretable measure.
        best = min(results, key=lambda item: item["mae"])
        self.model_name = best["name"]
        self.model = _new_candidates()[self.model_name]
        self.model.fit(featured[FEATURES], featured["energy_kwh"])
        self.metrics = {
            "mae": round(best["mae"], 3), "rmse": round(best["rmse"], 3),
            "r2": round(best["r2"], 3), "test_samples": int(len(test)),
            "model_name": self.model_name,
            "candidates": [{"model": r["name"], "mae": round(r["mae"], 3), "rmse": round(r["rmse"], 3), "r2": round(r["r2"], 3)} for r in sorted(results, key=lambda x: x["mae"])]
        }
        self.data = data
        return self.metrics

    def forecast(self, data, horizon=24):
        if self.model is None:
            self.fit(data)
        history = data.sort_index()["energy_kwh"].astype(float).copy()
        rows = []
        for _ in range(int(horizon)):
            ts = history.index[-1] + pd.Timedelta(hours=1)
            vals = history.to_numpy(dtype=float)
            def lag(n): return float(vals[-n]) if len(vals) >= n else float(vals[-1])
            feature = {
                "hour": ts.hour, "day_of_week": ts.dayofweek, "day_of_year": ts.dayofyear,
                "is_weekend": int(ts.dayofweek >= 5),
                "hour_sin": np.sin(2*np.pi*ts.hour/24), "hour_cos": np.cos(2*np.pi*ts.hour/24),
                "week_sin": np.sin(2*np.pi*(ts.dayofweek*24+ts.hour)/168), "week_cos": np.cos(2*np.pi*(ts.dayofweek*24+ts.hour)/168),
                "lag_1": lag(1), "lag_2": lag(2), "lag_24": lag(24), "lag_48": lag(48), "lag_168": lag(168),
                "rolling_6": float(np.mean(vals[-6:])), "rolling_24": float(np.mean(vals[-24:])),
                "rolling_168": float(np.mean(vals[-168:]))
            }
            prediction = max(0.0, float(self.model.predict(pd.DataFrame([feature], columns=FEATURES))[0]))
            rows.append({"timestamp": ts.isoformat(), "predicted_kwh": round(prediction, 2)})
            history.loc[ts] = prediction
        return pd.DataFrame(rows)

    def summary(self, data, forecast):
        recent = data["energy_kwh"].tail(24)
        pred = forecast["predicted_kwh"]
        last = float(recent.mean())
        next_avg = float(pred.mean()) if len(pred) else 0.0
        peak_i = int(pred.to_numpy().argmax()) if len(pred) else 0
        peak = float(pred.iloc[peak_i]) if len(pred) else 0.0
        change = ((next_avg-last)/last*100) if last else 0.0
        return {
            "latest_hour_kwh": round(float(data["energy_kwh"].iloc[-1]), 2),
            "daily_average_kwh": round(float(data["energy_kwh"].tail(24).sum()), 2),
            "forecast_average_kwh": round(next_avg, 2),
            "forecast_total_kwh": round(float(pred.sum()), 2),
            "change_pct": round(change, 1), "peak_kwh": round(peak, 2),
            "peak_time": forecast.iloc[peak_i]["timestamp"] if len(forecast) else None,
            "history_points": int(len(data))
        }
