from flask import Flask, render_template, request, jsonify
from datetime import datetime
import sqlite3
import os
import json
import math

try:
    import joblib
    import pandas as pd
except ImportError:
    joblib = None
    pd = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "nurturecare.db")
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
MODEL_PATH = os.path.join(BASE_DIR, "models", "maternal_risk_model.joblib")
ml_model_data = None
if joblib is not None and os.path.exists(MODEL_PATH):
    try:
        ml_model_data = joblib.load(MODEL_PATH)
        print("Maternal risk demo model loaded successfully.")
    except Exception as exc:
        print(f"ML model could not be loaded: {exc}")
else:
    print("ML model not found or ML packages missing. Screening features remain available.")

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS screenings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                name TEXT NOT NULL,
                weeks INTEGER NOT NULL,
                systolic INTEGER NOT NULL,
                diastolic INTEGER NOT NULL,
                symptoms TEXT NOT NULL,
                result_level TEXT NOT NULL,
                explanation TEXT NOT NULL,
                referral_status TEXT NOT NULL DEFAULT 'Not marked'
            )
        """)

def evaluate_demo(data):
    """Illustrative rules only; not clinical advice or a validated risk model."""
    errors = []
    try:
        name = str(data.get("name", "")).strip() or "Demo user"
        weeks = int(data.get("weeks", ""))
        systolic = int(data.get("systolic", ""))
        diastolic = int(data.get("diastolic", ""))
    except (TypeError, ValueError):
        return {"ok": False, "errors": ["Enter valid numbers for pregnancy week and blood pressure."]}

    if not 1 <= weeks <= 45:
        errors.append("Pregnancy week must be between 1 and 45 for this form.")
    if not 50 <= systolic <= 300:
        errors.append("Systolic BP is outside this form's plausibility range (50–300).")
    if not 30 <= diastolic <= 200:
        errors.append("Diastolic BP is outside this form's plausibility range (30–200).")
    if systolic <= diastolic:
        errors.append("Systolic BP should be higher than diastolic BP. Please check the values.")

    symptoms = data.get("symptoms", [])
    if isinstance(symptoms, str):
        symptoms = [symptoms]
    if not isinstance(symptoms, list):
        symptoms = []
    symptoms = [str(s) for s in symptoms]

    if errors:
        return {"ok": False, "errors": errors}

    severe_map = {
        "heavy_bleeding": "Heavy bleeding was selected.",
        "seizure": "Seizure or convulsion was selected.",
        "difficulty_breathing": "Difficulty breathing was selected.",
        "severe_headache_vision": "Severe headache or vision changes was selected.",
        "severe_abdominal_pain": "Severe abdominal pain was selected.",
        "reduced_fetal_movement": "Reduced or absent fetal movement was selected."
    }
    urgent_reasons = [severe_map[s] for s in symptoms if s in severe_map]
    reasons = []
    if systolic >= 160 or diastolic >= 110:
        reasons.append("Blood pressure is in a severe-range threshold in this illustrative rule set.")
    elif systolic >= 140 or diastolic >= 90:
        reasons.append("Blood pressure is elevated in this illustrative rule set and needs prompt professional review.")
    if urgent_reasons:
        level = "urgent"
        reasons = urgent_reasons + reasons
        explanation = "Urgent warning: " + " ".join(reasons) + " Seek urgent medical care now; do not wait for this website."
    elif reasons:
        level = "review"
        explanation = "Prompt clinical review recommended: " + " ".join(reasons) + " This is a screening prompt, not a diagnosis."
    else:
        level = "notice"
        explanation = "No warning rule was triggered by the limited fields entered. This does NOT mean everything is safe or rule out a problem. Contact a qualified healthcare professional with concerns."
    return {
        "ok": True, "name": name, "weeks": weeks, "systolic": systolic,
        "diastolic": diastolic, "symptoms": symptoms, "level": level,
        "explanation": explanation, "created_at": datetime.now().isoformat(timespec="seconds")
    }

def save_screening(result):
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO screenings
            (created_at, name, weeks, systolic, diastolic, symptoms, result_level, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (result["created_at"], result["name"], result["weeks"], result["systolic"],
             result["diastolic"], json.dumps(result["symptoms"]), result["level"], result["explanation"])
        )
        return cur.lastrowid

@app.route("/", methods=["GET"])
def index():
    init_db()
    return render_template("index.html")

@app.route("/api/screen", methods=["POST"])
def screen():
    init_db()
    data = request.get_json(silent=True) if request.is_json else request.form.to_dict(flat=False)
    if data is None:
        data = {}
    # Normalize form list values to their last value except symptoms.
    if not request.is_json:
        data = {k: (v if k == "symptoms" else (v[-1] if isinstance(v, list) else v)) for k, v in data.items()}
    result = evaluate_demo(data)
    if not result["ok"]:
        return jsonify(result), 400
    result["id"] = save_screening(result)
    return jsonify(result)

@app.route("/api/sync", methods=["POST"])
def sync():
    init_db()
    payload = request.get_json(silent=True) or {}
    items = payload.get("items", [])
    synced = []
    rejected = []
    for item in items[:100]:
        result = evaluate_demo(item)
        if not result["ok"]:
            rejected.append({"client_id": item.get("client_id"), "errors": result["errors"]})
            continue
        result["id"] = save_screening(result)
        synced.append({"client_id": item.get("client_id"), "id": result["id"], "created_at": result["created_at"]})
    return jsonify({"synced": synced, "rejected": rejected})

@app.route("/api/reports", methods=["GET"])
def reports():
    init_db()
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM screenings ORDER BY id DESC LIMIT 100").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/reports/<int:report_id>/referral", methods=["POST"])
def update_referral(report_id):
    init_db()
    status = (request.get_json(silent=True) or {}).get("status", "Not marked")
    allowed = {"Not marked", "Referred", "Follow-up needed", "Completed"}
    if status not in allowed:
        return jsonify({"error": "Invalid referral status"}), 400
    with get_db() as conn:
        cur = conn.execute("UPDATE screenings SET referral_status=? WHERE id=?", (status, report_id))
        if cur.rowcount == 0:
            return jsonify({"error": "Report not found"}), 404
    return jsonify({"ok": True, "status": status})


@app.route("/api/ml-demo", methods=["POST"])
def ml_demo():
    if ml_model_data is None or pd is None:
        return jsonify({"ok": False, "error": "The trained model is unavailable. Check models/maternal_risk_model.joblib and install requirements."}), 503
    data = request.get_json(silent=True) or {}
    features = ml_model_data.get("features", [])
    required = {"Age": "age", "SystolicBP": "systolic", "DiastolicBP": "diastolic", "BS": "bs", "BodyTemp": "bodytemp", "HeartRate": "heartrate"}
    try:
        values = {feature: float(data[input_name]) for feature, input_name in required.items()}
    except (KeyError, TypeError, ValueError):
        return jsonify({"ok": False, "error": "Please provide all six numeric measurements."}), 400
    if not all(math.isfinite(v) for v in values.values()):
        return jsonify({"ok": False, "error": "Measurements must be finite numbers."}), 400
    ranges = {"Age": (10,70), "SystolicBP": (50,300), "DiastolicBP": (30,200), "BS": (1,500), "BodyTemp": (80,110), "HeartRate": (20,250)}
    if any(not ranges[k][0] <= v <= ranges[k][1] for k,v in values.items()):
        return jsonify({"ok": False, "error": "One or more measurements are outside the demo input limits."}), 400
    if not features or any(feature not in values for feature in features):
        return jsonify({"ok": False, "error": "The saved model feature list is missing or does not match this form."}), 500
    X = pd.DataFrame([[values[name] for name in features]], columns=features)
    prediction = str(ml_model_data["model"].predict(X)[0])
    return jsonify({"ok": True, "demo_prediction": prediction, "notice": "Experimental machine-learning output only. Not a diagnosis or a clinically validated risk assessment. Do not use this result to decide whether care is needed."})

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
