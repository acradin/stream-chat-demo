// 요금제 정의 (UI 데모용). 실제 결제/구독 인증은 연동되지 않았으며,
// localStorage 의 plan 값을 유료 결제 인증으로 취급하지 않는다.

export type PlanId = "free" | "pro" | "mega";

export interface Plan {
  id: PlanId;
  name: string;
  priceLabel: string; // 표시용 가격
  priceSub: string; // 가격 보조 문구
  maxChats: number; // 허용 최대 AI 채팅 멤버
  recommended: boolean;
  paid: boolean;
  features: string[];
}

export const PLANS: Record<PlanId, Plan> = {
  free: {
    id: "free",
    name: "FREE",
    priceLabel: "₩0",
    priceSub: "영구 무료",
    maxChats: 1,
    recommended: false,
    paid: false,
    features: ["AI 채팅 1명", "제한된 사용량", "데모 환경 제공"],
  },
  pro: {
    id: "pro",
    name: "PRO",
    priceLabel: "₩29,000",
    priceSub: "/ 월",
    maxChats: 2,
    recommended: true,
    paid: true,
    features: [
      "AI 채팅 2명",
      "플랫폼 1개 선택",
      "AI 캐릭터 기본 설정",
      "실시간 채팅 반응",
    ],
  },
  mega: {
    id: "mega",
    name: "MEGA",
    priceLabel: "₩59,000",
    priceSub: "/ 월",
    maxChats: 4,
    recommended: false,
    paid: true,
    features: [
      "AI 채팅 4명",
      "멀티 플랫폼 지원",
      "AI 캐릭터 고급 설정",
      "고도화된 반응 모델",
      "우선 처리 및 빠른 반응",
    ],
  },
};

export const PLAN_ORDER: PlanId[] = ["free", "pro", "mega"];

/** 모든 플랜 중 최대 허용 인원 (이 값을 넘는 구간은 어떤 플랜에서도 불가) */
export const ABSOLUTE_MAX_CHATS = Math.max(
  ...PLAN_ORDER.map((id) => PLANS[id].maxChats),
); // = 4

export function planMaxChats(id: PlanId): number {
  return PLANS[id].maxChats;
}
