"""Resolve every (ref, pin) in design.NETS against the probed symbols and report problems.

usage: python check_spec.py [--pins REF ...]   (--pins prints the symbol pins of those refs)
Exit 1 when any reference fails to resolve, a pin lands on two nets, or a part has no connections.
"""
import json
import sys

from design import NETS, PARTS

SYMS = json.load(open("symbols.json", encoding="utf-8"))


def pins_of(ref):
    return SYMS[PARTS[ref][0]]["pins"]


def resolve(ref, key):
    """Return the list of pin numbers that (ref, key) refers to."""
    pins = pins_of(ref)
    if key.startswith("@"):
        name = key[1:]
        hits = [p["num"] for p in pins if p["name"] == name]
    else:
        hits = [p["num"] for p in pins if p["num"] == key]
    return hits


def resolved_nets():
    """net -> set of (ref, pin number); raises on unresolved references."""
    out, errors = {}, []
    for net, conns in NETS.items():
        for ref, key in conns:
            if ref not in PARTS:
                errors.append(f"{net}: unknown part {ref}")
                continue
            hits = resolve(ref, key)
            if not hits:
                errors.append(f"{net}: {ref} has no pin {key!r}")
            for n in hits:
                out.setdefault(net, set()).add((ref, n))
    return out, errors


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) > 2 and sys.argv[1] == "--pins":
        for ref in sys.argv[2:]:
            ps = sorted(pins_of(ref), key=lambda p: (len(p["num"]), p["num"]))
            print(ref, PARTS[ref][1], SYMS[PARTS[ref][0]].get("mpn"), SYMS[PARTS[ref][0]].get("footprint"))
            print("   " + "  ".join(f"{p['num']}={p['name']}" for p in ps))
        return 0
    nets, errors = resolved_nets()
    owner = {}
    for net, members in nets.items():
        for m in members:
            if m in owner and owner[m] != net:
                errors.append(f"pin {m} on two nets: {owner[m]} and {net}")
            owner[m] = net
    used = {ref for ref, _ in owner}
    for ref in PARTS:
        if ref not in used:
            errors.append(f"{ref} has no connections")
    for e in errors:
        print("ERROR", e)
    # unconnected pins report (informational)
    for ref in sorted(PARTS):
        free = [p for p in pins_of(ref) if (ref, p["num"]) not in owner]
        if free:
            print(f"nc {ref:5} " + " ".join(f"{p['num']}={p['name']}" for p in free))
    print(f"{len(nets)} nets, {len(owner)} pin connections, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
