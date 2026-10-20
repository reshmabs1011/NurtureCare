# NurtureCare AI — Hackathon Prototype

**Project:** AI-Powered Maternal Health Risk Screening and Emergency Referral System  
**Tagline:** Caring for Mothers. Connecting Lives.

A person-free, responsive maternal-health support prototype with a single-page interface, rule-based screening explanations, local history, a data-quality checker, offline draft queue, basic trend charts, and emergency/referral shortcuts.

## Requirements
- Python 3.10+
- A modern browser
- Internet is only required for initial dependency installation. Chart.js and Bootstrap are loaded from CDN; the core layout and screening form still work without them, but charts/CDN styling may be unavailable offline.

## Run on Windows
1. Extract the ZIP.
2. Open the extracted `NurtureCare_AI_Complete` folder in VS Code.
3. Open Terminal → New Terminal.
4. Create a virtual environment:
   ```powershell
   python -m venv .venv
   ```
5. Activate it:
   ```powershell
   .venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks activation, use Command Prompt and run:
   ```bat
   .venv\Scripts\activate.bat
   ```
6. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
7. Start the app:
   ```bash
   python app.py
   ```
8. Open the local address printed in the terminal (usually `http://127.0.0.1:5000`).

## Features in this starter
- No login required
- Hamburger navigation and five views: Home, Health Screening, Emergency & Referrals, Health Reports, About / Guidelines
- Person-free visual design with abstract/vector-like CSS symbols (no human photos)
- Pregnancy week, systolic/diastolic blood pressure, symptom input
- Basic data-quality validation and explainable configurable demo rules
- Local browser draft and offline queue; queued entries are sent to Flask when online
- SQLite screening log and referral status field
- BP trend chart with Chart.js when CDN is available
- Emergency phone link, editable SMS draft, and map search link

## Important clinical and privacy limitations
This is an educational hackathon prototype, not a clinically validated medical device and not a diagnosis. Screening rules are illustrative and must be reviewed by qualified clinicians before any real use. A reassuring demo result does not mean a pregnancy is safe. Severe or urgent symptoms require immediate care; do not wait for the website, model, synchronization, or a callback. Emergency phone numbers and local facilities vary by region; verify local contacts before deployment. Use synthetic/demo information only. Browser local storage is not encrypted, and this prototype does not implement authentication, consent workflows, production security, or secure clinical data governance.

## Dataset / ML
No Kaggle dataset or trained model is bundled. Once the interface is tested, add a compatible dataset and model in a separate step. Never invent missing feature values or allow an experimental model to override urgent symptom guidance.
