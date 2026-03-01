#!/usr/bin/env python3
"""Firebase Hosting REST API deploy script (no Firebase CLI needed)."""
import hashlib
import gzip
import json
import os
import subprocess
import sys
import requests

SITE = "lawmadi-db"
PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "public")
API_BASE = "https://firebasehosting.googleapis.com/v1beta1"

# firebase.json config
HOSTING_CONFIG = {
    "headers": [
        {
            "glob": "**",
            "headers": {
                "X-Frame-Options": "DENY",
                "X-Content-Type-Options": "nosniff",
                "X-XSS-Protection": "1; mode=block",
                "Referrer-Policy": "strict-origin-when-cross-origin",
                "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
                "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                "Content-Security-Policy": (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://www.google-analytics.com; "
                    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                    "font-src 'self' https://fonts.gstatic.com; "
                    "img-src 'self' https: data:; "
                    "connect-src 'self' https://lawmadi-os-v60-938146962157.asia-northeast3.run.app https://www.google-analytics.com https://region1.google-analytics.com; "
                    "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'; upgrade-insecure-requests"
                ),
            },
        },
        {"glob": "/index.html", "headers": {"Cache-Control": "no-cache, must-revalidate"}},
        {"glob": "/index-en.html", "headers": {"Cache-Control": "no-cache, must-revalidate"}},
        {"glob": "/sw.js", "headers": {"Cache-Control": "no-cache, must-revalidate"}},
        {"glob": "/manifest.json", "headers": {"Cache-Control": "no-cache, must-revalidate"}},
        {"glob": "/purify.min.js", "headers": {"Cache-Control": "public, max-age=2592000, immutable"}},
        {"glob": "/lawmadi-monitor.js", "headers": {"Cache-Control": "no-cache, must-revalidate"}},
        {"glob": "**/*.@(jpg|jpeg|png|gif|svg|webp|ico|mp4)", "headers": {"Cache-Control": "public, max-age=604800, immutable"}},
    ],
    "rewrites": [
        {"glob": "/en", "path": "/index-en.html"},
        {"glob": "/about", "path": "/about.html"},
        {"glob": "/about-en", "path": "/about-en.html"},
        {"glob": "/leaders", "path": "/leaders.html"},
        {"glob": "/leaders-en", "path": "/leaders-en.html"},
        {"glob": "/clevel-en", "path": "/clevel-en.html"},
        {"glob": "/leader", "path": "/leader-profile.html"},
    ],
}


def get_token():
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"], capture_output=True, text=True
    )
    return result.stdout.strip()


def api_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "x-goog-user-project": "lawmadi-db",
    }


def collect_files():
    """Collect all files and compute SHA256 of gzipped content."""
    files = {}
    for root, _dirs, filenames in os.walk(PUBLIC_DIR):
        for fname in filenames:
            if fname.startswith("."):
                continue
            full_path = os.path.join(root, fname)
            rel_path = "/" + os.path.relpath(full_path, PUBLIC_DIR)

            with open(full_path, "rb") as f:
                raw = f.read()
            compressed = gzip.compress(raw)
            sha = hashlib.sha256(compressed).hexdigest()

            files[rel_path] = {"hash": sha, "gzip": compressed, "size": len(compressed)}
    return files


def main():
    token = get_token()
    if not token:
        print("Failed to get gcloud token")
        sys.exit(1)

    headers = api_headers(token)

    # 1. Create version
    print("1. Creating new hosting version...")
    resp = requests.post(
        f"{API_BASE}/sites/{SITE}/versions",
        headers=headers,
        json={"config": HOSTING_CONFIG},
    )
    if resp.status_code != 200:
        print(f"   Failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    version = resp.json()
    version_name = version["name"]
    print(f"   Version: {version_name}")

    # 2. Collect files
    print("2. Collecting files...")
    files = collect_files()
    print(f"   Found {len(files)} files")

    # 3. Populate files (get upload URLs)
    print("3. Populating file list...")
    file_hashes = {path: info["hash"] for path, info in files.items()}
    resp = requests.post(
        f"{API_BASE}/{version_name}:populateFiles",
        headers=headers,
        json={"files": file_hashes},
    )
    if resp.status_code != 200:
        print(f"   Failed: {resp.status_code} {resp.text}")
        sys.exit(1)

    populate_result = resp.json()
    upload_url = populate_result.get("uploadUrl", "")
    files_to_upload = populate_result.get("uploadRequiredHashes", [])
    print(f"   Upload URL: {upload_url[:80]}...")
    print(f"   Files needing upload: {len(files_to_upload)}/{len(files)}")

    # 4. Upload files
    if files_to_upload:
        print("4. Uploading files...")
        hash_to_data = {}
        for path, info in files.items():
            hash_to_data[info["hash"]] = info["gzip"]

        uploaded = 0
        failed = 0
        for file_hash in files_to_upload:
            gzip_data = hash_to_data.get(file_hash)
            if not gzip_data:
                print(f"   WARNING: hash {file_hash} not found")
                failed += 1
                continue

            upload_headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
                "x-goog-user-project": "lawmadi-db",
            }
            resp = requests.post(
                f"{upload_url}/{file_hash}",
                headers=upload_headers,
                data=gzip_data,
            )
            if resp.status_code == 200:
                uploaded += 1
            else:
                print(f"   Failed {file_hash[:12]}...: {resp.status_code}")
                failed += 1

            if uploaded % 20 == 0:
                print(f"   Uploaded: {uploaded}/{len(files_to_upload)}")

        print(f"   Upload complete: {uploaded} ok, {failed} failed")
    else:
        print("4. All files already cached, no upload needed")

    # 5. Finalize version
    print("5. Finalizing version...")
    resp = requests.patch(
        f"{API_BASE}/{version_name}?updateMask=status",
        headers=headers,
        json={"status": "FINALIZED"},
    )
    if resp.status_code != 200:
        print(f"   Failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    print(f"   Status: {resp.json().get('status')}")

    # 6. Release version
    print("6. Releasing to live...")
    resp = requests.post(
        f"{API_BASE}/sites/{SITE}/releases?versionName={version_name}",
        headers=headers,
        json={},
    )
    if resp.status_code != 200:
        print(f"   Failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    release = resp.json()
    print(f"   Release: {release.get('name', 'ok')}")
    print(f"   Type: {release.get('type', '?')}")

    print()
    print("=" * 50)
    print("Firebase Hosting deployed successfully!")
    print(f"  https://lawmadi-db.web.app")
    print(f"  https://lawmadi-db.firebaseapp.com")
    print("=" * 50)


if __name__ == "__main__":
    main()
