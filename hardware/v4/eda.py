"""Run a JS file in the EasyEDA Pro window that has the target project open, via the local bridge.

usage: python eda.py script.js [out.json]
Prints the result (truncated) and, with out.json, writes the full JSON result there.
The target project defaults to "DecayDeck V4" (env EDA_PROJECT overrides).
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:49620"
PROJECT = os.environ.get("EDA_PROJECT", "DecayDeck V4")
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".eda_window")


def _post(path, payload, timeout):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"success": False, "error": f"HTTP {e.code}: {body[:2000]}"}


def find_window(attempts=20):
    """Find the window with PROJECT open; it reconnects under a new id after drops, so wait for it."""
    probe = "const p = await eda.dmt_Project.getCurrentProjectInfo(); return p ? p.friendlyName : null;"
    for _ in range(attempts):
        wins = json.loads(urllib.request.urlopen(BASE + "/eda-windows", timeout=10).read().decode())["windows"]
        for w in wins:
            r = _post("/execute", {"code": probe, "windowId": w["windowId"]}, 40)
            if r.get("result") == PROJECT:
                with open(CACHE, "w") as f:
                    f.write(w["windowId"])
                return w["windowId"]
        time.sleep(3)
    raise RuntimeError(f"no EasyEDA window has project {PROJECT!r} open")


def _window_gone(r):
    err = str(r.get("error", "")).lower()
    return not r.get("success") and any(s in err for s in ("window", "not connected", "disconnected", "no eda"))


def run(code, timeout=120, retry_on_drop=True):
    """Run code in the project window. A drop before the code ran is retried once; callers whose code is
    not idempotent pass retry_on_drop=False and reconcile state themselves."""
    wid = open(CACHE).read().strip() if os.path.exists(CACHE) else find_window()
    r = _post("/execute", {"code": code, "windowId": wid}, timeout)
    if _window_gone(r):
        wid = find_window()
        if retry_on_drop:
            r = _post("/execute", {"code": code, "windowId": wid}, timeout)
    return r


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    src = open(sys.argv[1], encoding="utf-8").read()
    resp = run(src)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as f:
            json.dump(resp, f, indent=1, ensure_ascii=False)
    text = json.dumps(resp, ensure_ascii=False)
    print(text[:4000] + ("..." if len(text) > 4000 else ""))
    print(f"[{len(text)} chars]")
