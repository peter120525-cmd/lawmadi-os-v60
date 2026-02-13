# 60 Leaders 동영상

**목적:** 60명 Leaders의 소개 및 시연 동영상 저장

---

## 📁 폴더 구조

```
videos/
├── intros/             # 소개 영상 (30초~1분)
│   ├── leader-001-intro.mp4
│   ├── leader-002-intro.mp4
│   └── ...
│
└── demos/              # 시연 영상 (1~3분)
    ├── leader-001-demo.mp4
    ├── leader-002-demo.mp4
    └── ...
```

---

## 📋 파일 명명 규칙

### 소개 영상
```
leader-{ID}-intro.mp4

ID: 001-060 (3자리 숫자, 0 패딩)
```

**예시:**
- `leader-001-intro.mp4` - Chief Legal Officer 소개
- `leader-015-intro.mp4` - 판례분석관 소개

### 시연 영상
```
leader-{ID}-demo.mp4
```

**예시:**
- `leader-001-demo.mp4` - CLO 기능 시연
- `leader-015-demo.mp4` - 판례분석 시연

---

## 📹 동영상 사양

### 소개 영상 (intros/)
- **길이:** 30초 ~ 1분
- **해상도:** 1920x1080 (1080p Full HD)
- **프레임레이트:** 30fps
- **포맷:** MP4 (H.264 + AAC)
- **비트레이트:**
  - 비디오: 5 Mbps
  - 오디오: 128 kbps (스테레오)
- **용량:** < 50MB
- **용도:** 인물 소개, 역할 설명

### 시연 영상 (demos/)
- **길이:** 1분 ~ 3분
- **해상도:** 1280x720 (720p HD)
- **프레임레이트:** 30fps
- **포맷:** MP4 (H.264 + AAC)
- **비트레이트:**
  - 비디오: 3 Mbps
  - 오디오: 128 kbps (스테레오)
- **용량:** < 100MB
- **용도:** 기능 시연, 사용 예시

---

## 🎬 콘텐츠 가이드라인

### 소개 영상 (Intros)

**구성:**
1. **오프닝 (5초)**
   - Lawmadi OS 로고 + 인물 이름
   - 배경음악 시작

2. **자기소개 (15초)**
   - 이름, 역할, 전문 분야
   - 핵심 역량 1-2가지

3. **특징 (10초)**
   - 차별화 포인트
   - 강점

4. **클로징 (5초)**
   - 행동 유도 (CTA)
   - "법률 문제를 해결하겠습니다"

**스타일:**
- 전문적이고 신뢰감 있는 톤
- 명확하고 간결한 메시지
- 시각적으로 깔끔한 편집

### 시연 영상 (Demos)

**구성:**
1. **인트로 (10초)**
   - 시연할 기능 소개
   - 문제 상황 제시

2. **시연 (90초~150초)**
   - 실제 사용 예시
   - 단계별 설명
   - 결과 확인

3. **요약 (10초)**
   - 핵심 기능 정리
   - 장점 강조

**스타일:**
- 실전 중심, 실용적
- 화면 녹화 + 나레이션
- 자막 포함

---

## 🛠️ 동영상 제작 도구

### 녹화
- **화면 녹화:** OBS Studio, Loom, Camtasia
- **카메라 녹화:** DSLR, 웹캠

### 편집
- **전문:** Adobe Premiere Pro, Final Cut Pro
- **간편:** DaVinci Resolve (무료), iMovie
- **온라인:** Clipchamp, Kapwing

### 최적화
- **인코딩:** Handbrake, FFmpeg
- **압축:** VideoSmaller, Clideo

---

## 📊 동영상 최적화

### FFmpeg 인코딩

**소개 영상 (1080p):**
```bash
ffmpeg -i input.mp4 -c:v libx264 -preset medium -crf 23 -vf "scale=1920:1080" \
  -c:a aac -b:a 128k -movflags +faststart leader-001-intro.mp4
```

**시연 영상 (720p):**
```bash
ffmpeg -i input.mp4 -c:v libx264 -preset medium -crf 25 -vf "scale=1280:720" \
  -c:a aac -b:a 128k -movflags +faststart leader-001-demo.mp4
```

