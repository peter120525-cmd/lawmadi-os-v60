import sys, json
data = json.load(sys.stdin)
for k, v in data.items():
    if k != 'response':
        print(f"{k}: {v}")
print()
resp = data.get('response', '')
print(f"Response length: {len(resp)} chars")
print()
print("=== FULL RESPONSE ===")
print(resp)
