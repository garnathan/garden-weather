import asyncio
from bleak import BleakScanner

SP_HINTS = ("sensorpush", "htp", "ht.w", "ht1", "tc.x")

def looks_sensorpush(name, mfg):
    n = (name or "").lower()
    if any(h in n for h in SP_HINTS):
        return True
    # sensorpush advertises manufacturer-specific data; flag any short mfg blob as candidate
    return False

async def main():
    print("Scanning 20s (active)...\n")
    seen = {}
    def cb(dev, adv):
        seen[dev.address] = (dev, adv)
    scanner = BleakScanner(detection_callback=cb)
    await scanner.start()
    await asyncio.sleep(20)
    await scanner.stop()

    print(f"Found {len(seen)} devices:\n")
    cands = []
    for addr, (dev, adv) in sorted(seen.items(), key=lambda x: -(x[1][1].rssi or -999)):
        name = adv.local_name or dev.name
        mfg = adv.manufacturer_data
        suuids = adv.service_uuids
        mfg_str = ", ".join(f"{cid:#06x}:{data.hex()}" for cid, data in mfg.items()) or "-"
        flag = "  <== SENSORPUSH?" if (looks_sensorpush(name, mfg) or any("ef09" in u.lower() for u in suuids)) else ""
        print(f"[{adv.rssi:>4} dBm] {addr}  name={name!r}")
        print(f"           mfg=[{mfg_str}]")
        if suuids:
            print(f"           svc_uuids={suuids}")
        if adv.service_data:
            print(f"           svc_data={ {u: d.hex() for u,d in adv.service_data.items()} }")
        if flag:
            print(f"          {flag}")
            cands.append(addr)
        print()
    print("Candidate SensorPush addresses:", cands or "NONE (inspect mfg blobs above)")

asyncio.run(main())
