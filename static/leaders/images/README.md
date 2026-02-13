# 60 Leaders 이미지

**목적:** 60명 Leaders의 프로필 이미지 저장

---

## 📁 폴더 구조

```
images/
├── profiles/           # 고해상도 프로필 사진
│   ├── leader-001.jpg (Chief Legal Officer)
│   ├── leader-002.jpg (사건분석관)
│   └── ...
│
└── thumbnails/         # 최적화된 썸네일
    ├── leader-001-thumb.jpg
    ├── leader-002-thumb.jpg
    └── ...
```

---

## 📋 파일 명명 규칙

### 프로필 사진
```
leader-{ID}.{ext}

ID: 001-060 (3자리 숫자, 0 패딩)
ext: jpg, png, webp
```

**예시:**
- `leader-001.jpg` - Chief Legal Officer
- `leader-015.jpg` - 판례분석관
- `leader-060.jpg` - 국제법 전문가

### 썸네일
```
leader-{ID}-thumb.{ext}
```

**예시:**
- `leader-001-thumb.jpg`
- `leader-015-thumb.jpg`

---

## 📏 이미지 사양

### 프로필 사진 (profiles/)
- **크기:** 1200x1200px (정사각형)
- **포맷:** JPEG (우선), PNG (투명 배경 필요 시)
- **용량:** < 500KB
- **품질:** JPEG 85%
- **용도:** 상세 페이지, 고해상도 표시

### 썸네일 (thumbnails/)
- **크기:** 300x300px (정사각형)
- **포맷:** JPEG
- **용량:** < 100KB
- **품질:** JPEG 80%
- **용도:** 목록, 카드, 미리보기

---

## 🎨 이미지 가이드라인

### 스타일
- 전문적이고 공식적인 이미지
- 깔끔한 배경 (단색 또는 그라디언트)
- 얼굴 중심, 상반신 구도
- 일관된 조명과 색감

### 색상
- 자연스러운 색감
- 과도한 필터 지양
- Lawmadi OS 브랜드 컬러와 조화

### 금지 사항
- 저작권 침해 이미지
- 부적절하거나 공격적인 내용
- 과도한 보정이나 왜곡

---

## 🛠️ 이미지 최적화

### 자동 최적화 스크립트
```bash
# 프로필 사진 최적화
python scripts/optimize_images.py --input profiles/ --output profiles/ --size 1200 --quality 85

# 썸네일 생성
python scripts/optimize_images.py --input profiles/ --output thumbnails/ --size 300 --quality 80 --suffix thumb
```

### 수동 최적화 (ImageMagick)
```bash
# 프로필 사진
convert input.jpg -resize 1200x1200^ -gravity center -extent 1200x1200 -quality 85 leader-001.jpg

# 썸네일 생성
convert leader-001.jpg -resize 300x300^ -gravity center -extent 300x300 -quality 80 leader-001-thumb.jpg
```

---

## 📊 저장소 관리

### Git LFS 사용 (권장)
```bash
# Git LFS 설치
git lfs install

# 이미지 추적
git lfs track "static/leaders/images/profiles/*.jpg"
git lfs track "static/leaders/images/profiles/*.png"
```

### 외부 스토리지 옵션
- **Google Cloud Storage** (추천)
- **AWS S3**
- **Cloudinary** (이미지 최적화 자동)
- **imgix** (CDN + 최적화)

---

## 🔗 API 엔드포인트

### 이미지 접근
```
GET /static/leaders/images/profiles/leader-{ID}.jpg
GET /static/leaders/images/thumbnails/leader-{ID}-thumb.jpg
```

### 예시
```
https://lawmadi-db.web.app/static/leaders/images/profiles/leader-001.jpg
https://lawmadi-db.web.app/static/leaders/images/thumbnails/leader-001-thumb.jpg
```

---

## 📝 업로드 프로세스

1. **이미지 준비**
   - 고해상도 원본 (최소 1200x1200px)
   - 적절한 파일명 (leader-{ID}.jpg)

2. **최적화**
   - 프로필: 1200x1200px, JPEG 85%
   - 썸네일: 300x300px, JPEG 80%

3. **검증**
   - 파일 크기 확인 (프로필 < 500KB, 썸네일 < 100KB)
   - 이미지 품질 확인

4. **업로드**
   - `static/leaders/images/profiles/`에 프로필 저장
   - `static/leaders/images/thumbnails/`에 썸네일 저장

5. **테스트**
   - 브라우저에서 이미지 로드 확인
   - 반응형 표시 확인

---

**버전:** v60.0.0
**최종 업데이트:** 2026-02-13
