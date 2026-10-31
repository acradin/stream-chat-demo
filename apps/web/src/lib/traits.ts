// 온보딩/설정의 "페르소나 성향" 복수 선택용 정의.
// 주의: 백엔드 /api/trigger 는 단일 persona id 만 받는다. 여기 traits 는
// 스트리머의 말투/분위기 선호 프로필(복수 선택)이며, 실제 생성 요청에는
// 이 선택을 가장 잘 대표하는 단일 백엔드 persona 로 매핑해 전달한다.

export interface Trait {
  id: string;
  label: string;
  description: string;
  accent: string;
  glyph: string;
  /** 이 성향이 매핑되는 백엔드 persona id */
  mapsTo: string;
}

export const TRAITS: Trait[] = [
  {
    id: "cheerful",
    label: "유쾌한",
    description: "밝고 경쾌하게 분위기를 띄워요",
    accent: "#f5b544",
    glyph: "☺",
    mapsTo: "witty_friend",
  },
  {
    id: "friendly",
    label: "친근한",
    description: "편하게 말 거는 친구 같은 말투",
    accent: "#f472b6",
    glyph: "♥",
    mapsTo: "witty_friend",
  },
  {
    id: "immersive",
    label: "과몰입",
    description: "상황에 푹 빠져 신나게 해설",
    accent: "#f97316",
    glyph: "⚡",
    mapsTo: "hype_commentator",
  },
  {
    id: "calm",
    label: "차분한",
    description: "담백하고 낮은 톤으로 차분하게",
    accent: "#818cf8",
    glyph: "◎",
    mapsTo: "dry_comic",
  },
  {
    id: "playful",
    label: "장난스러운",
    description: "툭툭 던지는 가벼운 장난과 드립",
    accent: "#2dd4bf",
    glyph: "✸",
    mapsTo: "witty_friend",
  },
  {
    id: "supportive",
    label: "응원하는",
    description: "따뜻하게 힘을 실어주는 응원",
    accent: "#34d399",
    glyph: "✧",
    mapsTo: "warm_supporter",
  },
];

export function traitById(id: string): Trait | undefined {
  return TRAITS.find((t) => t.id === id);
}

/**
 * 선택된 성향들에서 대표 백엔드 persona 를 고른다.
 * 가장 많이 매핑된 persona 를 선택, 동률이면 선택 순서가 앞선 것.
 * 선택이 없으면 null.
 */
export function primaryPersonaFromTraits(
  traitIds: string[],
  validPersonaIds: string[],
): string | null {
  const counts = new Map<string, number>();
  for (const id of traitIds) {
    const t = traitById(id);
    if (!t || !validPersonaIds.includes(t.mapsTo)) continue;
    counts.set(t.mapsTo, (counts.get(t.mapsTo) ?? 0) + 1);
  }
  let best: string | null = null;
  let bestCount = 0;
  for (const [persona, count] of counts) {
    if (count > bestCount) {
      best = persona;
      bestCount = count;
    }
  }
  return best;
}
