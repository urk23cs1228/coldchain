"""
ColdChain AI — Flask ML Backend
Fixed: sklearn feature name warnings resolved using pd.DataFrame with named columns
Run: python api/app.py
"""

from flask import Flask, request, jsonify, make_response
import numpy as np
import pandas as pd
import joblib
import json
import os
import warnings

# Suppress any residual sklearn warnings after the fix
warnings.filterwarnings('ignore', category=UserWarning, module='sklearn')

app = Flask(__name__)

# ── Load models ──────────────────────────────────────────────
BASE       = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE, '..', 'models')

rf_clf     = joblib.load(os.path.join(MODELS_DIR, 'rf_classifier.pkl'))
gb_reg     = joblib.load(os.path.join(MODELS_DIR, 'gb_regressor.pkl'))
rf_risk    = joblib.load(os.path.join(MODELS_DIR, 'rf_risk.pkl'))
le_food    = joblib.load(os.path.join(MODELS_DIR, 'le_food.pkl'))
le_vehicle = joblib.load(os.path.join(MODELS_DIR, 'le_vehicle.pkl'))
le_tod     = joblib.load(os.path.join(MODELS_DIR, 'le_tod.pkl'))
le_risk    = joblib.load(os.path.join(MODELS_DIR, 'le_risk.pkl'))

with open(os.path.join(MODELS_DIR, 'metadata.json')) as f:
    META = json.load(f)

# Feature column names — must match what models were trained with
FEATURE_COLS = META['features']

# ── Knowledge base ────────────────────────────────────────────
FOOD_SENSITIVITY  = {'Fish':0.95,'Meat':0.90,'Milk':0.80,'Dairy':0.70,'Eggs':0.60,'Vegetables':0.50,'Fruits':0.40}
VEHICLE_EFFICIENCY= {'Normal Truck':0.0,'Refrigerated Truck':0.75,'Frozen Container':0.95}
FOOD_TEMP_REQ     = {'Fish':(0,2),'Meat':(-2,2),'Milk':(2,4),'Dairy':(2,6),'Eggs':(2,5),'Vegetables':(4,8),'Fruits':(5,10)}
VEHICLE_TEMP_CAP  = {'Normal Truck':(15,40),'Refrigerated Truck':(2,8),'Frozen Container':(-10,5)}
FOOD_SHELF_LIFE   = {'Fish':12,'Meat':18,'Milk':48,'Dairy':72,'Eggs':120,'Vegetables':96,'Fruits':120}

# ── CORS — allow ALL origins (file://, localhost, any port) ───
def cors_headers(response):
    response.headers['Access-Control-Allow-Origin']  = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Accept'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

@app.after_request
def after_request(response):
    return cors_headers(response)

@app.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        resp = make_response('', 204)
        resp.headers['Access-Control-Allow-Origin']  = '*'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Accept'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        return resp

