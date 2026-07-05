import asyncio, time
from bleak import BleakScanner
from sensorpush_ble.parser import decode_values, SENSORPUSH_DEVICE_TYPES

ADDR = "40:79:12:AE:69:6B"

def decode_all(md):
    rows = []
    for id_, payload in md.items():
        data = int(id_).to_bytes(2, "little") + payload
        page = data[0] & 0x03
        if page != 0:
            rows.append((id_, data.hex(), page, None)); continue
        dtid = 64 + (data[0] >> 2)
        vals = decode_values(data, dtid)
        pretty = {}
        for k, v in vals.items():
            dc = getattr(getattr(k, "device_class", None), "value", str(getattr(k, "device_class", k)))
            unit = getattr(k, "native_unit_of_measurement", "")
            pretty[str(dc)] = f"{v} {unit}".strip()
        rows.append((id_, data.hex(), page, (SENSORPUSH_DEVICE_TYPES.get(dtid, dtid), pretty)))
    return rows

count = 0
def cb(dev, adv):
    global count
    if dev.address.upper() != ADDR:
        return
    count += 1
    print(f"[{time.strftime('%H:%M:%S')}] rssi={adv.rssi} dBm")
    for id_, hexd, page, dec in decode_all(adv.manufacturer_data):
        if dec:
            print(f"   id={id_:#06x} PAGE0 {hexd}  -> {dec[0]}: {dec[1]}")
        else:
            print(f"   id={id_:#06x} page{page} {hexd}")
    print(flush=True)

async def main():
    print(f"Live-decoding {ADDR} for 30s...\n", flush=True)
    s = BleakScanner(detection_callback=cb)
    await s.start(); await asyncio.sleep(30); await s.stop()
    print(f"Total detections: {count}")

asyncio.run(main())
