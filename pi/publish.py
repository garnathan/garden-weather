#!/usr/bin/env python3
"""Every 5 min: read the SensorPush, upload to Weather Underground, and commit
the reading into the garden-weather GitHub repo (full history + rolling window +
latest.json for the phone widget)."""
import os, sys, json, csv, time, subprocess, urllib.parse, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sensorpush import read_once                     # reuse existing BLE reader
import asyncio

REPO      = os.path.join(HERE, "wunderground-killi")
DATA      = os.path.join(REPO, "data")
RECENT_N  = 2016                                      # ~7 days at 5-min cadence
WU_URL    = "https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"
WU_TRIES  = 4                                         # ride out new-station propagation / transient 401s

def load_env(path=os.path.join(HERE, ".env")):
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

def upload_wu(d):
    wu_id, wu_key = os.environ.get("WU_ID"), os.environ.get("WU_KEY")
    if not wu_id or not wu_key:
        return "skipped (no creds)"
    params = {
        "ID": wu_id, "PASSWORD": wu_key, "action": "updateraw",
        "dateutc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        "tempf": round(d["temperature_f"], 2),
        "humidity": round(d["humidity_pct"], 2),
        "baromin": round(d["pressure_sealevel_mbar"] / 33.8639, 3),  # mbar -> inHg (sea level)
        "dewptf": round(d["dew_point_c"] * 9 / 5 + 32, 2),
        "softwaretype": "home-pi-sensorpush",
    }
    url = WU_URL + "?" + urllib.parse.urlencode(params)
    last = ""
    for i in range(WU_TRIES):
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                body = r.read().decode("utf-8", "replace").strip()
            if "success" in body.lower():
                return "success" if i == 0 else f"success (try {i+1})"
            last = f"error: {body[:60]}"
        except urllib.error.HTTPError as e:
            last = f"error: HTTP {e.code}"
        except Exception as e:
            last = f"error: {type(e).__name__}: {e}"
        if i < WU_TRIES - 1:
            time.sleep(2)
    return last

def write_files(d):
    os.makedirs(DATA, exist_ok=True)
    month = time.strftime("%Y-%m", time.gmtime(d["epoch"]))
    csv_path = os.path.join(DATA, f"{month}.csv")
    cols = ["epoch","ts","temperature_c","temperature_f","humidity_pct",
            "pressure_station_mbar","pressure_sealevel_mbar","dew_point_c",
            "heat_index_c","wu_status"]
    new = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if new: w.writeheader()
        w.writerow({k: d.get(k) for k in cols})
    recent_path = os.path.join(DATA, "recent.json")
    try:
        recent = json.load(open(recent_path)) if os.path.exists(recent_path) else []
        if not isinstance(recent, list): recent = []
    except Exception:
        recent = []
    recent.append(d)
    recent = recent[-RECENT_N:]
    json.dump(recent, open(recent_path, "w"))
    json.dump(d, open(os.path.join(REPO, "latest.json"), "w"), indent=2)

def git_push(d):
    env = dict(os.environ)
    try:
        subprocess.run(["git","-C",REPO,"add","-A"], check=True, capture_output=True, text=True, env=env)
        st = subprocess.run(["git","-C",REPO,"status","--porcelain"], capture_output=True, text=True, env=env).stdout
        if not st.strip():
            return "no-change"
        subprocess.run(["git","-C",REPO,"commit","-q","-m",
                        f"reading {d['ts']} ({d['temperature_c']}C {d['humidity_pct']}%)"],
                       check=True, capture_output=True, text=True, env=env)
        subprocess.run(["git","-C",REPO,"push","-q"], check=True, capture_output=True, text=True, env=env)
        return "pushed"
    except subprocess.CalledProcessError as e:
        return f"git-error: {(e.stderr or e.stdout or '').strip()[:160]}"

def main():
    load_env()
    d = asyncio.run(read_once())
    d["epoch"] = int(time.time())
    d["wu_status"] = upload_wu(d)
    write_files(d)
    push = git_push(d)
    print(f"[{d['ts']}] {d['temperature_c']}C {d['humidity_pct']}% "
          f"{d['pressure_sealevel_mbar']}mb | WU={d['wu_status']} | git={push}", flush=True)

if __name__ == "__main__":
    main()
