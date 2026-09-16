import json

a = {r["file"]: r for r in json.load(open(r"D:\front-desk\eval_results.json"))}
b = {r["file"]: r for r in json.load(open(r"D:\front-desk\eval_results_v2.json"))}

print("CHANGED BETWEEN RUNS")
print("-" * 92)
any_change = False
for f in sorted(b):
    old = a.get(f, {}).get("got", "?")
    new = b[f]["got"]
    if old != new:
        any_change = True
        direction = "FIXED  " if b[f]["hit"] else "BROKE  "
        print(f"  {direction}{f:<44} {old:<20} -> {new}")
if not any_change:
    print("  (nothing changed)")

print("\nSTILL FAILING")
print("-" * 92)
for f in sorted(b):
    if not b[f]["hit"]:
        print(f"  {f:<44} {b[f]['expected']:<26} -> {b[f]['got']}")
        print(f"      saw: {b[f].get('notes')}")
