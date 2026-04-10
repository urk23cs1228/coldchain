import pandas as pd
import numpy as np
import joblib
import os
import json
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import (classification_report, confusion_matrix,
                             accuracy_score, mean_absolute_error, r2_score)
from sklearn.pipeline import Pipeline

# ── Load dataset ──
df = pd.read_csv('data/shipment_dataset.csv')
print(f"Loaded {len(df)} records\n")

# ── Encode categoricals ──
le_food = LabelEncoder()
le_vehicle = LabelEncoder()
le_tod = LabelEncoder()
le_risk = LabelEncoder()

df['food_encoded'] = le_food.fit_transform(df['food_type'])
df['vehicle_encoded'] = le_vehicle.fit_transform(df['vehicle_type'])
df['tod_encoded'] = le_tod.fit_transform(df['time_of_day'])
df['risk_encoded'] = le_risk.fit_transform(df['risk_level'])

# ── Feature columns ──
FEATURES = [
    'food_encoded', 'vehicle_encoded', 'tod_encoded',
    'travel_hours', 'ambient_temp_c', 'humidity_pct',
    'container_temp_c', 'vehicle_compatible', 'temp_deviation',
    'food_sensitivity', 'vehicle_efficiency'
]

X = df[FEATURES]
y_class = df['spoiled']          # Binary classification
y_reg   = df['spoilage_probability']  # Regression (probability)
y_risk  = df['risk_encoded']     # Multi-class risk level

X_train, X_test, yc_train, yc_test, yr_train, yr_test, yrisk_train, yrisk_test = \
    train_test_split(X, y_class, y_reg, y_risk, test_size=0.2, random_state=42)

print("=" * 55)
print("MODEL 1: Random Forest — Spoilage Classification")
print("=" * 55)
rf_clf = RandomForestClassifier(n_estimators=200, max_depth=12,
                                 min_samples_split=5, random_state=42, n_jobs=-1)
rf_clf.fit(X_train, yc_train)
yc_pred = rf_clf.predict(X_test)
acc = accuracy_score(yc_test, yc_pred)
cv_scores = cross_val_score(rf_clf, X, y_class, cv=5)
print(f"Accuracy:        {acc*100:.2f}%")
print(f"Cross-val mean:  {cv_scores.mean()*100:.2f}% ± {cv_scores.std()*100:.2f}%")
print("\nClassification Report:")
print(classification_report(yc_test, yc_pred, target_names=['Not Spoiled','Spoiled']))

print("=" * 55)
print("MODEL 2: Gradient Boosting — Spoilage Probability")
print("=" * 55)
gb_reg = GradientBoostingRegressor(n_estimators=200, learning_rate=0.05,
                                    max_depth=5, random_state=42)
gb_reg.fit(X_train, yr_train)
yr_pred = gb_reg.predict(X_test)
yr_pred = np.clip(yr_pred, 0, 1)
mae = mean_absolute_error(yr_test, yr_pred)
r2  = r2_score(yr_test, yr_pred)
print(f"MAE:   {mae:.4f}  ({mae*100:.2f}% avg error)")
print(f"R²:    {r2:.4f}")

print("=" * 55)
print("MODEL 3: Random Forest — Risk Level (Low/Med/High)")
print("=" * 55)
rf_risk = RandomForestClassifier(n_estimators=150, max_depth=10, random_state=42, n_jobs=-1)
rf_risk.fit(X_train, yrisk_train)
yrisk_pred = rf_risk.predict(X_test)
risk_acc = accuracy_score(yrisk_test, yrisk_pred)
print(f"Accuracy: {risk_acc*100:.2f}%")
print(classification_report(yrisk_test, yrisk_pred,
      target_names=le_risk.classes_))

# ── Feature importances ──
print("=" * 55)
print("Feature Importances (Random Forest Classifier)")
print("=" * 55)
importances = rf_clf.feature_importances_
for feat, imp in sorted(zip(FEATURES, importances), key=lambda x: -x[1]):
    bar = '█' * int(imp * 50)
    print(f"  {feat:<25} {imp:.4f}  {bar}")

# ── Save models and encoders ──
os.makedirs('models', exist_ok=True)
joblib.dump(rf_clf,   'models/rf_classifier.pkl')
joblib.dump(gb_reg,   'models/gb_regressor.pkl')
joblib.dump(rf_risk,  'models/rf_risk.pkl')
joblib.dump(le_food,  'models/le_food.pkl')
joblib.dump(le_vehicle,'models/le_vehicle.pkl')
joblib.dump(le_tod,   'models/le_tod.pkl')
joblib.dump(le_risk,  'models/le_risk.pkl')

# Save metadata
meta = {
    'features': FEATURES,
    'food_classes': list(le_food.classes_),
    'vehicle_classes': list(le_vehicle.classes_),
    'tod_classes': list(le_tod.classes_),
    'risk_classes': list(le_risk.classes_),
    'classifier_accuracy': round(acc, 4),
    'regressor_mae': round(mae, 4),
    'regressor_r2': round(r2, 4),
    'risk_accuracy': round(risk_acc, 4),
    'training_samples': len(X_train),
    'test_samples': len(X_test)
}
with open('models/metadata.json', 'w') as f:
    json.dump(meta, f, indent=2)

print("\n✅ All models saved to /models/")
print(json.dumps(meta, indent=2))
