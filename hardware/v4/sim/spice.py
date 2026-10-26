"""Run ngspice in batch mode and read the results back as numpy arrays.

ngspice (free, ngspice.sourceforge.io) is found from $NGSPICE, then PATH, then the default unpack location
%LOCALAPPDATA%/Programs/ngspice-47/Spice64/bin.
"""
import os
import shutil
import subprocess
import tempfile
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, "vendor")
VENDOR_MODELS = {   # fetched on first use, kept out of git: the vendor's file, unchanged
    "us1m.lib": "https://www.vishay.com/docs/89605/us1m.txt",
}


def ngspice():
    for p in (os.environ.get("NGSPICE"), shutil.which("ngspice_con"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "ngspice-47", "Spice64", "bin",
                           "ngspice_con.exe")):
        if p and os.path.exists(p):
            return p
    raise SystemExit("ngspice not found: install it from ngspice.sourceforge.io or set NGSPICE")


def includes():
    os.makedirs(VENDOR, exist_ok=True)
    out = [os.path.join(HERE, "models.lib")]
    for name, url in VENDOR_MODELS.items():
        path = os.path.join(VENDOR, name)
        if not os.path.exists(path):
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            open(path, "wb").write(urllib.request.urlopen(req, timeout=30).read())
        out.append(path)
    return [f".include '{p.replace(os.sep, '/')}'" for p in out]


def run(title, body, tran, vectors, control="", timeout=3600, write=None):
    """Simulate `body` (netlist lines) with `.tran` arguments `tran`, save `vectors`, return (columns, stdout).
    control: extra ngspice commands run after the simulation, before the data is written (e.g. linearize, meas).
    write: the vectors to write out, when control leaves only some of them (linearize does)."""
    work = tempfile.mkdtemp(prefix="dd_sim_")
    data = os.path.join(work, "out.txt").replace(os.sep, "/")
    deck = [f"* {title}", *includes(), *body, f".tran {tran}", ".control", "set wr_singlescale", "set wr_vecnames",
            "option numdgt=8", f"save {' '.join(vectors)}", "run", control, f"wrdata {data} {' '.join(write or vectors)}",
            "quit", ".endc", ".end"]
    path = os.path.join(work, "deck.cir")
    open(path, "w").write("\n".join(deck) + "\n")
    p = subprocess.run([ngspice(), "-b", path], capture_output=True, text=True, timeout=timeout, cwd=work)
    if not os.path.exists(data):
        raise SystemExit(f"ngspice produced no data for {title}:\n{p.stdout[-3000:]}\n{p.stderr[-3000:]}\ndeck: {path}")
    with open(data) as f:
        names = f.readline().split()
        arr = np.loadtxt(f, ndmin=2)
    cols = {n.lower(): arr[:, i] for i, n in enumerate(names)}
    shutil.rmtree(work, ignore_errors=True)
    return cols, p.stdout


def avg(t, y, t0=None, t1=None):
    """Time average of y over [t0, t1] on ngspice's uneven time steps."""
    m = (t >= (t0 if t0 is not None else t[0])) & (t <= (t1 if t1 is not None else t[-1]))
    return np.trapezoid(y[m], t[m]) / (t[m][-1] - t[m][0])
