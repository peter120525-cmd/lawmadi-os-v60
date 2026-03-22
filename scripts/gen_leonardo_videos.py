#!/usr/bin/env python3
"""Leonardo.AI image-to-video batch generator for remaining leaders."""
import json, os, sys, time, requests

API_KEY = os.environ.get("LEONARDO_API_KEY", "")
BASE = "https://cloud.leonardo.ai/api/rest/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
IMG_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "images", "leaders")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "videos", "leaders")
RESULTS_FILE = os.path.join(os.path.dirname(__file__), "leonardo_results.json")

# Leaders that already have greeting mp4
DONE = {1,2,3,13,18,19,23,27,29,33,34,35,41,43,45,48,50,53,54,55,59}

LEADERS = {
    4:"aki",5:"yeonwoo",6:"byeori",7:"hanui",8:"onyu",9:"hanul",10:"gyeolhwi",
    11:"oreum",12:"aseul",14:"dasom",15:"byeolha",16:"seula",17:"mir",
    20:"chansol",21:"sebin",22:"gaon",24:"doul",25:"damwoo",26:"jinu",
    28:"haeseul",30:"damwoo",31:"roun",32:"bareum",36:"dana",37:"yesol",
    38:"seulbi",39:"gaon",40:"hangyeol",42:"haram",44:"boram",46:"daol",
    47:"saeron",49:"garam",51:"soul",52:"miso",56:"dain",57:"seum",
    58:"yeon",60:"madi"
}

PROMPT = "A professional Korean legal AI character in business attire performs a polite greeting bow, subtle smile, gentle hand gesture, studio lighting, smooth natural movement"

def load_results():
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            return json.load(f)
    return {}

def save_results(results):
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)

def check_balance():
    r = requests.get(f"{BASE}/me", headers=HEADERS)
    data = r.json()["user_details"][0]
    tokens = data.get("apiPaidTokens", 0) + (data.get("apiSubscriptionTokens") or 0)
    print(f"Available tokens: {tokens}")
    return tokens

def upload_image(leader_num, name):
    img_path = os.path.join(IMG_DIR, f"L{leader_num:02d}-{name}.jpg")
    if not os.path.exists(img_path):
        print(f"  Image not found: {img_path}")
        return None

    # Step 1: Get presigned URL
    r = requests.post(f"{BASE}/init-image", headers=HEADERS, json={"extension": "jpg"})
    if r.status_code != 200:
        print(f"  Upload init failed: {r.status_code} {r.text}")
        return None

    data = r.json()["uploadInitImage"]
    image_id = data["id"]
    upload_url = data["url"]
    fields = json.loads(data["fields"])

    # Step 2: Upload to S3
    with open(img_path, "rb") as f:
        resp = requests.post(upload_url, data=fields, files={"file": (f"L{leader_num:02d}.jpg", f, "image/jpeg")})
    if resp.status_code not in (200, 204):
        print(f"  S3 upload failed: {resp.status_code}")
        return None

    print(f"  Uploaded image: {image_id}")
    return image_id

def generate_video(image_id):
    payload = {
        "imageId": image_id,
        "imageType": "UPLOADED",
        "prompt": PROMPT,
        "model": "MOTION2FAST",
        "resolution": "RESOLUTION_480",
        "promptEnhance": False,
        "isPublic": False
    }
    r = requests.post(f"{BASE}/generations-image-to-video", headers=HEADERS, json=payload)
    if r.status_code != 200:
        print(f"  Video gen failed: {r.status_code} {r.text}")
        return None

    data = r.json()["motionVideoGenerationJob"]
    gen_id = data["generationId"]
    cost = data.get("cost", {})
    print(f"  Generation started: {gen_id} (cost: {cost})")
    return gen_id

def poll_video(gen_id, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(10)
        r = requests.get(f"{BASE}/generations/{gen_id}", headers=HEADERS)
        if r.status_code != 200:
            continue
        data = r.json()
        gens = data.get("generations_by_pk", {})
        status = gens.get("status")
        print(f"  Status: {status}")
        if status == "COMPLETE":
            videos = gens.get("generated_images", [])
            if videos:
                return videos[0].get("motionMP4URL") or videos[0].get("url")
        elif status == "FAILED":
            print(f"  Generation failed!")
            return None
    print(f"  Timeout after {timeout}s")
    return None

def download_video(url, leader_num):
    out_path = os.path.join(OUT_DIR, f"L{leader_num:02d}-greeting.mp4")
    r = requests.get(url, stream=True)
    with open(out_path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"  Downloaded: {out_path} ({size_mb:.1f}MB)")
    return out_path

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    results = load_results()
    tokens = check_balance()

    todo = sorted([n for n in LEADERS if n not in DONE and str(n) not in results])
    print(f"\nRemaining: {len(todo)} leaders")
    if not todo:
        print("All done!")
        return

    for num in todo:
        name = LEADERS[num]
        code = f"L{num:02d}"
        print(f"\n{'='*50}")
        print(f"Processing {code} ({name}) ...")

        # Check balance
        tokens = check_balance()
        if tokens < 20:
            print("Insufficient tokens, stopping.")
            break

        # Upload
        image_id = upload_image(num, name)
        if not image_id:
            results[str(num)] = {"status": "upload_failed"}
            save_results(results)
            continue

        # Generate
        gen_id = generate_video(image_id)
        if not gen_id:
            results[str(num)] = {"status": "gen_failed"}
            save_results(results)
            continue

        # Poll
        video_url = poll_video(gen_id)
        if not video_url:
            results[str(num)] = {"status": "poll_failed", "gen_id": gen_id}
            save_results(results)
            continue

        # Download
        out_path = download_video(video_url, num)
        results[str(num)] = {"status": "done", "gen_id": gen_id, "path": out_path}
        save_results(results)
        print(f"  {code} complete!")

    print(f"\n{'='*50}")
    print(f"Results: {sum(1 for v in results.values() if v.get('status')=='done')} done")
    save_results(results)

if __name__ == "__main__":
    main()
