
from pathlib import Path

import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)

# Find the project folder automatically
BASE_DIR = Path(__file__).resolve().parent

# Location of your dataset
DATA_FILE = Path (r"C:\Users\SRILEKHA\Downloads\archive\Maternal Health Risk Data Set.csv")
# Create a folder to save the trained model
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(exist_ok=True)

# STEP 1: Load the dataset
print("Loading maternal health dataset...")

df = pd.read_csv(DATA_FILE)
df.columns = df.columns.str.strip()

print("Dataset loaded successfully!")
print("Dataset shape:", df.shape)
print("Columns:", list(df.columns))

# STEP 2: Select the input features
features = [
    "Age",
    "SystolicBP",
    "DiastolicBP",
    "BS",
    "BodyTemp",
    "HeartRate"
]

target = "RiskLevel"

# Check whether the required columns exist
missing = set(features + [target]) - set(df.columns)

if missing:
    raise ValueError(
        f"Missing columns in dataset: {missing}"
    )

# STEP 3: Clean the data
df = df[features + [target]].dropna()
df = df.drop_duplicates()

X = df[features]
y = df[target].astype(str).str.strip().str.lower()

print("\nNumber of usable records:", len(df))
print("Risk categories:")
print(y.value_counts())

# STEP 4: Split data into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)

print("\nTraining the model...")

# STEP 5: Train the machine-learning model
model = RandomForestClassifier(
    n_estimators=200,
    random_state=42,
    class_weight="balanced"
)

model.fit(X_train, y_train)

print("Training completed!")

# STEP 6: Test the model
predictions = model.predict(X_test)

accuracy = accuracy_score(y_test, predictions)

print("\nModel test accuracy:", round(accuracy * 100, 2), "%")

print("\nClassification report:")
print(
    classification_report(
        y_test,
        predictions,
        zero_division=0
    )
)

print("Confusion matrix:")
print(confusion_matrix(y_test, predictions))

# STEP 7: Save the trained model
model_path = MODEL_DIR / "maternal_risk_model.joblib"

joblib.dump(
    {
        "model": model,
        "features": features
    },
    model_path
)

print("\n================================")
print("MODEL SAVED SUCCESSFULLY!")
print("Saved at:", model_path)
print("================================")
