# 🌳 Lawmadi OS 브랜치 구조

**정리 일자:** 2026-02-14
**구조:** 단순화 완료 (main + v60-development)

---

## 📋 현재 브랜치 구조

```
lawmadi-os-v50/
├── main                 (v50.3.0-VERIFIED - 프로덕션 안정 버전)
└── v60-development      (v60 업그레이드 개발 브랜치)
```

---

## 🎯 브랜치 설명

### main (프로덕션)
```
상태: v50.3.0-VERIFIED
태그: v50.3.0-VERIFIED
목적: 프로덕션 안정 버전
배포: Cloud Run + Firebase
```

**특징:**
- 프로덕션 환경에 배포된 안정 버전
- v50.3.0-VERIFIED 태그로 백업됨
- SSOT 90% 커버리지 (9/10 sources)
- Claude 응답 프레임워크 + 자동 검증
- 프리미엄 UI/UX

**최신 커밋:**
```
379b8c8 - ORGANIZE: 저장소 정리 - 95개 파일 아카이브
838dc99 - UPDATE: "법률 AI" → "Lawmadi OS" 용어 통일
919db47 - DOCS: Phase 4 문서화 + 테스트 파일 추가
```

### v60-development (개발)
```
기준: v50.3.0-VERIFIED
목적: v60 업그레이드 개발
상태: 개발 준비 완료
```

**특징:**
- v50을 기반으로 v60 기능 개발
- 실험적 기능 테스트
- 안정화 후 main으로 병합 예정

**백업:**
- v50으로 롤백 가능: `bash RESTORE_V50.sh`
- 백업 위치: 5곳 (Git, GCS, Docker, Cloud Run, Firebase)

---

## 🔄 워크플로우

### v60 개발 시작
```bash
# v60 브랜치로 전환
git checkout v60-development

# 개발 작업 수행
# ... 코드 수정 ...

# 커밋 및 푸시
git add .
git commit -m "FEATURE: v60 기능 추가"
git push origin v60-development
```

### v60 → main 병합 (안정화 후)
```bash
# main으로 전환
git checkout main

# v60 브랜치 병합
git merge v60-development

# 태그 생성
git tag -a v60.0.0 -m "Lawmadi OS v60.0.0"

# 원격 푸시
git push origin main
git push origin v60.0.0
```

### v60 실패 시 v50 복구
```bash
# 자동 복구 스크립트 실행
bash RESTORE_V50.sh

# 또는 수동 복구
git checkout v50.3.0-VERIFIED
```

---

## 🗑️ 삭제된 브랜치

다음 브랜치들이 정리되었습니다:

**로컬 + 원격 삭제:**
- `audit/v50.2.3` - 감사 브랜치 (불필요)
- `hotfix/remove-env-from-repo` - 핫픽스 완료 (병합됨)

**이유:**
- main에 이미 병합됨
- 더 이상 사용되지 않음
- 브랜치 구조 단순화

---

## 📊 브랜치 전략

### 브랜치 모델
```
main (프로덕션)
  └── v60-development (개발)
        └── (필요시) feature/* (기능 개발)
```

### 명명 규칙
- `main` - 프로덕션 안정 버전
- `v{N}-development` - 메이저 버전 개발
- `feature/*` - 특정 기능 개발 (선택)
- `hotfix/*` - 긴급 수정 (선택)

### 태그 규칙
- `v{major}.{minor}.{patch}` - 정식 릴리스
- `v{major}.{minor}.{patch}-VERIFIED` - 검증된 안정 버전
- 예: `v50.3.0-VERIFIED`, `v60.0.0`

---

## 🔒 보호 규칙

### main 브랜치
- ✅ 프로덕션 배포 브랜치
- ✅ 직접 푸시 가능 (소규모 팀)
- ✅ 태그로 버전 관리
- ⚠️ 신중한 병합 필요

### v60-development 브랜치
- ✅ 자유로운 실험 가능
- ✅ 커밋 히스토리 정리 불필요
- ✅ 안정화 후 main으로 병합

---

## 📚 관련 문서

- `V50_BACKUP_INFO.md` - v50 백업 정보
- `RESTORE_V50.sh` - v50 복구 스크립트
- `REPOSITORY_STRUCTURE.md` - 저장소 구조
- `.git/config` - Git 설정

---

## 🔍 브랜치 확인 명령어

### 현재 브랜치 확인
```bash
git branch
git branch -r  # 원격 브랜치
git branch -a  # 모든 브랜치
```

### 브랜치 전환
```bash
git checkout main           # main으로 전환
git checkout v60-development # v60으로 전환
```

### 브랜치 상태 확인
```bash
git log --oneline -5        # 최근 커밋
git status                  # 작업 상태
git diff main v60-development  # 브랜치 간 차이
```

---

**브랜치 정리:** Claude Code (Sonnet 4.5)
**정리 일자:** 2026-02-14
**구조:** main (프로덕션) + v60-development (개발)
