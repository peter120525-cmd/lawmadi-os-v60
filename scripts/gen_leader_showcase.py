#!/usr/bin/env python3
"""
60 Leader Showcase Video Generator (v2 - Premium Design)
- Per-leader theme colors matching their specialty mood
- Gradient overlay bar at bottom
- Fade-in text animation
- Glow/shadow effects on name
- Badge-style specialty label
- Output: 1920x1080 (16:9), ~5min total
"""

import json
import os
import subprocess
import sys
import shutil

PROJECT = "/data/data/com.termux/files/home/lawmadi-os-v60"
VIDEO_DIR = os.path.join(PROJECT, "frontend/public/videos/leaders")
OUTPUT_DIR = os.path.join(PROJECT, "frontend/public/videos/promo")
TEMP_DIR = os.path.join(PROJECT, "scripts/.tmp_showcase")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "lawmadi-60-leaders-showcase.mp4")

# Theme colors per specialty category
THEME_COLORS = {
    # Civil / Property / Construction - Warm earth tones
    "민사법": ("#E8B86D", "#1a1208"),
    "부동산법": ("#C9A96E", "#1a150a"),
    "건설법": ("#D4915E", "#1a1008"),
    "재개발·재건축": ("#CC8855", "#1a0f08"),
    "민사집행": ("#D4A76A", "#1a1208"),
    "등기·경매": ("#BF9B6A", "#1a140c"),
    "채권추심": ("#C48B5C", "#1a0f08"),
    "손해배상": ("#E09060", "#1a0e06"),
    # Medical / Science / Tech - Cool blue-green
    "의료법": ("#66D9E8", "#081a1a"),
    "IT·보안": ("#00E5FF", "#001a1f"),
    "정보통신": ("#40C4FF", "#001420"),
    "데이터·AI윤리": ("#7C4DFF", "#0d0820"),
    "과학기술": ("#448AFF", "#081020"),
    # Criminal / Military - Deep red-purple
    "형사법": ("#FF5252", "#1a0808"),
    "군형법": ("#FF6E40", "#1a0c06"),
    "소년법": ("#FF80AB", "#1a0a12"),
    # Family / Social / Human rights - Warm pink-rose
    "이혼·가족": ("#F48FB1", "#1a0a10"),
    "인권": ("#CE93D8", "#140a1a"),
    "사회복지": ("#F06292", "#1a080e"),
    "장애인·복지": ("#BA68C8", "#12081a"),
    "다문화·이주": ("#AB47BC", "#10061a"),
    # Business / Finance / Tax - Gold-amber
    "상사법": ("#FFD54F", "#1a1600"),
    "회사법·M&A": ("#FFC107", "#1a1400"),
    "스타트업": ("#FF9800", "#1a1000"),
    "벤처·신산업": ("#FFB74D", "#1a1200"),
    "조세·금융": ("#FFD740", "#1a1500"),
    "조세불복": ("#FFAB40", "#1a1200"),
    "보험": ("#FFE082", "#1a1600"),
    "보험·연금": ("#FFD180", "#1a1400"),
    # Traffic / Transport / Maritime - Blue
    "교통사고": ("#42A5F5", "#081420"),
    "해상·항공": ("#29B6F6", "#081620"),
    "해양·수산": ("#26C6DA", "#081a1a"),
    # Rental / Living - Green
    "임대차": ("#66BB6A", "#081a0c"),
    "교육·청소년": ("#81C784", "#0a1a0e"),
    # Government / Admin - Steel blue
    "국가계약": ("#78909C", "#0a1018"),
    "행정법": ("#90A4AE", "#0c1218"),
    "공정거래": ("#80CBC4", "#081a18"),
    # International / Trade - Teal
    "국제거래": ("#4DD0E1", "#061a1e"),
    "무역·관세": ("#4DB6AC", "#061a16"),
    # IP / Creative - Purple-violet
    "지식재산권": ("#B388FF", "#0e081a"),
    "저작권": ("#EA80FC", "#12081a"),
    "엔터테인먼트": ("#FF80AB", "#1a0812"),
    "게임·콘텐츠": ("#B9F6CA", "#081a0e"),
    "문화예술": ("#F48FB1", "#1a0a10"),
    "광고·언론": ("#FFAB91", "#1a0e08"),
    "스포츠·레저": ("#A5D6A7", "#0a1a0c"),
    # Environment / Agriculture - Green
    "환경법": ("#69F0AE", "#061a10"),
    "에너지·자원": ("#FFD54F", "#1a1600"),
    "농림·축산": ("#AED581", "#101a08"),
    "식품·보건": ("#C5E1A5", "#121a0a"),
    # Religion / Culture / Heritage
    "문화·종교": ("#BCAAA4", "#1a1412"),
    "종교·전통": ("#D7CCC8", "#1a1614"),
    # Constitution / System
    "헌법": ("#FFD700", "#1a1500"),
    "개인정보": ("#80DEEA", "#081a1c"),
    "상속·신탁": ("#A1887F", "#1a1210"),
    "시스템 총괄": ("#E0E0E0", "#0a0a1a"),
}

