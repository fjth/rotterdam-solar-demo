#!/usr/bin/env python3
import os
import random
import pandas as pd
import pytz
import pvlib
import requests

# Fetch current weather data from WeatherAPI.com based on coordinates
def fetch_current_weather(lat, lon, api_key):
    url = f"http://api.weatherapi.com/v1/current.json?key={api_key}&q={lat},{lon}&aqi=no"
    resp = requests.get(url)
    resp.raise_for_status()
    current = resp.json()['current']
    return {
        'temp_c': current['temp_c'],
        'humidity': current['humidity'],
        'cloud_pct': current['cloud'],
        'precip_mm': current['precip_mm'],
        'condition': current['condition']['text']
    }


def simulate_and_send():
    # 1) Timestamp
    tz = 'Europe/Amsterdam'
    now = pd.Timestamp.now(tz=pytz.timezone(tz))
    timestamp = now.isoformat()

    # 2) Clear-sky irradiance for solar simulation at updated coordinates
    latitude, longitude = 51.90187, 4.487495
    loc = pvlib.location.Location(latitude, longitude, tz)
    clearsky = loc.get_clearsky(pd.DatetimeIndex([now]))
    ghi_clear = clearsky['ghi'].iloc[0]

    # 3) Fetch simple current weather
    weather_api_key = os.environ.get('WEATHERAPI_KEY')
    weather = fetch_current_weather(latitude, longitude, weather_api_key)

    # 4) Effective irradiance
    cloud_frac = weather['cloud_pct'] / 100.0
    ghi_effective = ghi_clear * (1 - 0.75 * cloud_frac)

    # 5) Simulate multiple panels with slight variance
    num_panels = 8
    panel_area = 1.6   # m² per panel
    efficiency = 0.18  # 18%
    power_per_panel = ghi_effective * panel_area * efficiency

    measurements = []
    for i in range(1, num_panels + 1):
        # Apply a random +/-5% variance per panel
        variation = random.uniform(0.95, 1.05)
        power_varied = round(power_per_panel * variation, 1)
        measurements.append({
            'subject_id': f'panel_{i}',
            'power_w': power_varied
        })

    # 6) Build payload
    payload = {
        'building_id': 'fenix-i',
        'sensor_type': 'solar_panel',
        'timestamp': timestamp,
        'weather': weather,
        'measurements': measurements
    }

    # 7) Send to Blockbax
    url = os.environ.get('INBOUND_URL')
    api_key = os.environ.get('INBOUND_API_KEY')
    headers = {'Content-Type': 'application/json', 'Authorization': f'ApiKey {api_key}'}
    response = requests.post(url, json=payload, headers=headers)
    print(f"{timestamp} → {response.status_code} {response.text}")

if __name__ == '__main__':
    simulate_and_send()
