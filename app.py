from flask import Flask, render_template, request, jsonify, send_file
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
import io
from datetime import datetime, timedelta
from src.forecasting import EnergyForecaster
from src.data import load_energy_data, make_demo_data

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"
OUTPUT_DIR = BASE_DIR / "outputs"
for folder in (DATA_DIR, MODEL_DIR, OUTPUT_DIR):
    folder.mkdir(exist_ok=True)

app = Flask(__name__)
forecaster = EnergyForecaster()
DATA_PATH = DATA_DIR / "energy.csv"
MODEL_PATH = MODEL_DIR / "energy_model.joblib"
LATEST = {"metrics": None, "forecast": None, "history": None, "source": "demo simulation"}

def refresh_data():
    if DATA_PATH.exists():
        try:
            data = load_energy_data(DATA_PATH)
            LATEST["source"] = "uploaded/local dataset"
        except Exception:
            data = make_demo_data()
            LATEST["source"] = "demo simulation (fallback)"
    else:
        data = make_demo_data()
        LATEST["source"] = "demo simulation"
    LATEST["history"] = data
    return data

def train_model(data):
    metrics = forecaster.fit(data)
    joblib.dump(forecaster.model, MODEL_PATH)
    LATEST["metrics"] = metrics
    return metrics

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/dashboard")
def dashboard_data():
    data = refresh_data()
    if LATEST["metrics"] is None:
        train_model(data)
    forecast = forecaster.forecast(data, 24)
    LATEST["forecast"] = forecast
    return jsonify({
        "source": LATEST["source"],
        "metrics": LATEST["metrics"],
        "summary": forecaster.summary(data, forecast),
        "history": data.tail(168).reset_index().rename(columns={"index":"timestamp"}).to_dict(orient="records"),
        "forecast": forecast.to_dict(orient="records"),
        "hourly_profile": [{"hour": int(hour), "avg_kwh": round(float(value), 2)} for hour, value in data.groupby(data.index.hour)["energy_kwh"].mean().items()],
        "weekday_profile": [{"day": str(day), "avg_kwh": round(float(value), 2)} for day, value in data.groupby(data.index.day_name())["energy_kwh"].mean().reindex(["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]).items() if pd.notna(value)]
    })

@app.route("/api/forecast", methods=["POST"])
def create_forecast():
    body = request.get_json(silent=True) or {}
    horizon = int(body.get("horizon", 24))
    if horizon < 1 or horizon > 168:
        return jsonify({"error": "Forecast horizon must be between 1 and 168 hours."}), 400
    data = refresh_data()
    if LATEST["metrics"] is None:
        train_model(data)
    forecast = forecaster.forecast(data, horizon)
    LATEST["forecast"] = forecast
    forecast.to_csv(OUTPUT_DIR / "latest_forecast.csv", index=False)
    return jsonify({
        "forecast": forecast.to_dict(orient="records"),
        "summary": forecaster.summary(data, forecast),
        "horizon": horizon
    })

@app.route("/api/train", methods=["POST"])
def retrain():
    data = refresh_data()
    metrics = train_model(data)
    return jsonify({"message":"Model trained successfully", "metrics":metrics, "source":LATEST["source"]})

@app.route("/api/upload", methods=["POST"])
def upload_dataset():
    if "dataset" not in request.files:
        return jsonify({"error":"Choose a CSV file first."}), 400
    uploaded = request.files["dataset"]
    if not uploaded.filename.lower().endswith(".csv"):
        return jsonify({"error":"Please upload a .csv file."}), 400
    target = DATA_DIR / "energy.csv"
    uploaded.save(target)
    try:
        data = load_energy_data(target)
    except Exception as exc:
        target.unlink(missing_ok=True)
        return jsonify({"error":str(exc)}), 400
    LATEST["history"] = data
    LATEST["source"] = "uploaded dataset"
    LATEST["metrics"] = None
    return jsonify({"message":f"Dataset loaded: {len(data):,} hourly rows", "rows":len(data), "source":LATEST["source"]})

@app.route("/api/export")
def export_forecast():
    forecast = LATEST.get("forecast")
    if forecast is None:
        data = refresh_data()
        if LATEST["metrics"] is None:
            train_model(data)
        forecast = forecaster.forecast(data, 24)
    output = io.BytesIO()
    forecast.to_csv(output, index=False)
    output.seek(0)
    return send_file(output, mimetype="text/csv", as_attachment=True, download_name="energy_forecast.csv")

@app.route("/api/reset-demo", methods=["POST"])
def reset_demo():
    DATA_PATH.unlink(missing_ok=True)
    LATEST.update({"metrics":None, "forecast":None, "history":None, "source":"demo simulation"})
    data = refresh_data()
    train_model(data)
    return jsonify({"message":"Demo dataset restored", "source":LATEST["source"]})

@app.route("/health")
def health():
    return jsonify({"status":"ok", "service":"AI Energy Forecasting Dashboard"})

if __name__ == "__main__":
    print("\\n⚡ AI Energy Forecasting Dashboard")
    print("Open http://127.0.0.1:5000")
    app.run(debug=True, host="127.0.0.1", port=5000)