# ── Routes ────────────────────────────────────────────────────
@app.route('/', methods=['GET'])
def index():
    return jsonify({
        'status': 'ColdChain ML API running',
        'port': 5000,
        'models': {
            'classifier': f"{META['classifier_accuracy']*100:.1f}% accuracy",
            'regressor':  f"R2={META['regressor_r2']:.4f}, MAE={META['regressor_mae']:.4f}",
            'risk_model': f"{META['risk_accuracy']*100:.1f}% accuracy"
        },
        'training_samples': META['training_samples']
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

@app.route('/predict', methods=['POST', 'OPTIONS'])
def predict():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'error': 'No JSON body received'}), 400

    try:
        food    = data.get('food_type', 'Milk')
        vehicle = data.get('vehicle_type', 'Refrigerated Truck')
        tod     = data.get('time_of_day', 'afternoon')
        travel  = float(data.get('travel_hours', 10))
        ambient = float(data.get('ambient_temp_c', 35))
        humidity= float(data.get('humidity_pct', 65))
        qty     = int(data.get('quantity', 200))
        cost    = float(data.get('cost_per_unit', 50))

        # Validate
        if food not in FOOD_SENSITIVITY:
            return jsonify({'error': f'Unknown food type: {food}. Use one of: {list(FOOD_SENSITIVITY.keys())}'}), 400
        if vehicle not in VEHICLE_EFFICIENCY:
            return jsonify({'error': f'Unknown vehicle: {vehicle}. Use one of: {list(VEHICLE_EFFICIENCY.keys())}'}), 400

        # Derive features
        req_min, req_max = FOOD_TEMP_REQ[food]
        veh_min, veh_max = VEHICLE_TEMP_CAP[vehicle]
        compatible = int((veh_min <= req_max) and (veh_max >= req_min))

        if vehicle == 'Normal Truck':
            container_temp = ambient * 0.95
        elif vehicle == 'Refrigerated Truck':
            container_temp = max(min(ambient * 0.1, req_max), req_min)
        else:
            container_temp = (req_min + req_max) / 2

        temp_dev  = abs(container_temp - (req_min + req_max) / 2)
        food_sens = FOOD_SENSITIVITY[food]
        veh_eff   = VEHICLE_EFFICIENCY[vehicle]

        # Encode labels
        food_enc    = le_food.transform([food])[0]
        vehicle_enc = le_vehicle.transform([vehicle])[0]
        tod_enc     = le_tod.transform([tod])[0]

        # ── FIX: wrap in DataFrame with named columns to match training ──
        features = pd.DataFrame([[
            food_enc, vehicle_enc, tod_enc,
            travel, ambient, humidity,
            container_temp, compatible, temp_dev,
            food_sens, veh_eff
        ]], columns=FEATURE_COLS)

        # ── Run all 3 ML models ──
        spoiled_pred  = int(rf_clf.predict(features)[0])
        spoiled_proba = rf_clf.predict_proba(features)[0]
        spoiled_conf  = round(float(max(spoiled_proba)) * 100, 1)

        sp_prob      = float(np.clip(gb_reg.predict(features)[0], 0, 1))
        risk_enc     = int(rf_risk.predict(features)[0])
        risk_label   = le_risk.inverse_transform([risk_enc])[0]
        risk_proba   = rf_risk.predict_proba(features)[0]

        # ── Compute outputs ──
        spoilage_pct = round(sp_prob * 100, 1)
        risk_score   = min(int(spoilage_pct * 0.6 + (travel / 24) * 40), 100)
        shelf_left   = max(0, int(FOOD_SHELF_LIFE.get(food, 48) - travel))
        est_loss     = round(qty * cost * sp_prob)
        cold_stop    = travel > 12 or spoilage_pct > 50
        rec_temp     = f"{req_min}°C – {req_max}°C"
        dist_km      = round(travel * 65)

        if spoilage_pct > 60 or shelf_left < 6:
            priority = 'Critical'
        elif spoilage_pct > 35:
            priority = 'High'
        elif spoilage_pct > 15:
            priority = 'Medium'
        else:
            priority = 'Low'

        if compatible:
            veh_note = f"{vehicle} maintains {veh_min}°C to {veh_max}°C — within required range for {food}."
        else:
            veh_note = f"WARNING: {vehicle} cannot maintain {req_min}°C to {req_max}°C required for {food}. Switch vehicle immediately."

        return jsonify({
            'ml_predictions': {
                'model_1_classifier': {
                    'model': 'Random Forest Classifier',
                    'prediction': 'Will Spoil' if spoiled_pred else 'Safe',
                    'confidence': spoiled_conf,
                    'accuracy': f"{META['classifier_accuracy']*100:.1f}%"
                },
                'model_2_regressor': {
                    'model': 'Gradient Boosting Regressor',
                    'spoilage_probability_pct': spoilage_pct,
                    'r2_score': META['regressor_r2'],
                    'mae': META['regressor_mae']
                },
                'model_3_risk': {
                    'model': 'Random Forest Risk Classifier',
                    'risk_level': risk_label,
                    'risk_probabilities': {
                        cls: round(float(p) * 100, 1)
                        for cls, p in zip(le_risk.classes_, risk_proba)
                    },
                    'accuracy': f"{META['risk_accuracy']*100:.1f}%"
                }
            },
            'prediction_summary': {
                'spoilage_probability_pct': spoilage_pct,
                'risk_level': risk_label,
                'risk_score': risk_score,
                'recommended_container_temp': rec_temp,
                'shelf_life_remaining_hours': shelf_left,
                'delivery_priority': priority,
                'vehicle_compatible': bool(compatible),
                'vehicle_note': veh_note,
                'cold_stop_needed': cold_stop,
                'estimated_loss_inr': est_loss,
                'estimated_distance_km': dist_km,
                'container_temp_achieved_c': round(container_temp, 1)
            },
            'input_features': {
                'food_type': food, 'vehicle_type': vehicle,
                'time_of_day': tod, 'travel_hours': travel,
                'ambient_temp_c': ambient, 'humidity_pct': humidity, 'quantity': qty
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/model-info', methods=['GET'])
def model_info():
    return jsonify({
        'models_trained': 3,
        'dataset_size': META['training_samples'] + META['test_samples'],
        'algorithms': {
            'classifier':  'Random Forest (200 trees, max_depth=12)',
            'regressor':   'Gradient Boosting (200 estimators, lr=0.05)',
            'risk_model':  'Random Forest (150 trees, max_depth=10)'
        },
        'performance': {
            'classifier_accuracy': f"{META['classifier_accuracy']*100:.1f}%",
            'regressor_r2':        META['regressor_r2'],
            'regressor_mae':       f"{META['regressor_mae']*100:.2f}%",
            'risk_accuracy':       f"{META['risk_accuracy']*100:.1f}%"
        },
        'supported_foods':    META['food_classes'],
        'supported_vehicles': META['vehicle_classes']
    })


if __name__ == '__main__':
    print("\n" + "="*50)
    print("  ColdChain AI — ML Backend Starting")
    print("  URL: http://localhost:5000")
    print("  sklearn warnings: FIXED (using DataFrame with named columns)")
    print("  Keep this window open while using the app")
    print("="*50 + "\n")
    app.run(debug=False, host='0.0.0.0', port=5000)