### 최적화 옵션
- `-crf 23`: 품질 (낮을수록 고품질, 18-28 권장)
- `-preset medium`: 인코딩 속도 vs 압축률
- `-movflags +faststart`: 웹 스트리밍 최적화
- `-vf scale`: 해상도 조정

---

## ⚠️ 저장소 관리

### 권장: 외부 스토리지 사용

**이유:**
- 동영상 파일 크기가 큼 (60명 × 150MB ≈ 9GB)
- Git 저장소 비대화 방지
- 빠른 로딩 및 스트리밍

**옵션:**
1. **YouTube (비공개/공개)** ⭐ 추천
   - 무료, 무제한 저장
   - 자동 최적화 및 CDN
   - 임베드 간편

2. **Vimeo**
   - 전문적인 플레이어
   - 브랜딩 옵션

3. **Google Cloud Storage**
   - 직접 제어
   - 비용 발생

4. **AWS S3 + CloudFront**
   - CDN 통합
   - 글로벌 배포

### Git LFS 사용 (로컬 저장 시)
```bash
# Git LFS 설치
git lfs install

# 동영상 추적
git lfs track "static/leaders/videos/**/*.mp4"
git add .gitattributes
git commit -m "Add Git LFS tracking for videos"
```

---

## 🔗 API 엔드포인트

### 동영상 접근
```
GET /static/leaders/videos/intros/leader-{ID}-intro.mp4
GET /static/leaders/videos/demos/leader-{ID}-demo.mp4
```

### YouTube 임베드 (권장)
```html
<!-- leaders.html -->
<iframe
  width="560"
  height="315"
  src="https://www.youtube.com/embed/{VIDEO_ID}"
  frameborder="0"
  allowfullscreen>
</iframe>
```

---

## 📝 업로드 프로세스

### 로컬 저장 방식
1. **동영상 제작**
   - 녹화 및 편집
   - 사양에 맞게 인코딩

2. **최적화**
   - FFmpeg로 압축
   - 용량 확인 (소개 < 50MB, 시연 < 100MB)

3. **업로드**
   - `static/leaders/videos/intros/` 또는 `demos/`에 저장
   - Git LFS 사용 (큰 파일)

4. **테스트**
   - 브라우저에서 재생 확인
   - 로딩 속도 확인

### YouTube 방식 (권장)
1. **YouTube 업로드**
   - 비공개 또는 공개 설정
   - 제목: "Lawmadi OS - Leader #001 (Chief Legal Officer)"
   - 설명 및 태그 추가

2. **임베드 코드 복사**
   - 공유 → 퍼가기
   - iframe 코드 복사

3. **leaders.json 업데이트**
   ```json
   {
     "id": "001",
     "name": "Chief Legal Officer",
     "intro_video": "https://www.youtube.com/embed/VIDEO_ID",
     "demo_video": "https://www.youtube.com/embed/VIDEO_ID"
   }
   ```

4. **프론트엔드 통합**
   - leaders.html에 iframe 추가
   - 반응형 플레이어 구현

---

## 📊 예상 디스크 사용량

```
항목                    파일 수    평균 크기    총 용량
────────────────────────────────────────────────────────
소개 영상 (intros)      60개      40MB         2.4GB
시연 영상 (demos)       60개      80MB         4.8GB
────────────────────────────────────────────────────────
총계                    120개                  7.2GB
```

**권장:** YouTube 임베드 사용으로 Git 저장소 크기 최소화 (0GB)

---

## 🔒 보안 및 접근 제어

### 공개 동영상
- `/static/leaders/videos/` - 누구나 접근 가능
- YouTube 공개 영상

### 비공개 동영상 (선택)
- YouTube 비공개 또는 일부 공개
- 인증 필요한 시연 영상

---

## 📝 체크리스트

- [ ] 60명 소개 영상 제작 (30초~1분)
- [ ] 60명 시연 영상 제작 (1~3분)
- [ ] 동영상 최적화 (FFmpeg)
- [ ] YouTube 업로드 (권장)
- [ ] leaders.json에 동영상 URL 추가
- [ ] leaders.html 업데이트
- [ ] 반응형 플레이어 구현
- [ ] 로딩 최적화 (lazy loading)
- [ ] 테스트 (모바일, 데스크톱)

---

**버전:** v60.0.0
**최종 업데이트:** 2026-02-13
**권장 방식:** YouTube 임베드 (무료, 무제한, 자동 최적화)
