#!/usr/bin/env python3
"""
Lawmadi OS v60 시스템 점검 스크립트
"""
import os
import sys
import json
from pathlib import Path

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def check_mark(condition, success_msg, fail_msg):
    if condition:
        print(f"✅ {success_msg}")
        return True
    else:
        print(f"❌ {fail_msg}")
        return False

def main():
    print("🔍 Lawmadi OS v60 시스템 점검 시작\n")

    issues = []
    checks_passed = 0
    total_checks = 0

    # =========================================
    # 1. 버전 확인
    # =========================================
    print_section("1. 버전 확인")

    # main.py 버전
    main_py = Path("main.py")
    if main_py.exists():
        with open(main_py, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'OS_VERSION = "v60.0.0"' in content:
                print("✅ main.py: v60.0.0")
                checks_passed += 1
            else:
                print("❌ main.py: 버전 불일치")
                issues.append("main.py 버전이 v60.0.0이 아님")
    total_checks += 1

    # config.json 버전
    config_json = Path("config.json")
    if config_json.exists():
        with open(config_json, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # system_metadata 안에 있는 os_version 확인
            version = config.get('system_metadata', {}).get('os_version', 'unknown')
            if version == "v60.0.0":
                print(f"✅ config.json: {version}")
                checks_passed += 1
            else:
                print(f"❌ config.json: {version} (v60.0.0 기대)")
                issues.append(f"config.json 버전이 {version}")
    total_checks += 1

    # =========================================
    # 2. 필수 디렉토리 확인
    # =========================================
    print_section("2. 필수 디렉토리")

    required_dirs = [
        "uploads",
        "static",
        "static/leaders",
        "static/leaders/images",
        "static/leaders/videos",
        "frontend/public",
        "scripts",
        "agents",
        "connectors",
        "services",
    ]

    for dir_path in required_dirs:
        path = Path(dir_path)
        if check_mark(path.exists() and path.is_dir(),
                     f"{dir_path}/",
                     f"{dir_path}/ 없음"):
            checks_passed += 1
        else:
            issues.append(f"{dir_path}/ 디렉토리 없음")
        total_checks += 1

    # =========================================
    # 3. 핵심 파일 확인
    # =========================================
    print_section("3. 핵심 파일")

    core_files = [
        "main.py",
        "config.json",
        "requirements.txt",
        "Dockerfile",
        "README.md",
        "claude.md",
        "frontend/public/index.html",
        "scripts/migrate_v60_documents.sql",
        "V60_DOCUMENT_UPLOAD_SUMMARY.md",
    ]

    for file_path in core_files:
        path = Path(file_path)
        if check_mark(path.exists() and path.is_file(),
                     file_path,
                     f"{file_path} 없음"):
            checks_passed += 1
        else:
            issues.append(f"{file_path} 파일 없음")
        total_checks += 1

    # =========================================
    # 4. 환경변수 확인
    # =========================================
    print_section("4. 환경변수")

    env_vars = [
        "GEMINI_API_KEY",
        "LAWGO_DRF_OC",
    ]

    for var in env_vars:
        value = os.getenv(var)
        if check_mark(value is not None and value != "",
                     f"{var}: 설정됨",
                     f"{var}: 미설정"):
            checks_passed += 1
        else:
            issues.append(f"{var} 환경변수 미설정")
        total_checks += 1

    # DATABASE_URL (선택적)
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        print(f"✅ DATABASE_URL: 설정됨")
    else:
        print(f"⚠️  DATABASE_URL: 미설정 (선택적)")

    # =========================================
    # 5. 의존성 확인
    # =========================================
    print_section("5. Python 패키지")

    packages = [
        "fastapi",
        "uvicorn",
        "google.genai",
        "PyPDF2",
    ]

    for package in packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package}")
            checks_passed += 1
        except ImportError:
            print(f"❌ {package} 미설치")
            issues.append(f"{package} 패키지 미설치")
        total_checks += 1

    # =========================================
    # 6. 파일 업로드 기능 확인 (코드 검증)
    # =========================================
    print_section("6. v60 문서 업로드 기능")

    # main.py에서 upload 엔드포인트 확인
    with open("main.py", 'r', encoding='utf-8') as f:
        main_content = f.read()

    upload_checks = [
        ('@app.post("/upload")', "POST /upload 엔드포인트"),
        ('@app.post("/analyze-document', "POST /analyze-document 엔드포인트"),
        ('async def _analyze_image_document', "이미지 분석 함수"),
        ('async def _analyze_pdf_document', "PDF 분석 함수"),
        ('UploadFile', "파일 업로드 import"),
    ]

    for code_snippet, description in upload_checks:
        if check_mark(code_snippet in main_content,
                     description,
                     f"{description} 없음"):
            checks_passed += 1
        else:
            issues.append(f"{description} 코드 없음")
        total_checks += 1

    # index.html에서 업로드 UI 확인
    index_html = Path("frontend/public/index.html")
    if index_html.exists():
        with open(index_html, 'r', encoding='utf-8') as f:
            html_content = f.read()

        ui_checks = [
            ('id="uploadBtn"', "업로드 버튼"),
            ('id="fileInput"', "파일 입력"),
            ('handleFileUploadAndAnalysis', "파일 업로드 핸들러"),
            ('formatDocumentAnalysis', "문서 분석 포맷터"),
        ]

        for code_snippet, description in ui_checks:
            if check_mark(code_snippet in html_content,
                         f"프론트엔드: {description}",
                         f"프론트엔드: {description} 없음"):
                checks_passed += 1
            else:
                issues.append(f"프론트엔드 {description} 코드 없음")
            total_checks += 1

    # =========================================
    # 7. 최종 보고
    # =========================================
    print_section("최종 점검 결과")

    success_rate = (checks_passed / total_checks * 100) if total_checks > 0 else 0

    print(f"✅ 통과: {checks_passed}/{total_checks} ({success_rate:.1f}%)")

    if issues:
        print(f"\n⚠️  발견된 문제 ({len(issues)}개):\n")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
    else:
        print(f"\n🎉 모든 점검 통과!")

    print(f"\n{'='*60}")

    if success_rate >= 90:
        print("✅ 시스템 상태: 양호 (배포 가능)")
        return 0
    elif success_rate >= 70:
        print("⚠️  시스템 상태: 주의 (일부 기능 제한)")
        return 1
    else:
        print("❌ 시스템 상태: 불량 (점검 필요)")
        return 2

if __name__ == "__main__":
    sys.exit(main())
