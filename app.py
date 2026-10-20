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


# --- NurtureCare multilingual rule-based assistant (no AI model required) ---
# This assistant uses predefined keyword rules and replies. It does not diagnose.
CHAT_URGENT_TERMS = {
    "en": ["heavy bleeding", "bleeding heavily", "seizure", "convulsion", "can't breathe", "cannot breathe", "difficulty breathing", "severe headache", "blurred vision", "vision changes", "severe abdominal pain", "severe stomach pain", "baby not moving", "reduced fetal movement", "fainting"],
    "ta": ["அதிக இரத்தப்போக்கு", "இரத்தப்போக்கு", "வலிப்பு", "மூச்சுத்திணறல்", "மூச்சு விட முடியவில்லை", "கடுமையான தலைவலி", "கண் மங்கல்", "பார்வை மங்கல்", "கடுமையான வயிற்று வலி", "குழந்தை அசைவில்லை", "குழந்தை அசைவு குறைவு"],
    "hi": ["बहुत खून बहना", "तेज रक्तस्राव", "खून बह रहा", "दौरा", "सांस लेने में कठिनाई", "सांस नहीं ले पा रही", "तेज सिरदर्द", "धुंधला दिखना", "आंखों के आगे धुंधला", "पेट में तेज दर्द", "बच्चे की हलचल नहीं", "बच्चे की हलचल कम", "बेहोशी"]
}