DEFAULT_THEME = ("#4FC3F7", "#0a0a1a")


def get_font():
    """Find a Korean-capable font."""
    for f in [
        "/data/data/com.termux/files/usr/share/fonts/TTF/NanumGothicBold.ttf",
        "/system/fonts/NotoSansCJK-Regular.ttc",
        "/data/data/com.termux/files/usr/share/fonts/TTF/NanumGothic.ttf",
        "/system/fonts/OneUISansKR-VF.ttf",
        "/system/fonts/DroidSansFallback.ttf",
    ]:
        if os.path.exists(f):
            return f
    return ""


def load_leaders():
    """Load leader data from leaders.json."""
    with open(os.path.join(PROJECT, "leaders.json"), "r", encoding="utf-8") as f:
        data = json.load(f)
    registry = data["swarm_engine_config"]["leader_registry"]
    leaders = []
    for i in range(1, 61):
        code = f"L{i:02d}"
        if code in registry:
            leaders.append({
                "code": code,
                "name": registry[code]["name"],
                "specialty": registry[code]["specialty"],
                "video": os.path.join(VIDEO_DIR, f"{code}-greeting.mp4"),
            })
    return leaders


def process_single(leader, idx, total, font_path):
    """Process a single leader video with premium styled overlay."""
    code = leader["code"]
    name = leader["name"]
    specialty = leader["specialty"]
    input_path = leader["video"]
    output_path = os.path.join(TEMP_DIR, f"{code}.mp4")

    if not os.path.exists(input_path):
        print(f"  ⚠ {code} video not found, skipping")
        return None

    accent, bg = THEME_COLORS.get(specialty, DEFAULT_THEME)
    font_esc = font_path.replace(":", "\\:")

    # Fade alpha expression: 0→1 over first 0.8s, stay 1
    fade_alpha = "if(lt(t\\,0.8)\\,t/0.8\\,1)"

    # Build filter_complex:
    # 1. Scale video to 1080x1080 (original 1:1 ratio)
    # 2. Semi-transparent gradient bar at bottom
    # 3. Leader code badge, name with glow, specialty badge
    # 4. Decorative accent line
    filter_complex = (
        # Scale video to 1080x1080
        f"[0:v]scale=1080:1080[base];"

        # Bottom gradient overlay (dark gradient for text readability)
        f"color=c=black@0.7:s=1080x250:d=5[grad];"
        f"[base][grad]overlay=0:830[withgrad];"

        # Accent line (thin colored bar at y=825)
        f"color=c={accent}@0.6:s=300x3:d=5[line];"
        f"[withgrad][line]overlay=(W-w)/2:828[withline];"

        # Leader code badge - top left with background box
        f"[withline]drawtext=fontfile='{font_esc}'"
        f":text='{code}'"
        f":fontsize=30:fontcolor={accent}"
        f":x=45:y=35"
        f":shadowcolor=black@0.8:shadowx=2:shadowy=2"
        f":alpha='{fade_alpha}'"
        f":box=1:boxcolor=black@0.5:boxborderw=8"
        f"[t0];"

        # Counter badge - top right
        f"[t0]drawtext=fontfile='{font_esc}'"
        f":text='{idx+1}/60'"
        f":fontsize=24:fontcolor=white@0.6"
        f":x=w-text_w-45:y=38"
        f":alpha='{fade_alpha}'"
        f"[t1];"

        # Name - large with triple shadow for glow effect
        # Shadow layer 1 (outer glow)
        f"[t1]drawtext=fontfile='{font_esc}'"
        f":text='{name}'"
        f":fontsize=80:fontcolor={accent}@0.3"
        f":x=(w-text_w)/2:y=870"
        f":shadowcolor={accent}@0.2:shadowx=0:shadowy=0"
        f":alpha='{fade_alpha}'"
        f"[glow];"
        # Main name text
        f"[glow]drawtext=fontfile='{font_esc}'"
        f":text='{name}'"
        f":fontsize=80:fontcolor=white"
        f":x=(w-text_w)/2:y=870"
        f":shadowcolor=black@0.9:shadowx=3:shadowy=3"
        f":alpha='{fade_alpha}'"
        f"[t2];"

        # Specialty - badge style with box background
        f"[t2]drawtext=fontfile='{font_esc}'"
        f":text='  {specialty}  '"
        f":fontsize=36:fontcolor={accent}"
        f":x=(w-text_w)/2:y=970"
        f":shadowcolor=black@0.6:shadowx=1:shadowy=1"
        f":box=1:boxcolor=black@0.4:boxborderw=10"
        f":alpha='{fade_alpha}'"
        f"[out]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-t", "5",
        "-an",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ✗ {code} {name} FAILED")
        print(f"    {result.stderr[-300:]}")
        return None

    print(f"  ✓ [{idx+1}/{total}] {code} {name} ({specialty}) 🎨 {accent}")
    return output_path


def concat_videos(clip_paths):
    """Concatenate all processed clips into final video."""
    concat_file = os.path.join(TEMP_DIR, "concat.txt")
    with open(concat_file, "w") as f:
        for path in clip_paths:
            f.write(f"file '{path}'\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        OUTPUT_FILE,
    ]

    print(f"\n🎬 Concatenating {len(clip_paths)} clips...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"✗ Concat failed: {result.stderr[-300:]}")
        return False
    print(f"✓ Output: {OUTPUT_FILE}")
    return True


def main():
    print("=" * 60)
    print("  법마디 60 Leaders Showcase Generator (v2 Premium)")
    print("  Output: 1080x1080 (1:1 original ratio), ~5 min")
    print("  Features: Theme colors, gradient, glow, fade-in")
    print("=" * 60)

    font_path = get_font()
    if not font_path:
        print("✗ No Korean font found!")
        sys.exit(1)
    print(f"📝 Font: {font_path}")

    leaders = load_leaders()
    print(f"👥 Leaders: {len(leaders)}")

    os.makedirs(TEMP_DIR, exist_ok=True)

    print("\n🎥 Processing individual clips (premium style)...")
    clip_paths = []
    for idx, leader in enumerate(leaders):
        result = process_single(leader, idx, len(leaders), font_path)
        if result:
            clip_paths.append(result)

    if not clip_paths:
        print("✗ No clips processed")
        sys.exit(1)

    print(f"\n✓ {len(clip_paths)}/{len(leaders)} clips processed")

    success = concat_videos(clip_paths)

    if success:
        size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
        print(f"\n{'=' * 60}")
        print(f"  ✅ Complete! {len(clip_paths)} leaders, {len(clip_paths)*5}s")
        print(f"  📁 {OUTPUT_FILE}")
        print(f"  💾 {size_mb:.1f} MB")
        print(f"{'=' * 60}")

    print(f"\nTemp files in {TEMP_DIR}")
    if "--cleanup" in sys.argv:
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        print("🧹 Temp cleaned up")


if __name__ == "__main__":
    main()
