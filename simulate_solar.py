#!/usr/bin/env python3
import os
import pandas as pd
import pytz
import pvlib
import requests

def simulate_and_send():
    # 1) Timestamp
    tz = 'Europe/Amsterdam'
    now = pd.Timestamp.now(tz=pytz.timezone(tz))
    timestamp = now.isoformat()

    # 2) Clear-sky irradiance for Rotterdam
    latitude, longitude = 51.9244, 4.4777
    loc = pvlib.location.Location(latitude, longitude, tz)
    times = pd.DatetimeIndex([now])
    clearsky = loc.get_clearsky(times)

    # 3) Generic panel: GHI × area × efficiency
    ghi = clearsky['ghi'].iloc[0]           # W/m²
    panel_area = 50.0                       # m²
    efficiency = 0.18                       # 18%
    ac_power = ghi * panel_area * efficiency

    # 4) Build payload
    payload = {
        "building_id": "demo-building",
        "sensor_type": "solar_panel",
        "timestamp": timestamp,
        "power_w": round(ac_power, 1)
    }

    # 5) POST to Blockbax
    url = os.environ.get('INBOUND_URL')
    api_key = os.environ.get('INBOUND_API_KEY')
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"ApiKey {api_key}"
    }
    response = requests.post(url, json=payload, headers=headers)
    print(f"{timestamp} → {response.status_code} {response.text}")

if __name__ == "__main__":
    simulate_and_send()