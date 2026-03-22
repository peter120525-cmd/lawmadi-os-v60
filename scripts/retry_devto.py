#!/usr/bin/env python3
"""Retry failed Dev.to posts with longer delays."""
import json
import os
import time
import sys
import requests

DEVTO_API_KEY = os.environ.get("DEVTO_API_KEY", "")
DEVTO_URL = "https://dev.to/api/articles"

# Import leader data and content generator
sys.path.insert(0, ".")
from scripts.publish_leaders import LEADERS, generate_title, generate_post_content

def publish_devto(title, content, tags):
    payload = {
        "article": {
            "title": title,
            "published": True,
            "body_markdown": content,
            "tags": tags[:4],
            "series": "Lawmadi OS Leaders"
        }
    }
    resp = requests.post(
        DEVTO_URL,
        headers={"api-key": DEVTO_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=30
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("id"), data.get("url")

def main():
    # Load previous results to find failures
    with open("scripts/publish_results.json") as f:
        results = json.load(f)

    failed_leaders = {r["leader"] for r in results if not r["devto_id"]}
    leader_map = {l[0]: l for l in LEADERS}

    to_retry = [(lid, leader_map[lid]) for lid in sorted(failed_leaders) if lid in leader_map]
    print(f"Retrying {len(to_retry)} failed Dev.to posts with 15s intervals...\n")

    success_count = 0
    updated = {r["leader"]: r for r in results}

    for i, (lid, leader_data) in enumerate(to_retry):
        _, name, spec_ko, spec_en, domain_label, personality, catchphrase, topics = leader_data
        title = generate_title(lid, name, spec_en)
        content = generate_post_content(lid, name, spec_ko, spec_en, personality, catchphrase, topics)
        tags = ["ai", "legaltech", "korean", spec_en.lower().replace(" ", "").replace("&", "")[:20]]

        print(f"[{i+1}/{len(to_retry)}] {lid} {name} ({spec_en})...", end=" ", flush=True)

        try:
            devto_id, devto_url = publish_devto(title, content, tags)
            print(f"✅ {devto_url}")
            updated[lid]["devto_id"] = devto_id
            updated[lid]["devto_url"] = devto_url
            success_count += 1
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print(f"⏳ 429 — waiting 60s...")
                time.sleep(60)
                # One more try
                try:
                    devto_id, devto_url = publish_devto(title, content, tags)
                    print(f"  ✅ Retry OK: {devto_url}")
                    updated[lid]["devto_id"] = devto_id
                    updated[lid]["devto_url"] = devto_url
                    success_count += 1
                except Exception as e2:
                    print(f"  ❌ Retry failed: {e2}")
            else:
                print(f"❌ {e}")
        except Exception as e:
            print(f"❌ {e}")

        time.sleep(15)

    # Save updated results
    final = list(updated.values())
    with open("scripts/publish_results.json", "w") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Retry complete: {success_count}/{len(to_retry)} succeeded")
    still_failed = sum(1 for r in final if not r.get("devto_id"))
    print(f"Total Dev.to failures remaining: {still_failed}")

if __name__ == "__main__":
    main()
