import { useState, useEffect } from "react";

/*
  Design direction: 20-30대 여성이 편안하게 느끼는 법률 AI 서비스 테마.
  "법률"이지만 딱딱하지 않고, "여성 타깃"이지만 유치하지 않은 균형.
  핵심: 부드러움 + 신뢰감 + 세련됨
*/

const themes = [
  {
    id: "soft-sage",
    name: "Soft Sage",
    nameKo: "소프트 세이지",
    emoji: "🌿",
    description:
      "차분한 세이지 그린 기반. 자연스럽고 편안한 느낌으로, 법률 서비스의 딱딱함을 부드럽게 중화합니다. 요즘 인테리어·뷰티 트렌드와도 잘 맞아 2030 여성에게 친숙한 톤.",
    personality: "차분하고 믿음직한 친구",
    moodKeywords: ["자연스러운", "편안한", "신뢰감"],
    recommended: true,
    dark: {
      bg: "#101A15",
      surface: "#151F1A",
      card: "#1A2922",
      border: "#2D4038",
      textPrimary: "#E4EDE8",
      textSecondary: "#8BAA9A",
      textMuted: "#5D7D6D",
      accent: "#6DBB8F",
      accentSoft: "#6DBB8F22",
      accentHover: "#8DD4AA",
      success: "#6DBB8F",
      warning: "#E8C468",
      error: "#E87C7C",
      headerBg: "#0D1611",
    },
    light: {
      bg: "#F4F8F5",
      surface: "#FFFFFF",
      card: "#FFFFFF",
      border: "#D4E4DA",
      textPrimary: "#1A2E22",
      textSecondary: "#4A6B56",
      textMuted: "#7A9A88",
      accent: "#3D8B5E",
      accentSoft: "#3D8B5E12",
      accentHover: "#2D7A4E",
      success: "#3D8B5E",
      warning: "#B8922D",
      error: "#C45454",
      headerBg: "#EDF3EF",
    },
  },
  {
    id: "blush-rose",
    name: "Blush & Rose",
    nameKo: "블러쉬 로제",
    emoji: "🌸",
    description:
      "따뜻한 로즈/블러쉬 톤에 뉴트럴 베이스. 부드럽지만 유치하지 않은 성숙한 핑크. '불안을 행동으로' 메시지와 정서적으로 가장 잘 맞는 따뜻한 테마.",
    personality: "따뜻하고 공감하는 언니",
    moodKeywords: ["따뜻한", "공감", "안심"],
    recommended: false,
    dark: {
      bg: "#161213",
      surface: "#1C1718",
      card: "#241E20",
      border: "#3D3335",
      textPrimary: "#F0E8EA",
      textSecondary: "#B89EA3",
      textMuted: "#8A6F74",
      accent: "#D4848E",
      accentSoft: "#D4848E22",
      accentHover: "#E4A0A8",
      success: "#6DBB8F",
      warning: "#E8C468",
      error: "#D4848E",
      headerBg: "#120F10",
    },
    light: {
      bg: "#FBF6F7",
      surface: "#FFFFFF",
      card: "#FFFFFF",
      border: "#EDDDE0",
      textPrimary: "#2E1F22",
      textSecondary: "#6B4E54",
      textMuted: "#9A7E84",
      accent: "#B5616B",
      accentSoft: "#B5616B10",
      accentHover: "#9E4D57",
      success: "#3D8B5E",
      warning: "#B8922D",
      error: "#B5616B",
      headerBg: "#F6ECEE",
    },
  },
  {
    id: "lavender-mist",
    name: "Lavender Mist",
    nameKo: "라벤더 미스트",
    emoji: "💜",
    description:
      "은은한 라벤더/바이올렛 톤. 지적이면서도 부드러운 느낌. AI·테크 서비스 느낌을 유지하면서도 따뜻함을 잃지 않는 균형점. 프리미엄 감성.",
    personality: "세련되고 똑똑한 조언자",
    moodKeywords: ["지적", "세련됨", "프리미엄"],
    recommended: false,
    dark: {
      bg: "#12101A",
      surface: "#17141F",
      card: "#1E1A28",
      border: "#332E42",
      textPrimary: "#EAE6F2",
      textSecondary: "#A49BBF",
      textMuted: "#7A7092",
      accent: "#9B8EC4",
      accentSoft: "#9B8EC422",
      accentHover: "#B8ADDA",
      success: "#6DBB8F",
      warning: "#E8C468",
      error: "#D87C8A",
      headerBg: "#0E0C15",
    },
    light: {
      bg: "#F7F5FC",
      surface: "#FFFFFF",
      card: "#FFFFFF",
      border: "#DDD6EE",
      textPrimary: "#1E1A2E",
      textSecondary: "#574E72",
      textMuted: "#857BA0",
      accent: "#7160A8",
      accentSoft: "#7160A810",
      accentHover: "#5E4D95",
      success: "#3D8B5E",
      warning: "#B8922D",
      error: "#B5546B",
      headerBg: "#EFEAF8",
    },
  },
  {
    id: "warm-sand",
    name: "Warm Sand",
    nameKo: "웜 샌드",
    emoji: "🏖️",
    description:
      "따뜻한 베이지/샌드 베이스에 테라코타 액센트. 카페·서점 같은 편안한 공간감. 법률이라는 주제의 무게감을 가장 효과적으로 줄여주는 테마.",
    personality: "편안한 동네 카페의 상담사",
    moodKeywords: ["편안한", "일상적", "접근성"],
    recommended: false,
    dark: {
      bg: "#15120E",
      surface: "#1A1713",
      card: "#22201A",
      border: "#3A3630",
      textPrimary: "#EDE8E0",
      textSecondary: "#ADA393",
      textMuted: "#847A6C",
      accent: "#C4956A",
      accentSoft: "#C4956A22",
      accentHover: "#D8AE88",
      success: "#6DBB8F",
      warning: "#C4956A",
      error: "#D47C6A",
      headerBg: "#110F0B",
    },
    light: {
      bg: "#FAF7F3",
      surface: "#FFFFFF",
      card: "#FFFFFF",
      border: "#E8DED2",
      textPrimary: "#2A2418",
      textSecondary: "#6B5E4C",
      textMuted: "#9A8E7C",
      accent: "#A06B3C",
      accentSoft: "#A06B3C10",
      accentHover: "#8A5830",
      success: "#3D8B5E",
      warning: "#A06B3C",
      error: "#B05544",
      headerBg: "#F3EDE5",
    },
  },
];

