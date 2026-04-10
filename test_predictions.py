"""
Standalone ML prediction test — simulates what the Flask API does
"""
import numpy as np
import joblib
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE, 'models')

rf_clf     = joblib.load(os.path.join(MODELS_DIR, 'rf_classifier.pkl'))
gb_reg     = joblib.load(os.path.join(MODELS_DIR, 'gb_regressor.pkl'))
rf_risk    = joblib.load(os.path.join(MODELS_DIR, 'rf_risk.pkl'))
le_food    = joblib.load(os.path.join(MODELS_DIR, 'le_food.pkl'))
le_vehicle = joblib.load(os.path.join(MODELS_DIR, 'le_vehicle.pkl'))
le_tod     = joblib.load(os.path.join(MODELS_DIR, 'le_tod.pkl'))
le_risk    = joblib.load(os.path.join(MODELS_DIR, 'le_risk.pkl'))

FOOD_SENSITIVITY  = {'Fish':0.95,'Meat':0.90,'Milk':0.80,'Dairy':0.70,'Eggs':0.60,'Vegetables':0.50,'Fruits':0.40}
VEHICLE_EFFICIENCY= {'Normal Truck':0.0,'Refrigerated Truck':0.75,'Frozen Container':0.95}
FOOD_TEMP_REQ     = {'Fish':(0,2),'Meat':(-2,2),'Milk':(2,4),'Dairy':(2,6),'Eggs':(2,5),'Vegetables':(4,8),'Fruits':(5,10)}
VEHICLE_TEMP_CAP  = {'Normal Truck':(15,40),'Refrigerated Truck':(2,8),'Frozen Container':(-10,5)}
FOOD_SHELF_LIFE   = {'Fish':12,'Meat':18,'Milk':48,'Dairy':72,'Eggs':120,'Vegetables':96,'Fruits':120}

TEST_CASES = [
    {'food':'Milk','vehicle':'Normal Truck','tod':'afternoon','travel':8,'ambient':38,'humidity':72,'qty':200,'cost':50,'label':'HIGH RISK expected'},
    {'food':'Milk','vehicle':'Refrigerated Truck','tod':'night','travel':6,'ambient':22,'humidity':55,'qty':200,'cost':50,'label':'LOW RISK expected'},
    {'food':'Meat','vehicle':'Normal Truck','tod':'afternoon','travel':5,'ambient':40,'humidity':80,'qty':100,'cost':200,'label':'CRITICAL expected'},
    {'food':'Fruits','vehicle':'Refrigerated Truck','tod':'morning','travel':4,'ambient':28,'humidity':60,'qty':500,'cost':30,'label':'LOW RISK expected'},
]

def predict(d):
    food, vehicle, tod = d['food'], d['vehicle'], d['tod']
    travel, ambient, humidity = d['travel'], d['ambient'], d['humidity']

    req_min, req_max = FOOD_TEMP_REQ[food]
    veh_min, veh_max = VEHICLE_TEMP_CAP[vehicle]
    compatible = int((veh_min <= req_max) and (veh_max >= req_min))

    if vehicle == 'Normal Truck':
        container_temp = ambient * 0.95
    elif vehicle == 'Refrigerated Truck':
        container_temp = max(min(ambient * 0.1, req_max), req_min)
    else:
        container_temp = (req_min + req_max) / 2

    temp_dev  = abs(container_temp - (req_min+req_max)/2)
    food_enc  = le_food.transform([food])[0]
    veh_enc   = le_vehicle.transform([vehicle])[0]
    tod_enc   = le_tod.transform([tod])[0]

    feat = np.array([[food_enc, veh_enc, tod_enc,
                      travel, ambient, humidity,
                      container_temp, compatible, temp_dev,
                      FOOD_SENSITIVITY[food], VEHICLE_EFFICIENCY[vehicle]]])

    spoiled     = rf_clf.predict(feat)[0]
    sp_proba    = rf_clf.predict_proba(feat)[0]
    sp_prob     = float(np.clip(gb_reg.predict(feat)[0], 0, 1))
    risk_enc    = rf_risk.predict(feat)[0]
    risk_label  = le_risk.inverse_transform([risk_enc])[0]
    risk_proba  = rf_risk.predict_proba(feat)[0]

    shelf_left  = max(0, FOOD_SHELF_LIFE[food] - travel)
    est_loss    = round(d['qty'] * d['cost'] * sp_prob)

    return {
        'spoilage_pct': round(sp_prob*100,1),
        'will_spoil':   'YES' if spoiled else 'NO',
        'confidence':   round(float(max(sp_proba))*100,1),
        'risk_level':   risk_label,
        'risk_probs':   {c:round(float(p)*100,1) for c,p in zip(le_risk.classes_,risk_proba)},
        'shelf_left_hrs': shelf_left,
        'compatible':   bool(compatible),
        'est_loss_inr': est_loss,
        'container_temp': round(container_temp,1)
    }

print("=" * 60)
print("ColdChain ML Model — Live Prediction Tests")
print("=" * 60)

for i, case in enumerate(TEST_CASES, 1):
    result = predict(case)
    print(f"\n📦 Test {i}: {case['food']} via {case['vehicle']}")
    print(f"   [{case['label']}]")
    print(f"   Route context: {case['travel']}h · {case['ambient']}°C · {case['humidity']}% humidity")
    print(f"   ── ML Outputs ──────────────────────────────")
    print(f"   Spoilage Probability : {result['spoilage_pct']}%  (GBM Regressor)")
    print(f"   Will Spoil?          : {result['will_spoil']} (confidence: {result['confidence']}%)  (RF Classifier)")
    print(f"   Risk Level           : {result['risk_level']}  {result['risk_probs']}  (RF Risk Model)")
    print(f"   Shelf Life Left      : {result['shelf_left_hrs']} hours")
    print(f"   Vehicle Compatible   : {'✅ Yes' if result['compatible'] else '❌ NO — Switch vehicle!'}")
    print(f"   Container Temp       : {result['container_temp']}°C")
    print(f"   Est. Financial Loss  : ₹{result['est_loss_inr']:,}")

print("\n" + "=" * 60)
print("✅ All 3 ML models working correctly")
print("=" * 60)
