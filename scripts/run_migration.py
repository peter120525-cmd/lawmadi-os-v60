#!/usr/bin/env python3
"""
Lawmadi OS v60 - 데이터베이스 마이그레이션 실행 스크립트
"""
import os
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from connectors.db_client_v2 import execute

def run_migration():
    """v60 문서 업로드 테이블 마이그레이션 실행"""
    print("🚀 Lawmadi OS v60 마이그레이션 시작...\n")

    # SQL 파일 읽기
    sql_file = Path(__file__).parent / "migrate_v60_documents.sql"

    if not sql_file.exists():
        print(f"❌ SQL 파일을 찾을 수 없습니다: {sql_file}")
        sys.exit(1)

    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # SQL을 세미콜론으로 분리하여 실행
    statements = [
        stmt.strip()
        for stmt in sql_content.split(';')
        if stmt.strip() and not stmt.strip().startswith('--')
    ]

    success_count = 0
    for i, stmt in enumerate(statements, 1):
        # DO 블록과 CREATE 문 등 개별 실행
        if any(keyword in stmt.upper() for keyword in ['CREATE', 'DO $$', 'COMMENT']):
            print(f"📝 실행 중 ({i}/{len(statements)}): {stmt[:50]}...")
            result = execute(stmt, fetch="none")

            if result.get("ok"):
                print(f"   ✅ 성공\n")
                success_count += 1
            else:
                error = result.get("error", "Unknown error")
                # 이미 존재하는 테이블/인덱스는 경고로 처리
                if "already exists" in str(error).lower():
                    print(f"   ⚠️  이미 존재함: {error}\n")
                    success_count += 1
                else:
                    print(f"   ❌ 실패: {error}\n")

    print(f"\n{'='*60}")
    print(f"✅ 마이그레이션 완료: {success_count}/{len(statements)} 성공")
    print(f"{'='*60}\n")

    # 테이블 확인
    verify_result = execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'uploaded_documents'",
        fetch="one"
    )

    if verify_result.get("ok") and verify_result.get("data"):
        count = verify_result["data"][0]
        if count > 0:
            print("✅ uploaded_documents 테이블 생성 확인됨")
        else:
            print("⚠️  uploaded_documents 테이블을 찾을 수 없습니다")

    print("\n🎉 마이그레이션 프로세스 완료!\n")


if __name__ == "__main__":
    run_migration()
