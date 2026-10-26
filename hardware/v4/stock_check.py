"""Check every BOM line against JLC's own assembly stock (the warehouse PCBA draws from; LCSC retail stock differs),
and that each LCSC number is still the part the BOM names (JLC's manufacturer part number must match exactly).
Run it right before ordering: stock moves, and an out-of-stock line must be decided by hand, never substituted.

usage: python stock_check.py [boards]     (default 5 assembled boards)
"""
import csv
import io
import json
import sys
import time
import urllib.request

BOM = "fab/2026-10-25/DecayDeck_v4_BOM.csv"
URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"


def lookup(lcsc):
    body = json.dumps({"keyword": lcsc, "currentPage": 1, "pageSize": 5}).encode()
    req = urllib.request.Request(URL, data=body, headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=20))
    lst = ((d.get("data") or {}).get("componentPageInfo") or {}).get("list") or []
    return next((x for x in lst if x.get("componentCode") == lcsc), None)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    boards = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    rows = list(csv.reader(io.StringIO(open(BOM, "rb").read().decode("utf-16")), delimiter="\t"))[1:]
    short, wrong, ext = [], [], 0
    for r in rows:
        qty, refs, mpn, lcsc = int(r[1]), r[3], r[6], r[8]
        x = lookup(lcsc)
        if not x or x.get("componentModelEn") != mpn:
            wrong.append(f"{lcsc} ({refs[:40]}): BOM says {mpn}, JLC says {x and x.get('componentModelEn')}")
        stock = x and x.get("stockCount")
        if x and x.get("componentLibraryType") == "expand" and not x.get("preferredComponentFlag"):
            ext += 1
        need = qty * boards
        if not stock or stock < need * 3:
            short.append(f"{lcsc} {mpn} ({refs[:40]}): stock {stock}, need {need}")
        time.sleep(0.3)
    print(f"{len(rows)} BOM lines checked for {boards} boards; {ext} extended parts (a setup fee each at JLC)")
    print("all in stock (3x margin)" if not short else "SHORT or tight:\n  " + "\n  ".join(short))
    print("every LCSC number is the BOM's part" if not wrong else "NOT THE BOM'S PART:\n  " + "\n  ".join(wrong))
    return 1 if short or wrong else 0


if __name__ == "__main__":
    sys.exit(main())