function getContrast(fg, bg) {
  const hexToRgb = (hex) => [
    parseInt(hex.slice(1, 3), 16),
    parseInt(hex.slice(3, 5), 16),
    parseInt(hex.slice(5, 7), 16),
  ];
  const lum = ([r, g, b]) => {
    const a = [r, g, b].map((v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2];
  };
  const l1 = lum(hexToRgb(fg));
  const l2 = lum(hexToRgb(bg));
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

function WcagBadge({ ratio }) {
  const r = Math.round(ratio * 10) / 10;
  const level = r >= 7 ? "AAA" : r >= 4.5 ? "AA" : "FAIL";
  const color = r >= 7 ? "#059669" : r >= 4.5 ? "#2563EB" : "#DC2626";
  const bg = r >= 7 ? "#05966915" : r >= 4.5 ? "#2563EB15" : "#DC262615";
  return (
    <span
      style={{
        fontSize: 9,
        fontWeight: 700,
        color,
        backgroundColor: bg,
        padding: "2px 5px",
        borderRadius: 3,
        letterSpacing: 0.3,
      }}
    >
      {r}:1 {level}
    </span>
  );
}

function MiniPreview({ theme, mode, isActive }) {
  const c = mode === "dark" ? theme.dark : theme.light;
  return (
    <div
      style={{
        width: "100%",
        backgroundColor: c.bg,
        borderRadius: 10,
        padding: 14,
        border: `2px solid ${isActive ? c.accent : c.border}`,
        transition: "all 0.3s ease",
        cursor: "pointer",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {theme.recommended && (
        <div
          style={{
            position: "absolute",
            top: 8,
            right: 8,
            fontSize: 8,
            fontWeight: 800,
            color: c.bg,
            backgroundColor: c.accent,
            padding: "2px 6px",
            borderRadius: 4,
            letterSpacing: 0.5,
          }}
        >
          추천
        </div>
      )}
      <div style={{ fontSize: 18, marginBottom: 6 }}>{theme.emoji}</div>
      <div
        style={{
          fontSize: 12,
          fontWeight: 700,
          color: c.textPrimary,
          marginBottom: 2,
        }}
      >
        {theme.nameKo}
      </div>
      <div style={{ fontSize: 10, color: c.textSecondary }}>{theme.personality}</div>
      <div style={{ display: "flex", gap: 4, marginTop: 8 }}>
        {[c.bg, c.surface, c.accent, c.textPrimary, c.textSecondary].map(
          (color, i) => (
            <div
              key={i}
              style={{
                width: 14,
                height: 14,
                borderRadius: "50%",
                backgroundColor: color,
                border: `1px solid ${c.border}`,
              }}
            />
          )
        )}
      </div>
    </div>
  );
}

function FullPreview({ theme, mode }) {
  const c = mode === "dark" ? theme.dark : theme.light;

  return (
    <div
      style={{
        backgroundColor: c.bg,
        borderRadius: 16,
        overflow: "hidden",
        border: `1px solid ${c.border}`,
        fontFamily: "'Pretendard', -apple-system, sans-serif",
      }}
    >
      {/* Nav */}
      <div
        style={{
          backgroundColor: c.headerBg,
          borderBottom: `1px solid ${c.border}`,
          padding: "12px 20px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              width: 24,
              height: 24,
              borderRadius: 6,
              backgroundColor: c.accent,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 12,
              color: mode === "dark" ? c.bg : "#FFF",
              fontWeight: 800,
            }}
          >
            L
          </div>
          <span
            style={{ fontSize: 13, fontWeight: 700, color: c.textPrimary }}
          >
            Lawmadi OS
          </span>
          <span
            style={{
              fontSize: 9,
              color: c.accent,
              backgroundColor: c.accentSoft,
              padding: "2px 6px",
              borderRadius: 4,
              fontWeight: 600,
            }}
          >
            v60
          </span>
        </div>
        <div style={{ display: "flex", gap: 16, fontSize: 11, color: c.textMuted }}>
          <span>소개</span>
          <span>요금제</span>
          <span
            style={{
              color: mode === "dark" ? c.bg : "#FFF",
              backgroundColor: c.accent,
              padding: "4px 10px",
              borderRadius: 6,
              fontWeight: 600,
              fontSize: 10,
            }}
          >
            시작하기
          </span>
        </div>
      </div>

      {/* Hero */}
      <div style={{ padding: "32px 24px 24px", textAlign: "center" }}>
        <div
          style={{
            fontSize: 9,
            letterSpacing: 3,
            color: c.accent,
            fontWeight: 700,
            textTransform: "uppercase",
            marginBottom: 10,
          }}
        >
          Legal AI Platform
        </div>
        <div
          style={{
            fontSize: 22,
            fontWeight: 800,
            color: c.textPrimary,
            lineHeight: 1.4,
            marginBottom: 8,
          }}
        >
          불안을 행동으로 바꾸는
          <br />
          법률 운영체제
        </div>
        <div
          style={{
            fontSize: 13,
            color: c.textSecondary,
            lineHeight: 1.6,
            marginBottom: 20,
          }}
        >
          60명의 AI 전문 리더가 함께 분석합니다
        </div>
        <div style={{ display: "flex", justifyContent: "center", gap: 10 }}>
          <div
            style={{
              backgroundColor: c.accent,
              color: mode === "dark" ? c.bg : "#FFF",
              fontSize: 12,
              fontWeight: 700,
              padding: "10px 24px",
              borderRadius: 10,
            }}
          >
            무료로 시작하기
          </div>
          <div
            style={{
              border: `1.5px solid ${c.border}`,
              color: c.textSecondary,
              fontSize: 12,
              fontWeight: 600,
              padding: "10px 24px",
              borderRadius: 10,
            }}
          >
            자세히 보기
          </div>
        </div>
      </div>

      {/* Feature Cards */}
      <div style={{ padding: "0 20px 20px", display: "flex", gap: 10 }}>
        {[
          { icon: "✓", title: "실시간 법령 검증", desc: "3,043개 법령" },
          { icon: "⚡", title: "60명 AI 리더", desc: "자동 배정" },
          { icon: "🛡", title: "DRF 검증", desc: "fail-closed" },
        ].map((f) => (
          <div
            key={f.title}
            style={{
              flex: 1,
              backgroundColor: c.surface,
              border: `1px solid ${c.border}`,
              borderRadius: 12,
              padding: 14,
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: 18, marginBottom: 6 }}>{f.icon}</div>
            <div
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: c.textPrimary,
                marginBottom: 3,
              }}
            >
              {f.title}
            </div>
            <div style={{ fontSize: 10, color: c.textMuted }}>{f.desc}</div>
          </div>
        ))}
      </div>

      {/* Trust Bar */}
      <div
        style={{
          margin: "0 20px 20px",
          backgroundColor: c.surface,
          border: `1px solid ${c.border}`,
          borderRadius: 12,
          padding: 14,
          display: "flex",
          justifyContent: "space-around",
        }}
      >
        {[
          { value: "99.9%", label: "검증률", color: c.success },
          { value: "3,043", label: "법령", color: c.accent },
          { value: "60명", label: "전문 리더", color: c.warning },
          { value: "4단계", label: "파이프라인", color: c.textSecondary },
        ].map((s) => (
          <div key={s.label} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: s.color }}>
              {s.value}
            </div>
            <div
              style={{ fontSize: 9, color: c.textMuted, marginTop: 2 }}
            >
              {s.label}
            </div>
          </div>
        ))}
      </div>

      {/* Trust Principles Mini */}
      <div style={{ padding: "0 20px 20px" }}>
        <div
          style={{
            backgroundColor: c.surface,
            border: `1px solid ${c.border}`,
            borderRadius: 12,
            padding: 14,
          }}
        >
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: c.textPrimary,
              marginBottom: 10,
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <div
              style={{
                width: 3,
                height: 14,
                backgroundColor: c.accent,
                borderRadius: 2,
              }}
            />
            신뢰 원칙
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr",
              gap: 6,
            }}
          >
            {[
              "공식 법령만",
              "추측 금지",
              "모르면 멈춤",
              "사칭 금지",
              "정확한 날짜",
              "출처 공개",
            ].map((p) => (
              <div
                key={p}
                style={{
                  fontSize: 9,
                  color: c.textSecondary,
                  backgroundColor: c.accentSoft,
                  padding: "5px 6px",
                  borderRadius: 6,
                  textAlign: "center",
                  fontWeight: 500,
                }}
              >
                {p}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ColorRow({ label, hex, bgHex }) {
  const ratio = bgHex ? getContrast(hex, bgHex) : null;
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "4px 0",
      }}
    >
      <div
        style={{
          width: 20,
          height: 20,
          borderRadius: 5,
          backgroundColor: hex,
          border: "1px solid rgba(128,128,128,0.2)",
          flexShrink: 0,
        }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <span style={{ fontSize: 10, opacity: 0.6 }}>{label}</span>
      </div>
      <code style={{ fontSize: 9, opacity: 0.4, fontFamily: "monospace" }}>
        {hex}
      </code>
      {ratio && <WcagBadge ratio={ratio} />}
    </div>
  );
}

export default function LawmadiThemeShowcase() {
  const [selected, setSelected] = useState(0);
  const [mode, setMode] = useState("light");
  const [animKey, setAnimKey] = useState(0);

  useEffect(() => {
    setAnimKey((k) => k + 1);
  }, [selected, mode]);

  const theme = themes[selected];
  const c = mode === "dark" ? theme.dark : theme.light;

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(145deg, #0A0A0C 0%, #111118 50%, #0A0A0C 100%)",
        color: "#D4D4D8",
        fontFamily: "'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif",
        padding: "28px 16px",
      }}
    >
      <div style={{ maxWidth: 860, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ marginBottom: 32 }}>
          <div
            style={{
              display: "inline-block",
              fontSize: 9,
              letterSpacing: 3,
              color: "#6B6B7B",
              fontWeight: 600,
              textTransform: "uppercase",
              marginBottom: 8,
              borderBottom: "1px solid #2A2A35",
              paddingBottom: 4,
            }}
          >
            Lawmadi OS · Theme for 20-30s Women
          </div>
          <h1
            style={{
              fontSize: 24,
              fontWeight: 800,
              margin: "8px 0 0",
              lineHeight: 1.4,
              background: "linear-gradient(135deg, #E4E4E8 0%, #A4A4B8 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            20-30대 여성을 위한
            <br />
            테마 컬러 4종
          </h1>
          <p
            style={{
              fontSize: 13,
              color: "#7A7A8A",
              marginTop: 8,
              lineHeight: 1.7,
              maxWidth: 520,
            }}
          >
            법률 서비스의 전문성은 유지하면서, 딱딱하지 않고 편안한 느낌을 주는
            테마입니다. 다크/라이트 모두 WCAG AA 이상 대비율을 충족합니다.
          </p>
        </div>

        {/* Theme Selector */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 10,
            marginBottom: 24,
          }}
        >
          {themes.map((t, i) => (
            <div key={t.id} onClick={() => setSelected(i)}>
              <MiniPreview theme={t} mode={mode} isActive={selected === i} />
            </div>
          ))}
        </div>

        {/* Mode Toggle */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 16,
          }}
        >
          <div>
            <span
              style={{ fontSize: 16, fontWeight: 800, color: "#E4E4E8" }}
            >
              {theme.emoji} {theme.nameKo}
            </span>
            {theme.recommended && (
              <span
                style={{
                  marginLeft: 8,
                  fontSize: 9,
                  fontWeight: 800,
                  backgroundColor: "#6DBB8F",
                  color: "#000",
                  padding: "3px 8px",
                  borderRadius: 4,
                }}
              >
                BEST PICK
              </span>
            )}
          </div>
          <div
            style={{
              display: "flex",
              backgroundColor: "#18181E",
              borderRadius: 10,
              padding: 3,
              border: "1px solid #2A2A35",
            }}
          >
            {["light", "dark"].map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                style={{
                  padding: "7px 18px",
                  borderRadius: 8,
                  border: "none",
                  backgroundColor: mode === m ? "#2A2A38" : "transparent",
                  color: mode === m ? "#FFF" : "#555",
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "all 0.25s ease",
                }}
              >
                {m === "light" ? "☀️ Light" : "🌙 Dark"}
              </button>
            ))}
          </div>
        </div>

        {/* Description */}
        <div
          style={{
            backgroundColor: "#14141A",
            borderRadius: 12,
            border: "1px solid #22222E",
            padding: 16,
            marginBottom: 16,
            fontSize: 13,
            color: "#9A9AAA",
            lineHeight: 1.7,
          }}
        >
          {theme.description}
          <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
            {theme.moodKeywords.map((kw) => (
              <span
                key={kw}
                style={{
                  fontSize: 10,
                  padding: "3px 10px",
                  borderRadius: 20,
                  backgroundColor:
                    (mode === "dark" ? theme.dark.accent : theme.light.accent) + "18",
                  color: mode === "dark" ? theme.dark.accent : theme.light.accent,
                  fontWeight: 600,
                }}
              >
                {kw}
              </span>
            ))}
          </div>
        </div>

        {/* Main Content: Preview + Palette */}
        <div
          key={animKey}
          style={{
            display: "grid",
            gridTemplateColumns: "1.3fr 0.7fr",
            gap: 16,
            animation: "fadeSlide 0.4s ease",
          }}
        >
          {/* Preview */}
          <div>
            <div
              style={{
                fontSize: 9,
                letterSpacing: 2,
                color: "#555",
                fontWeight: 700,
                textTransform: "uppercase",
                marginBottom: 8,
              }}
            >
              실제 적용 미리보기
            </div>
            <FullPreview theme={theme} mode={mode} />
          </div>

          {/* Palette */}
          <div>
            <div
              style={{
                fontSize: 9,
                letterSpacing: 2,
                color: "#555",
                fontWeight: 700,
                textTransform: "uppercase",
                marginBottom: 8,
              }}
            >
              컬러 시스템 + 대비율
            </div>
            <div
              style={{
                backgroundColor: "#111116",
                borderRadius: 14,
                border: "1px solid #1E1E28",
                padding: 16,
              }}
            >
              {/* Backgrounds */}
              <div
                style={{
                  fontSize: 9,
                  fontWeight: 700,
                  color: "#555",
                  letterSpacing: 1.5,
                  textTransform: "uppercase",
                  marginBottom: 6,
                }}
              >
                배경
              </div>
              <ColorRow label="Background" hex={c.bg} />
              <ColorRow label="Surface" hex={c.surface} />
              <ColorRow label="Border" hex={c.border} />

              <div
                style={{
                  height: 1,
                  backgroundColor: "#1E1E28",
                  margin: "10px 0",
                }}
              />

              {/* Text */}
              <div
                style={{
                  fontSize: 9,
                  fontWeight: 700,
                  color: "#555",
                  letterSpacing: 1.5,
                  textTransform: "uppercase",
                  marginBottom: 6,
                }}
              >
                텍스트 (on BG)
              </div>
              <ColorRow label="Primary" hex={c.textPrimary} bgHex={c.bg} />
              <ColorRow label="Secondary" hex={c.textSecondary} bgHex={c.bg} />
              <ColorRow label="Muted" hex={c.textMuted} bgHex={c.bg} />

              <div
                style={{
                  height: 1,
                  backgroundColor: "#1E1E28",
                  margin: "10px 0",
                }}
              />

              {/* Text on Surface */}
              <div
                style={{
                  fontSize: 9,
                  fontWeight: 700,
                  color: "#555",
                  letterSpacing: 1.5,
                  textTransform: "uppercase",
                  marginBottom: 6,
                }}
              >
                텍스트 (on Surface)
              </div>
              <ColorRow label="Primary" hex={c.textPrimary} bgHex={c.surface} />
              <ColorRow
                label="Secondary"
                hex={c.textSecondary}
                bgHex={c.surface}
              />

              <div
                style={{
                  height: 1,
                  backgroundColor: "#1E1E28",
                  margin: "10px 0",
                }}
              />

              {/* Accent & Status */}
              <div
                style={{
                  fontSize: 9,
                  fontWeight: 700,
                  color: "#555",
                  letterSpacing: 1.5,
                  textTransform: "uppercase",
                  marginBottom: 6,
                }}
              >
                액센트 & 상태
              </div>
              <ColorRow label="Accent" hex={c.accent} bgHex={c.bg} />
              <ColorRow label="Success" hex={c.success} />
              <ColorRow label="Warning" hex={c.warning} />
              <ColorRow label="Error" hex={c.error} />

              {/* Overall Score */}
              <div
                style={{
                  marginTop: 14,
                  padding: 10,
                  backgroundColor: "#0A0A10",
                  borderRadius: 8,
                  border: "1px solid #1A1A24",
                  textAlign: "center",
                }}
              >
                <div style={{ fontSize: 9, color: "#555", marginBottom: 4 }}>
                  전체 텍스트 대비율
                </div>
                <div style={{ display: "flex", justifyContent: "center", gap: 8 }}>
                  <div>
                    <div style={{ fontSize: 9, color: "#666", marginBottom: 2 }}>
                      제목
                    </div>
                    <WcagBadge ratio={getContrast(c.textPrimary, c.bg)} />
                  </div>
                  <div>
                    <div style={{ fontSize: 9, color: "#666", marginBottom: 2 }}>
                      본문
                    </div>
                    <WcagBadge ratio={getContrast(c.textSecondary, c.bg)} />
                  </div>
                  <div>
                    <div style={{ fontSize: 9, color: "#666", marginBottom: 2 }}>
                      보조
                    </div>
                    <WcagBadge ratio={getContrast(c.textMuted, c.bg)} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Comparison Table */}
        <div
          style={{
            marginTop: 24,
            backgroundColor: "#111116",
            borderRadius: 14,
            border: "1px solid #1E1E28",
            padding: 18,
          }}
        >
          <div
            style={{
              fontSize: 9,
              letterSpacing: 2,
              color: "#555",
              fontWeight: 700,
              textTransform: "uppercase",
              marginBottom: 14,
            }}
          >
            한눈에 비교
          </div>
          <table
            style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}
          >
            <thead>
              <tr style={{ borderBottom: "1px solid #1E1E28" }}>
                {["테마", "액센트", "느낌", "이런 분에게"].map((h) => (
                  <th
                    key={h}
                    style={{
                      textAlign: "left",
                      padding: "8px 6px",
                      fontSize: 9,
                      color: "#555",
                      fontWeight: 700,
                      letterSpacing: 1,
                      textTransform: "uppercase",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                {
                  t: themes[0],
                  feel: "자연스럽고 차분한",
                  who: "자연 친화적, 미니멀 취향",
                },
                {
                  t: themes[1],
                  feel: "따뜻하고 공감하는",
                  who: "감성적, 따뜻한 톤 선호",
                },
                {
                  t: themes[2],
                  feel: "세련되고 지적인",
                  who: "프리미엄, 모던 감성 선호",
                },
                {
                  t: themes[3],
                  feel: "편안하고 일상적",
                  who: "카페·서점 무드 선호",
                },
              ].map((row) => (
                <tr
                  key={row.t.id}
                  style={{
                    borderBottom: "1px solid #18181E",
                    opacity: selected === themes.indexOf(row.t) ? 1 : 0.6,
                    transition: "opacity 0.2s",
                  }}
                >
                  <td style={{ padding: "10px 6px" }}>
                    <div
                      style={{ display: "flex", alignItems: "center", gap: 8 }}
                    >
                      <span style={{ fontSize: 16 }}>{row.t.emoji}</span>
                      <span style={{ fontWeight: 600, fontSize: 12 }}>
                        {row.t.nameKo}
                      </span>
                      {row.t.recommended && (
                        <span
                          style={{
                            fontSize: 8,
                            fontWeight: 800,
                            backgroundColor: "#6DBB8F",
                            color: "#000",
                            padding: "1px 5px",
                            borderRadius: 3,
                          }}
                        >
                          추천
                        </span>
                      )}
                    </div>
                  </td>
                  <td style={{ padding: "10px 6px" }}>
                    <div style={{ display: "flex", gap: 4 }}>
                      <div
                        style={{
                          width: 16,
                          height: 16,
                          borderRadius: 4,
                          backgroundColor: row.t.light.accent,
                          border: "1px solid rgba(255,255,255,0.1)",
                        }}
                      />
                      <div
                        style={{
                          width: 16,
                          height: 16,
                          borderRadius: 4,
                          backgroundColor: row.t.dark.accent,
                          border: "1px solid rgba(255,255,255,0.1)",
                        }}
                      />
                    </div>
                  </td>
                  <td style={{ padding: "10px 6px", color: "#8A8A9A", fontSize: 11 }}>
                    {row.feel}
                  </td>
                  <td style={{ padding: "10px 6px", color: "#6A6A7A", fontSize: 11 }}>
                    {row.who}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Bottom Note */}
        <div
          style={{
            marginTop: 16,
            padding: 16,
            borderRadius: 12,
            backgroundColor: "#0F1A15",
            border: "1px solid #1A2E22",
            fontSize: 12,
            color: "#8BAA9A",
            lineHeight: 1.8,
          }}
        >
          <strong style={{ color: "#E4EDE8" }}>💡 추천 의견:</strong>{" "}
          <strong style={{ color: "#6DBB8F" }}>소프트 세이지</strong>를 1순위로
          추천합니다. 2030 여성 사이에서 세이지 그린은 인테리어·패션·뷰티 전반에서 가장 트렌디한 컬러이면서도, 법률 서비스에 필요한 신뢰감과 차분함을 동시에 전달합니다. 라이트 모드에서도 텍스트 가독성이 우수하고, 현재 글자색 문제를 완전히 해결할 수 있는 팔레트입니다.
          <br />
          <br />
          2순위로는 <strong style={{ color: "#C4956A" }}>웜 샌드</strong>를 제안합니다.
          "불안을 행동으로"라는 브랜드 메시지에 가장 따뜻하게 호응하는 톤이에요.
        </div>
      </div>

      <style>{`
        @keyframes fadeSlide {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
