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
    cond = current['condition']
    # Construct 128x128 icon URL by replacing size in the default icon path
    icon_path = cond['icon']  # e.g. "//cdn.weatherapi.com/weather/64x64/day/113.png"
    icon_url = 'https:' + icon_path.replace('/64x64/', '/128x128/')
    return {
        'temp_c': current['temp_c'],
        'humidity': current['humidity'],
        'cloud_pct': current['cloud'],
        'precip_mm': current['precip_mm'],
        'condition': cond['text'],
        'icon_url': icon_url
    }


def simulate_and_send():
    # 1) Timestamp
    tz = 'Europe/Amsterdam'
    now = pd.Timestamp.now(tz=pytz.timezone(tz))
    timestamp = now.isoformat()

    # 2) Solar irradiance at location
    latitude, longitude = 51.90187, 4.487495
    loc = pvlib.location.Location(latitude, longitude, tz)
    clearsky = loc.get_clearsky(pd.DatetimeIndex([now]))
    ghi_clear = clearsky['ghi'].iloc[0]

    # 3) Fetch weather including resized icon URL
    weather_api_key = os.environ.get('WEATHERAPI_KEY')
    weather_full = fetch_current_weather(latitude, longitude, weather_api_key)
    icon_url = weather_full.pop('icon_url')  # remove from payload

    # 4) Effective irradiance
    cloud_frac = weather_full['cloud_pct'] / 100.0
    ghi_effective = ghi_clear * (1 - 0.75 * cloud_frac)

    # 5) Simulate inverters
    num_inverters = 8
    panel_area = 1.6   # m² per unit
    efficiency = 0.18  # 18%
    base_power = ghi_effective * panel_area * efficiency

    measurements = []
    for i in range(1, num_inverters + 1):
        variation = random.uniform(0.95, 1.05)
        measurements.append({
            'subject_id': f'inverter_{i}',
            'power_w': round(base_power * variation, 1)
        })

    # Aggregate total inverter power for the building-level measurement
    total_power = sum(m['power_w'] for m in measurements)
    measurements.append({
        'subject_id': 'fenix-i',
        'power_w': round(total_power, 1)
    })

    # 6) Build payload
    payload = {
        'building_id': 'fenix-i',
        'sensor_type': 'solar_inverter',
        'timestamp': timestamp,
        'weather': weather_full,
        'measurements': measurements
    }

    # 7) Inbound POST
    inbound_url = os.environ.get('INBOUND_URL')
    api_key = os.environ.get('INBOUND_API_KEY')
    headers = {'Content-Type': 'application/json', 'Authorization': f'ApiKey {api_key}'}
    resp_post = requests.post(inbound_url, json=payload, headers=headers)
    print(f"Inbound POST {timestamp} → {resp_post.status_code}")

    # 8) PATCH icon property separately
    property_url = os.environ.get('BLOCKBAX_PROPERTY_URL')
    if property_url and icon_url:
        patch_payload = {
            'values': {
                'f62e7be1-4e81-43fb-85fb-1fdfc7c3fe0f': {
                    'text': icon_url
                }
            }
        }
        resp_patch = requests.patch(property_url, json=patch_payload, headers=headers)
        print(f"Property PATCH {timestamp} → {resp_patch.status_code}")

if __name__ == '__main__':
    simulate_and_send()