CHAT_REPLIES = {
    "en": {
        "urgent": "This may be an emergency. Please seek urgent medical care now or contact your local emergency service. In India, call 112. Do not wait for this chatbot or an app result.",
        "bleeding": "Bleeding during pregnancy needs professional assessment. Heavy bleeding is an emergency—seek urgent medical care now. Do not rely on this chatbot to judge the cause.",
        "bp": "High blood pressure during pregnancy can be serious. A reading of 140/90 mmHg or higher needs prompt advice from a healthcare professional; 160 systolic or 110 diastolic or higher needs urgent assessment. If you feel unwell or have warning symptoms, seek urgent care now.",
        "low_bp": "Low blood pressure during pregnancy can have different causes. If you feel dizzy, faint, weak, or unwell, contact a healthcare professional promptly. If you faint or have severe symptoms, seek urgent medical care. This chatbot cannot assess your condition.",
        "headache": "A severe or persistent headache, especially with vision changes, needs urgent medical assessment during pregnancy. Please seek care now rather than waiting for an online answer.",
        "pain": "Stay calm and take the prescribed medicine, if the pain is unbearable contact the nearby hospitals or 112.",
        "movement": "If your baby's movements are reduced or have stopped, contact your maternity unit or healthcare professional urgently now. Do not wait until tomorrow or rely on a chatbot.",
        "nutrition": "During pregnancy, aim for varied meals, safe drinking water, and foods recommended by your healthcare professional. Ask your clinician about iron, folic acid, or other supplements; do not start or change medicines based only on a chatbot.",
        "checkup": "Keep regular antenatal appointments so a healthcare professional can check your health and your baby's development. Ask your local clinic when your next visit and recommended tests are due.",
        "medicine": "Please check with your doctor, midwife, or pharmacist before taking, stopping, or changing any medicine or supplement during pregnancy. I cannot recommend a specific medicine or dose.",
        "default": "I can share general maternal-care information about antenatal checkups, blood pressure, nutrition, medicines, and warning signs. Try asking one of those questions. I cannot diagnose or confirm that you or your baby are safe."
    },
    "ta": {
        "urgent": "இது அவசரநிலையாக இருக்கலாம். உடனே அருகிலுள்ள மருத்துவமனைக்குச் செல்லுங்கள் அல்லது உள்ளூர் அவசர உதவியை அழைக்கவும். இந்தியாவில் 112-ஐ அழைக்கலாம். இந்த chatbot பதிலுக்காக காத்திருக்க வேண்டாம்.",
        "bleeding": "கர்ப்ப கால இரத்தப்போக்கிற்கு மருத்துவ பரிசோதனை அவசியம். அதிக இரத்தப்போக்கு இருந்தால் உடனடியாக அவசர மருத்துவ உதவி பெறுங்கள். காரணத்தை இந்த chatbot மூலம் தீர்மானிக்க வேண்டாம்.",
        "bp": "கர்ப்ப காலத்தில் உயர் இரத்த அழுத்தம் ஆபத்தானதாக இருக்கலாம். 140/90 mmHg அல்லது அதற்கு மேல் இருந்தால் விரைவாக சுகாதார நிபுணரைத் தொடர்புகொள்ளுங்கள்; மேல் அழுத்தம் 160 அல்லது கீழ் அழுத்தம் 110 அல்லது அதற்கு மேல் இருந்தால் அவசர மதிப்பீடு தேவை. உடல்நிலை மோசமாக இருந்தால் உடனே மருத்துவ உதவி பெறுங்கள்.",
        "low_bp": "கர்ப்ப காலத்தில் குறைந்த இரத்த அழுத்தம் தலைச்சுற்றல், பலவீனம் அல்லது மயக்கத்தை ஏற்படுத்தலாம். இரத்த அழுத்தம் குறைவாக இருந்து உடல்நலக் குறைவு ஏற்பட்டால், விரைவாக சுகாதார நிபுணரைத் தொடர்புகொள்ளுங்கள். மயக்கம் அல்லது கடுமையான அறிகுறிகள் இருந்தால் உடனடியாக மருத்துவ உதவி பெறுங்கள்.",
        "headache": "கடுமையான அல்லது நீடிக்கும் தலைவலி, குறிப்பாக பார்வை மாற்றங்களுடன் இருந்தால், கர்ப்ப காலத்தில் உடனடி மருத்துவ மதிப்பீடு தேவை. இணையப் பதிலுக்காக காத்திருக்க வேண்டாம்.",
        "movement": "குழந்தையின் அசைவு குறைந்தாலோ நின்றுவிட்டாலோ உடனே மகப்பேறு பிரிவு அல்லது சுகாதார நிபுணரைத் தொடர்புகொள்ளுங்கள். நாளை வரை காத்திருக்க வேண்டாம்.",
        "nutrition": "கர்ப்ப காலத்தில் பலவகை சத்தான உணவுகள் மற்றும் பாதுகாப்பான குடிநீர் எடுத்துக்கொள்ளுங்கள். இரும்பு, ஃபோலிக் அமிலம் அல்லது பிற சத்துமருந்துகள் பற்றி மருத்துவரிடம் கேளுங்கள். chatbot ஆலோசனையால் மட்டும் மருந்தைத் தொடங்கவோ மாற்றவோ வேண்டாம்.",
        "checkup": "தாய் மற்றும் குழந்தையின் நலனை கண்காணிக்க கர்ப்பகால பரிசோதனைகளை தவறாமல் மேற்கொள்ளுங்கள். அடுத்த பரிசோதனை மற்றும் தேவையான சோதனைகள் குறித்து உங்கள் சுகாதார மையத்திடம் கேளுங்கள்.",
        "medicine": "கர்ப்ப காலத்தில் எந்த மருந்தையும் எடுத்துக்கொள்வதற்கு, நிறுத்துவதற்கு அல்லது அளவை மாற்றுவதற்கு முன் மருத்துவர் அல்லது மருந்தாளரை அணுகுங்கள். குறிப்பிட்ட மருந்தையோ அளவையோ நான் பரிந்துரைக்க முடியாது.",
        "default": "கர்ப்பகால பரிசோதனை, இரத்த அழுத்தம், உணவு, மருந்துகள் மற்றும் எச்சரிக்கை அறிகுறிகள் பற்றி பொதுவான தகவலை வழங்க முடியும். அவற்றில் ஒன்றைப் பற்றி கேளுங்கள். நான் நோயறிதல் செய்யவோ நீங்கள் பாதுகாப்பாக உள்ளீர்கள் என்று உறுதி செய்யவோ முடியாது."
    },
    "hi": {
        "urgent": "यह आपात स्थिति हो सकती है। कृपया तुरंत चिकित्सा सहायता लें या स्थानीय आपातकालीन सेवा से संपर्क करें। भारत में 112 पर कॉल कर सकते हैं। चैटबॉट के जवाब का इंतज़ार न करें।",
        "bleeding": "गर्भावस्था में रक्तस्राव की चिकित्सकीय जाँच ज़रूरी है। अधिक रक्तस्राव होने पर तुरंत आपातकालीन चिकित्सा सहायता लें। चैटबॉट से कारण का अनुमान न लगाएँ।",
        "bp": "गर्भावस्था में उच्च रक्तचाप गंभीर हो सकता है। 140/90 mmHg या अधिक होने पर जल्द स्वास्थ्यकर्मी से संपर्क करें; ऊपर का दबाव 160 या नीचे का 110 या अधिक हो तो तत्काल जाँच ज़रूरी है। अस्वस्थ महसूस हो या चेतावनी के लक्षण हों तो तुरंत सहायता लें।",
        "headache": "गर्भावस्था में तेज़ या लगातार सिरदर्द, खासकर दृष्टि में बदलाव के साथ, तत्काल चिकित्सकीय जाँच की आवश्यकता हो सकती है। ऑनलाइन जवाब की प्रतीक्षा न करें।",
        "movement": "यदि बच्चे की हलचल कम हो गई है या बंद हो गई है, तो अभी अपनी प्रसूति इकाई या स्वास्थ्यकर्मी से संपर्क करें। कल तक इंतज़ार न करें।",
        "nutrition": "गर्भावस्था में विविध पौष्टिक भोजन और सुरक्षित पानी लें। आयरन, फोलिक एसिड या अन्य सप्लीमेंट के बारे में स्वास्थ्यकर्मी से पूछें। केवल चैटबॉट की सलाह पर दवा शुरू या बदलें नहीं।",
        "checkup": "अपने और बच्चे के स्वास्थ्य की निगरानी के लिए नियमित प्रसवपूर्व जाँच कराएँ। अगली मुलाकात और ज़रूरी जाँचों के बारे में अपने स्वास्थ्य केंद्र से पूछें।",
        "medicine": "गर्भावस्था में कोई दवा या सप्लीमेंट लेने, रोकने या बदलने से पहले डॉक्टर, दाई या फार्मासिस्ट से पूछें। मैं किसी विशेष दवा या खुराक की सलाह नहीं दे सकता।",
        "default": "मैं प्रसवपूर्व जाँच, रक्तचाप, पोषण, दवाओं और चेतावनी संकेतों के बारे में सामान्य जानकारी दे सकता हूँ। इनमें से किसी विषय पर पूछें। मैं निदान नहीं कर सकता और यह पुष्टि नहीं कर सकता कि आप या बच्चा सुरक्षित हैं।"
    }
}

