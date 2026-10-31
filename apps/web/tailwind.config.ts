import type { Config } from "tailwindcss";

// 디자이너 시안 기준 토큰 (tiki).
// Window #303030 / Elevated #484848 / Input #686868 / Track #626262
// Brand: #03FFD5 -> #2DFF8F (그라데이션), Online #EF454F
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // 창/표면 레이어
        window: "#303030",
        surface: "#484848",
        input: "#686868",
        track: "#626262",
        // 브라우저 배경(앱 창 뒤). 'backdrop' 은 Tailwind 예약 접두어와
        // 겹치므로 'canvas' 로 둔다.
        canvas: "#141414",

        base: {
          950: "#141414",
          900: "#1e1e1e",
          850: "#2a2a2a",
          800: "#303030",
          750: "#3a3a3a",
          700: "#484848",
          600: "#5a5a5a",
        },
        line: {
          soft: "#3d3d3d",
          DEFAULT: "#4a4a4a",
          strong: "#5c5c5c",
        },
        ink: {
          DEFAULT: "#ffffff",
          soft: "#c8c8c8",
          faint: "#a0a0a0",
        },
        // 브랜드 포인트 (민트 -> 그린)
        brand: {
          DEFAULT: "#03FFD5",
          soft: "#2DFF8F",
          deep: "#06c6a6",
          glow: "#20d8b0",
        },
        online: "#EF454F",
        win: {
          close: "#EF454F",
          min: "#F5C04E",
        },
        // 페르소나 액센트 (설정/온보딩에서 사용) — 브랜드 톤과 공존
        persona: {
          witty: "#2DFF8F",
          warm: "#03FFD5",
          hype: "#5be8c0",
          dry: "#8fe9cf",
        },
        status: {
          ok: "#2DFF8F",
          warn: "#F5C04E",
          error: "#EF454F",
          info: "#03FFD5",
        },
      },
      fontFamily: {
        sans: [
          "Pretendard",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Apple SD Gothic Neo",
          "Noto Sans KR",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: {
        window: "40px",
      },
      boxShadow: {
        window: "0 30px 80px -24px rgba(0,0,0,0.85), 0 0 0 1px rgba(255,255,255,0.04)",
        orb: "0 0 0 1px rgba(255,255,255,0.18), 0 0 46px -4px rgba(45,255,143,0.55), 0 20px 50px -18px rgba(3,255,213,0.5)",
        "orb-hover":
          "0 0 0 1px rgba(255,255,255,0.28), 0 0 64px 0px rgba(45,255,143,0.7), 0 22px 54px -16px rgba(3,255,213,0.6)",
      },
      backgroundImage: {
        brand: "linear-gradient(135deg, #03FFD5 0%, #2DFF8F 100%)",
        "brand-orb":
          "radial-gradient(circle at 50% 30%, #2DFF8F 0%, #0fd9b0 55%, #06c6a6 100%)",
      },
      keyframes: {
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
      },
      animation: {
        "pulse-dot": "pulse-dot 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
