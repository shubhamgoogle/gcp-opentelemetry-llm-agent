import json
import urllib.request

url = "http://127.0.0.1:8001/run_sse"
payload = {
    "app_name": "otel_agent",
    "user_id": "user",
    "session_id": "test-session",
    "prompt": "Count the vowels in this sentence."
}
data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as response:
        print(f"Status Code: {response.getcode()}")
        print(f"Response: {response.read().decode('utf-8')}")
except Exception as e:
    print(f"Error: {e}")
