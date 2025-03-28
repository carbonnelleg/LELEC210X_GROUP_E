import requests
import json

url = 'http://localhost:8000'

data = {
    "current_class_names": ["chainsaw", "fire", "fireworks", "gun"],
    "current_class_probas": [0.1, 0.3, 0.4, 0.2],
    "current_feature_vector": [[0.1] * 20] * 20,
    "current_packet_data": "00" * (12 + 800 + 16),
    "current_choice": "fire"
}

response = requests.post(url, json=data)
print(response.status_code)
