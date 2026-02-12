#!/usr/bin/env python3
"""
최종 시스템 점검
- 모든 핵심 기능 검증
- 배포 전 체크리스트
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, '/workspaces/lawmadi-os-v50')

def print_header(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def check_environment_variables():
    """환경변수 검증"""
    print_header("1️⃣ 환경변수 검증")

    required = {
        "GEMINI_KEY": "Gemini API 키",
        "LAWGO_DRF_OC": "법제처 DRF API 키",
    }

    optional = {
        "CLOUD_SQL_INSTANCE": "Cloud SQL 인스턴스",
        "DB_USER": "DB 사용자",
        "DB_PASS": "DB 비밀번호",
        "DB_NAME": "DB 이름",
        "INTERNAL_TOKEN": "관리자 토큰",
    }

    print("\n필수 환경변수:")
    for key, desc in required.items():
        value = os.getenv(key)
        if value:
            print(f"   ✅ {key}: 설정됨 ({desc})")
        else:
            print(f"   ❌ {key}: 미설정 ({desc})")

    print("\n선택 환경변수:")
    for key, desc in optional.items():
        value = os.getenv(key)
        if value:
            print(f"   ✅ {key}: 설정됨 ({desc})")
        else:
            print(f"   ⚠️  {key}: 미설정 ({desc})")

def check_file_structure():
    """파일 구조 검증"""
    print_header("2️⃣ 파일 구조 검증")

    critical_files = {
        "main.py": "메인 서버",
        "Dockerfile": "Docker 이미지",
        "requirements.txt": "Python 패키지",
        "frontend/index.html": "프론트엔드",
        "connectors/db_client_v2.py": "DB 클라이언트",
        "agents/swarm_orchestrator.py": "Swarm 엔진",
        "agents/clevel_handler.py": "C-Level 시스템",
    }

    print("\n핵심 파일:")
    for file, desc in critical_files.items():
        path = Path(file)
        if path.exists():
            size = path.stat().st_size
            print(f"   ✅ {file}: {size:,} bytes ({desc})")
        else:
            print(f"   ❌ {file}: 없음 ({desc})")

def check_configuration():
    """설정 파일 검증"""
    print_header("3️⃣ 설정 파일 검증")

    # config.json
    if Path("config.json").exists():
        with open("config.json") as f:
            config = json.load(f)
        print("\n✅ config.json:")
        print(f"   - model_config: {len(config.get('model_config', {}))} 항목")
        print(f"   - core_registry: {len(config.get('core_registry', {}))} 임원")

    # leaders.json
    if Path("leaders.json").exists():
        with open("leaders.json") as f:
            leaders = json.load(f)
        leader_count = len(leaders.get('swarm_engine_config', {}).get('leader_registry', {}))
        print("\n✅ leaders.json:")
        print(f"   - leader_registry: {leader_count} 리더")

    # .env (샘플만 확인)
    if Path(".env.example").exists():
        print("\n✅ .env.example: 존재")

    if Path(".env").exists():
        print("✅ .env: 존재 (실제 환경변수)")

def check_dockerfile():
    """Dockerfile 검증"""
    print_header("4️⃣ Dockerfile 검증")

    if Path("Dockerfile").exists():
        with open("Dockerfile") as f:
            content = f.read()

        checks = {
            "FROM python:": "베이스 이미지",
            "COPY requirements.txt": "의존성 복사",
            "RUN pip install": "패키지 설치",
            "COPY . /app": "소스 코드 복사",
            "CMD": "실행 명령",
        }

        print("\nDockerfile 내용:")
        for pattern, desc in checks.items():
            if pattern in content:
                print(f"   ✅ {desc}: 확인")
            else:
                print(f"   ❌ {desc}: 누락")

def check_github_actions():
    """GitHub Actions 설정 검증"""
    print_header("5️⃣ GitHub Actions 검증")

    workflow_path = Path(".github/workflows/claude-code.yml")
    if workflow_path.exists():
        with open(workflow_path) as f:
            content = f.read()

        print("\n✅ claude-code.yml:")

        checks = {
            "on: [push]": "Push 트리거",
            "build": "빌드 job",
            "docker": "Docker 관련",
            "gcloud": "Cloud Run 배포",
        }

        for pattern, desc in checks.items():
            if pattern in content.lower():
                print(f"   ✅ {desc}: 확인")
            else:
                print(f"   ⚠️  {desc}: 확인 필요")

def check_git_status():
    """Git 상태 확인"""
    print_header("6️⃣ Git 상태 확인")

    import subprocess

    # 현재 브랜치
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True, text=True
    ).stdout.strip()
    print(f"\n현재 브랜치: {branch}")

    # 커밋 상태
    status = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True, text=True
    ).stdout

    if status.strip():
        print("\n변경사항:")
        print(status)
    else:
        print("\n✅ 모든 변경사항 커밋됨")

    # 최근 커밋
    log = subprocess.run(
        ["git", "log", "-1", "--oneline"],
        capture_output=True, text=True
    ).stdout.strip()
    print(f"\n최근 커밋: {log}")

def deployment_checklist():
    """배포 체크리스트"""
    print_header("7️⃣ 배포 전 체크리스트")

    checklist = [
        ("환경변수 설정", "GEMINI_KEY, LAWGO_DRF_OC 등"),
        ("DB 테이블 초기화", "chat_history, visitor_stats 등"),
        ("Docker 이미지 빌드", "Dockerfile 검증"),
        ("Cloud Run 설정", "GCP 프로젝트, 권한"),
        ("Firebase 설정", "firebase.json, .firebaserc"),
        ("도메인 설정", "lawmadi-os-v50.run.app"),
        ("모니터링 설정", "/health, /metrics 엔드포인트"),
    ]

    print("\n필수 확인 사항:")
    for idx, (item, desc) in enumerate(checklist, 1):
        print(f"   {idx}. {item}")
        print(f"      → {desc}")

def main():
    print("\n" + "🔍" * 40)
    print("   Lawmadi OS 최종 시스템 점검")
    print("🔍" * 40)

    check_environment_variables()
    check_file_structure()
    check_configuration()
    check_dockerfile()
    check_github_actions()
    check_git_status()
    deployment_checklist()

    print("\n" + "=" * 80)
    print("✅ 시스템 점검 완료!")
    print("=" * 80)
    print("\n다음 단계:")
    print("  1. main 브랜치로 병합: git checkout main && git merge hotfix/remove-env-from-repo")
    print("  2. GitHub push: git push origin main")
    print("  3. Cloud Run 자동 배포 확인")
    print("  4. Firebase 배포: firebase deploy --only hosting")
    print("\n")

if __name__ == "__main__":
    main()