def maternal_chat_reply(message, language):
    """Return a predefined, language-specific response based on simple keyword rules."""
    lang = language if language in CHAT_REPLIES else "en"
    text = message.casefold()
    # Urgent keyword matches are checked first and override ordinary topic matches.
    if any(term.casefold() in text for term in CHAT_URGENT_TERMS[lang]):
        return CHAT_REPLIES[lang]["urgent"], True
    if lang == "en":
        rules = [
    (["low bp", "low blood pressure", "blood pressure is low",
      "my bp is low", "bp is too low", "hypotension"], "low_bp"),
    (["bleed", "spotting"], "bleeding"),
    (["blood pressure", " bp", "hypertension", "pressure high"], "bp"),
    (["headache", "vision", "blurred", "dizzy"], "headache"),
    (["movement", "kick", "baby moving", "fetal"], "movement"),
    (["food", "diet", "nutrition", "eat", "iron", "folic"], "nutrition"),
    (["checkup", "check-up", "antenatal", "prenatal", "appointment", "scan"], "checkup"),
    (["medicine", "medication", "tablet", "drug", "supplement"], "medicine")
]
    elif lang == "ta":
        rules = [
            (["இரத்தப்போக்கு", "ரத்தப்போக்கு", "இரத்தம்"], "bleeding"),
            (["இரத்த அழுத்தம்", "அழுத்தம்"], "bp"),
            (["தலைவலி", "பார்வை", "மயக்கம்"], "headache"),
            (["அசைவு", "உதை", "குழந்தை அசைவு"], "movement"),
            (["உணவு", "சத்து", "ஊட்டச்சத்து", "இரும்பு", "ஃபோலிக்"], "nutrition"),
            (["பரிசோதனை", "மருத்துவமனை", "சோதனை", "ஸ்கேன்"], "checkup"),
            (["மருந்து", "மாத்திரை"], "medicine")]
    else:
        rules = [
            (["रक्तस्राव", "खून", "ब्लीडिंग"], "bleeding"),
            (["रक्तचाप", "ब्लड प्रेशर", "बीपी", "दबाव"], "bp"),
            (["सिरदर्द", "दृष्टि", "धुंधला", "चक्कर"], "headache"),
            (["हलचल", "लात", "बच्चा हिल"], "movement"),
            (["खाना", "भोजन", "पोषण", "आयरन", "फोलिक"], "nutrition"),
            (["जाँच", "जांच", "चेकअप", "अस्पताल", "अल्ट्रासाउंड"], "checkup"),
            (["दवा", "गोली", "दवाई", "सप्लीमेंट"], "medicine")]
    for terms, key in rules:
        if any(term in text for term in terms):
            return CHAT_REPLIES[lang][key], False
    return CHAT_REPLIES[lang]["default"], False

@app.route("/assistant", methods=["GET"])
def assistant_page():
    return render_template("chat.html")

@app.route("/api/chat", methods=["POST"])
def chat_api():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    language = str(payload.get("language", "en")).lower()
    if not message:
        return jsonify({"ok": False, "error": "Please enter a message."}), 400
    if len(message) > 1000:
        return jsonify({"ok": False, "error": "Please keep your message under 1,000 characters."}), 400
    if language not in {"en", "ta", "hi"}:
        language = "en"
    reply, urgent = maternal_chat_reply(message, language)
    return jsonify({"ok": True, "reply": reply, "urgent": urgent, "mode": "rule-based", "notice": "General information only—not a diagnosis. For severe symptoms, seek urgent medical care."})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
