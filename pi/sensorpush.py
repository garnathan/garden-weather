#!/usr/bin/env python3
"""Read SensorPush HTP.xw (garden) over BLE and match the SensorPush app 1:1.

Reports station + sea-level pressure (from the app's 50 m altitude setting),
plus computed dew point & heat index (the app derives those from temp+humidity;
they are not sensor channels).

Usage: sensorpush.py [--json] [--watch N]
"""
import asyncio, struct, json, sys, time, math
from bleak import BleakClient, BleakScanner

ADDR = "40:79:12:AE:69:6B"                       # SensorPush HTP.xw 96B
CH_TEMP     = "ef090080-11d6-42ba-93b8-9dd7ec090aa9"
CH_HUMIDITY = "ef090081-11d6-42ba-93b8-9dd7ec090aa9"
CH_PRESSURE = "ef090082-11d6-42ba-93b8-9dd7ec090aa9"

ALTITUDE_M = 50.0            # matches the altitude set in the SensorPush app

def sealevel_pressure(station_mbar, t_c):
    """Temperature-compensated barometric reduction to sea level (the app's method)."""
    h = ALTITUDE_M
    return station_mbar * (1 + (0.0065 * h) / (t_c + 0.0065 * h + 273.15)) ** 5.257

def dew_point_c(t, rh):
    a, b = 17.625, 243.04
    g = math.log(max(rh, 0.01) / 100.0) + a * t / (b + t)
    return b * g / (a - g)

def heat_index_c(t_c, rh):
    t = t_c * 9 / 5 + 32                          # NWS formula works in °F
    if t < 80:                                    # below ~26.7°C HI ≈ air temp
        return t_c
    hi = (-42.379 + 2.04901523*t + 10.14333127*rh - 0.22475541*t*rh
          - 6.83783e-3*t*t - 5.481717e-2*rh*rh + 1.22874e-3*t*t*rh
          + 8.5282e-4*t*rh*rh - 1.99e-6*t*t*rh*rh)
    return (hi - 32) * 5 / 9

async def _read_i32(client, uuid):
    await client.write_gatt_char(uuid, struct.pack("<i", 1), response=True)
    await asyncio.sleep(0.15)
    raw = await client.read_gatt_char(uuid)
    return struct.unpack("<i", raw[:4])[0]

async def read_once():
    dev = await BleakScanner.find_device_by_address(ADDR, timeout=20)
    if not dev:
        raise RuntimeError(f"SensorPush {ADDR} not found in BLE scan")
    async with BleakClient(dev, timeout=30) as c:
        t = await _read_i32(c, CH_TEMP)     / 100.0
        h = await _read_i32(c, CH_HUMIDITY) / 100.0
        p = await _read_i32(c, CH_PRESSURE) / 100.0     # Pascals (station)
    station = p / 100.0                                  # mbar
    return {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "temperature_c": round(t, 2),
        "temperature_f": round(t * 9 / 5 + 32, 2),
        "humidity_pct": round(h, 2),
        "pressure_station_mbar": round(station, 2),
        "pressure_sealevel_mbar": round(sealevel_pressure(station, t), 2),
        "dew_point_c": round(dew_point_c(t, h), 1),
        "heat_index_c": round(heat_index_c(t, h), 1),
    }

def render(d, as_json):
    if as_json:
        print(json.dumps(d), flush=True); return
    print(f"[{d['ts']}]  SensorPush HTP.xw — garden")
    print(f"   Temperature : {d['temperature_c']} °C  ({d['temperature_f']} °F)")
    print(f"   Humidity    : {d['humidity_pct']} %")
    print(f"   Pressure    : {d['pressure_sealevel_mbar']} mb (sea-level @ {ALTITUDE_M:.0f} m)"
          f"  [{d['pressure_station_mbar']} mb station]")
    print(f"   Dew point   : {d['dew_point_c']} °C")
    print(f"   Heat index  : {d['heat_index_c']} °C", flush=True)

async def main():
    as_json = "--json" in sys.argv
    watch = int(sys.argv[sys.argv.index("--watch") + 1]) if "--watch" in sys.argv else 0
    while True:
        try:
            render(await read_once(), as_json)
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        if not watch:
            break
        await asyncio.sleep(watch)

if __name__ == "__main__":
    asyncio.run(main())
