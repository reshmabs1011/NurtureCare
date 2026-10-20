# NurtureCare AI — Modern UI package

## What is included
- Modern responsive navy/teal sidebar interface
- Existing screening rules and form
- Experimental ML demo form with a large, visible prediction result
- Emergency guidance, referral SMS draft, map search
- SQLite reports and referral status updates
- Local draft storage and offline sync queue
- Blood pressure trend chart

## Install on Windows
1. Extract this ZIP.
2. Copy your existing `models\maternal_risk_model.joblib` into this project's `models` folder. Do not retrain unless you want to.
3. Open the extracted `NurtureCare_AI_Modern` folder in VS Code.
4. Open Terminal > New Terminal.
5. Run: `py -m pip install -r requirements.txt`
6. Run: `py app.py`
7. Open `http://127.0.0.1:5000` in your browser. Keep the terminal open.

## Important
- This is a hackathon prototype, not a medical device or diagnosis tool.
- Use synthetic/demo data only. Do not enter real patient identifiers.
- Severe symptoms need urgent professional care. Do not wait for this app, the model, or internet sync.
- The model's prediction is experimental and should not guide real care decisions.
- The offline queue stores draft data in browser localStorage, which is not encrypted.
- Chart.js and Google Fonts are loaded from CDNs; those features may be limited offline.

## Keep your current project safe
Before replacing files in your existing project, make a copy of the whole folder. This ZIP is a separate project folder and does not overwrite your original files.
