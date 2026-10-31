// 온보딩/설정의 "페르소나 성향" 복수 선택용 정의.
// 주의: 백엔드 /api/trigger 는 단일 persona id 만 받는다. 여기 traits 는
// 스트리머의 말투/분위기 선호 프로필(복수 선택)이며, 실제 생성 요청에는
// 이 선택을 가장 잘 대표하는 단일 백엔드 persona 로 매핑해 전달한다.

export interface Trait {
  id: string;
  label: string;
  description: string;
  accent: string;
  image: string;
  /** 이 성향이 매핑되는 백엔드 persona id */
  mapsTo: string;
}

export const TRAITS: Trait[] = [
  {
    id: "cheerful",
    label: "유쾌한 친구",
    description: "재치있는 드립과 적절한 놀림으로 방송을 활발하게 만들어주는 스타일",
    accent: "#f5b544",
    image: "/personas/witty.png",
    mapsTo: "witty_friend",
  },
  {
    id: "friendly",
    label: "수다쟁이",
    description: "끊임없는 질문과 대화로 방송의 적막을 채워주는 스타일",
    accent: "#f472b6",
    image: "/personas/chatter.png",
    mapsTo: "witty_friend",
  },
  {
    id: "immersive",
    label: "리액션봇",
    description: "사소한 순간에도 적극적으로 반응하며 방송의 재미를 살려주는 스타일",
    accent: "#f97316",
    image: "/personas/reaction.png",
    mapsTo: "hype_commentator",
  },
  {
    id: "calm",
    label: "분석러",
    description: "게임 상황을 빠르게 분석하고 날카로운 판단과 전략을 제시하는 스타일",
    accent: "#818cf8",
    image: "/personas/analyst.png",
    mapsTo: "dry_comic",
  },
  {
    id: "playful",
    label: "훈수형",
    description: "거침없는 참견과 잔소리로 방송에 재미를 더해주는 스타일",
    accent: "#2dd4bf",
    image: "/personas/coach.png",
    mapsTo: "witty_friend",
  },
  {
    id: "supportive",
    label: "응원러",
    description: "아낌없는 칭찬과 긍정적인 반응으로 방송에 활력을 불어넣는 스타일",
    accent: "#34d399",
    image: "/personas/supporter.png",
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
