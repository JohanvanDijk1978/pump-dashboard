import os
from dotenv import load_dotenv
import requests

load_dotenv()

PRIVATE_KEY = os.getenv("PUMP_PRIVATE_KEY")
assert PRIVATE_KEY, "No PUMP_PRIVATE_KEY in .env"

files = {
    "private_key": (None, PRIVATE_KEY),
    "amount": (None, "0.1"),
    "name": (None, "TestFromScript"),
    "symbol": (None, "TST"),
    "description": (None, "Test token from script"),
}

resp = requests.post(
    "https://api.pumpfunapi.org/pumpfun/create/token",
    files=files,
    timeout=60,
    headers={"User-Agent": "pump-dashboard-test/1.0"},
)

print("Status:", resp.status_code)
print("Raw:", resp.text[:500])

try:
    print("JSON:", resp.json())
except Exception as e:
    print("JSON parse failed:", e)
