#!/usr/bin/env python3
import os
import random
import requests
import pandas as pd
import pytz

# 1) Fetch room subjects by type and extract internal->external ID map
def get_room_subjects():
    subjects_url = os.environ['SUBJECTS_URL']
    headers = {'Authorization': f"ApiKey {os.environ['INBOUND_API_KEY']}"}
    params = {'subjectTypeIds': os.environ['ROOM_SUBJECTTYPEID']}
    resp = requests.get(subjects_url, headers=headers, params=params)
    resp.raise_for_status()
    data = resp.json().get('result', resp.json().get('data', []))
    return {item['id']: item['externalId'] for item in data}

# 2) Fetch latest occupancy measurements using the /measurements endpoint
#    Returns a dict: internal ID -> rounded occupancy number
def get_latest_occupancy(internal_ids):
    meas_url = os.environ['MEASUREMENTS_URL']
    headers = {'Authorization': f"ApiKey {os.environ['INBOUND_API_KEY']}"}
    params = []
    for sid in internal_ids:
        params.append(('subjectIds', sid))
    for mid in os.environ['OCCUPANCY_METRICID'].split(','):
        params.append(('metricIds', mid))
    resp = requests.get(meas_url, headers=headers, params=params)
    resp.raise_for_status()
    series = resp.json().get('series', [])
    occ_map = {}
    for entry in series:
        sid = entry.get('subjectId')
        measurements = entry.get('measurements', [])
        if measurements:
            occ_map[sid] = round(measurements[0].get('number', 0))
    return occ_map

# 3) Simulate and send payload
def simulate_and_send():
    tz = 'Europe/Amsterdam'
    now = pd.Timestamp.now(tz=pytz.timezone(tz)).isoformat()

    # Fetch subjects and occupancy
    id_to_external = get_room_subjects()
    internal_ids = list(id_to_external.keys())
    occ_map = get_latest_occupancy(internal_ids)

    # Build measurements array (no per-item timestamps)
    measurements = []
    for internal_id, occ in occ_map.items():
        external_id = id_to_external.get(internal_id)
        if not external_id:
            continue
        base_power = 100.0                # W per room
        base_gas = 0.05                   # cubic meters per occupant
        base_water = 5.0                  # liters per occupant

        variation_power = random.uniform(0.8, 1.2)  # ±20%
        variation_gas = random.uniform(0.8, 1.2)
        variation_water = random.uniform(0.8, 1.2)

        power_w = round(base_power * occ * variation_power, 1)
        gas_m3 = round(base_gas * occ * variation_gas, 3)
        water_l = round(base_water * occ * variation_water, 1)

        measurements.append({
            'subject_id': external_id,
            'power_w': power_w,
            'gas_m3': gas_m3,
            'water_l': water_l
        })

    # Log summary of generated metrics
    print(f"Generated {len(measurements)} room usage entries")

    # Final payload with single timestamp
    payload = {
        'building_id': os.environ.get('BUILDING_ID', 'fenix-i'),
        'sensor_type': 'room_power',
        'timestamp': now,
        'measurements': measurements
    }

    # POST to measurements endpoint
    post_url = os.environ['MEASUREMENTS_POST_URL']
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"ApiKey {os.environ['INBOUND_API_KEY']}"
    }
    resp = requests.post(post_url, json=payload, headers=headers)
    print(f"Measurements POST → {resp.status_code}")

if __name__ == '__main__':
    simulate_and_send()