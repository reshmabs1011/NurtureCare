
import requests

url = "http://127.0.0.1:5000/api/ml-demo"

data = {
    "age": 25,
    "systolic": 120,
    "diastolic": 80,
    "bs": 7.5,
    "bodytemp": 98.6,
    "heartrate": 76
}

response = requests.post(url, json=data)

print("Status code:", response.status_code)
print("Response:", response.json())
