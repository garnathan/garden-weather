import asyncio, struct
from bleak import BleakClient, BleakScanner

ADDR = "40:79:12:AE:69:6B"
SVC  = "ef090000-11d6-42ba-93b8-9dd7ec090ab0"

async def main():
    print(f"Scanning for {ADDR}...")
    dev = await BleakScanner.find_device_by_address(ADDR, timeout=20)
    if not dev:
        print("NOT FOUND in scan"); return
    print(f"Found {dev.address}. Connecting (GATT)...")
    async with BleakClient(dev, timeout=30) as c:
        print(f"CONNECTED: {c.is_connected}\n")
        print("=== FULL GATT TABLE ===")
        for svc in c.services:
            print(f"[service] {svc.uuid}  ({svc.description})")
            for ch in svc.characteristics:
                print(f"   [char] {ch.uuid}  props={ch.properties}")
        print("\n=== READ SENSORPUSH DATA CHARS (write-trigger then read, int32/100) ===")
        svc = c.services.get_service(SVC)
        if not svc:
            print("SensorPush service not present"); return
        labels = {"80": "temperature (C)", "81": "humidity (%)", "82": "pressure"}
        for ch in svc.characteristics:
            props = ch.properties
            tag = next((v for k, v in labels.items() if ch.uuid[6:8] == k), "")
            try:
                if "write" in props or "write-without-response" in props:
                    await c.write_gatt_char(ch.uuid, struct.pack("<i", 1),
                                            response=("write" in props))
                    await asyncio.sleep(0.15)
                if "read" in props:
                    raw = await c.read_gatt_char(ch.uuid)
                    if len(raw) >= 4:
                        v = struct.unpack("<i", raw[:4])[0]
                        print(f"   {ch.uuid} {tag:<16} raw={raw.hex()} int32={v} /100={v/100}")
                    else:
                        print(f"   {ch.uuid} {tag:<16} raw={raw.hex()} (short)")
            except Exception as e:
                print(f"   {ch.uuid} {tag:<16} ERR {type(e).__name__}: {e}")

asyncio.run(main())
