import pandas as pd
import numpy as np
import os

np.random.seed(42)
N = 5000

food_types = ['Milk', 'Meat', 'Fish', 'Vegetables', 'Fruits', 'Dairy', 'Eggs']
vehicle_types = ['Normal Truck', 'Refrigerated Truck', 'Frozen Container']
time_of_day = ['morning', 'afternoon', 'evening', 'night']

# Food sensitivity scores (higher = more perishable)
food_sensitivity = {'Fish': 0.95, 'Meat': 0.90, 'Milk': 0.80, 'Dairy': 0.70, 'Eggs': 0.60, 'Vegetables': 0.50, 'Fruits': 0.40}
# Vehicle cooling efficiency (higher = better cooling)
vehicle_efficiency = {'Normal Truck': 0.0, 'Refrigerated Truck': 0.75, 'Frozen Container': 0.95}
# Required temp ranges
food_temp_req = {'Fish': (0,2), 'Meat': (-2,2), 'Milk': (2,4), 'Dairy': (2,6), 'Eggs': (2,5), 'Vegetables': (4,8), 'Fruits': (5,10)}
# Vehicle temp capability
vehicle_temp_cap = {'Normal Truck': (15,40), 'Refrigerated Truck': (2,8), 'Frozen Container': (-10,5)}

records = []
for _ in range(N):
    food = np.random.choice(food_types)
    vehicle = np.random.choice(vehicle_types)
    tod = np.random.choice(time_of_day)
    
    travel_hours = np.random.uniform(2, 30)
    ambient_temp = np.random.uniform(18, 45) if tod in ['afternoon', 'morning'] else np.random.uniform(15, 30)
    humidity = np.random.uniform(40, 95)
    quantity = np.random.randint(50, 1000)
    
    # Vehicle compatible?
    req_min, req_max = food_temp_req[food]
    veh_min, veh_max = vehicle_temp_cap[vehicle]
    compatible = (veh_min <= req_max) and (veh_max >= req_min)
    
    # Container temp achieved
    if vehicle == 'Normal Truck':
        container_temp = ambient_temp * 0.95
    elif vehicle == 'Refrigerated Truck':
        container_temp = np.random.uniform(2, 8)
    else:
        container_temp = np.random.uniform(-5, 5)
    
    # Temp deviation from ideal
    ideal_temp = (req_min + req_max) / 2
    temp_deviation = abs(container_temp - ideal_temp)
    
    # Compute spoilage probability (ground truth label)
    fs = food_sensitivity[food]
    ve = vehicle_efficiency[vehicle]
    
    base = fs * 0.3
    time_factor = min(travel_hours / 24, 1.0) * 0.25
    temp_factor = min(temp_deviation / 20, 1.0) * 0.25
    humidity_factor = (humidity / 100) * 0.10
    vehicle_factor = (1 - ve) * 0.10
    compat_penalty = 0.15 if not compatible else 0.0
    
    prob = base + time_factor + temp_factor + humidity_factor + vehicle_factor + compat_penalty
    prob = min(max(prob + np.random.normal(0, 0.04), 0.0), 1.0)
    
    # Binary spoilage label (threshold 0.5)
    spoiled = int(prob >= 0.5)
    
    # Risk level
    if prob < 0.3:
        risk_level = 'Low'
    elif prob < 0.6:
        risk_level = 'Medium'
    else:
        risk_level = 'High'
    
    records.append({
        'food_type': food,
        'vehicle_type': vehicle,
        'time_of_day': tod,
        'travel_hours': round(travel_hours, 2),
        'ambient_temp_c': round(ambient_temp, 2),
        'humidity_pct': round(humidity, 2),
        'container_temp_c': round(container_temp, 2),
        'quantity': quantity,
        'vehicle_compatible': int(compatible),
        'temp_deviation': round(temp_deviation, 2),
        'food_sensitivity': fs,
        'vehicle_efficiency': ve,
        'spoilage_probability': round(prob, 4),
        'spoiled': spoiled,
        'risk_level': risk_level
    })

df = pd.DataFrame(records)
os.makedirs('data', exist_ok=True)
df.to_csv('data/shipment_dataset.csv', index=False)
print(f"Dataset generated: {len(df)} records")
print(df['risk_level'].value_counts())
print(df['spoiled'].value_counts())
print(df.head(3))
