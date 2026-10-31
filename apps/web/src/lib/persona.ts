// 페르소나별 시각 메타데이터. 서버 PERSONAS 의 id 와 1:1 대응한다.
// 서버가 내려주는 id/name/description 을 UI 의 컬러/글리프와 매핑하기 위한 표.

export interface PersonaVisual {
  accent: string; // tailwind persona.* 색상 hex
  ring: string; // 선택 시 테두리/글로우용 rgba
  soft: string; // 카드 배경 soft
  glyph: string; // 짧은 상징 문자
  label: string; // 영문 짧은 태그
}

const FALLBACK: PersonaVisual = {
  accent: "#2dd4bf",
  ring: "rgba(45,212,191,0.5)",
  soft: "rgba(45,212,191,0.10)",
  glyph: "✦",
  label: "PERSONA",
};

export const PERSONA_VISUALS: Record<string, PersonaVisual> = {
  witty_friend: {
    accent: "#f5b544",
    ring: "rgba(245,181,68,0.55)",
    soft: "rgba(245,181,68,0.10)",
    glyph: "✸",
    label: "WITTY",
  },
  warm_supporter: {
    accent: "#f472b6",
    ring: "rgba(244,114,182,0.55)",
    soft: "rgba(244,114,182,0.10)",
    glyph: "♥",
    label: "WARM",
  },
  hype_commentator: {
    accent: "#f97316",
    ring: "rgba(249,115,22,0.55)",
    soft: "rgba(249,115,22,0.10)",
    glyph: "⚡",
    label: "HYPE",
  },
  dry_comic: {
    accent: "#818cf8",
    ring: "rgba(129,140,248,0.55)",
    soft: "rgba(129,140,248,0.10)",
    glyph: "◎",
    label: "DRY",
  },
};

export function personaVisual(id: string): PersonaVisual {
  return PERSONA_VISUALS[id] ?? FALLBACK;
}
