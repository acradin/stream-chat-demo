import { create } from "zustand";
import { loadJson, saveJson } from "@/lib/storage";
import {
  ABSOLUTE_MAX_CHATS,
  planMaxChats,
  type PlanId,
} from "@/lib/plans";

// 앱 화면 라우팅 + 스트리머 선호/플랜 상태. UI 전용이며 API 흐름(sessionStore)과 분리.
// 결제/구독 검증은 미연동 — plan 은 UI 게이팅 구조만 제공한다.
// localStorage 의 plan 값을 실제 유료 결제 인증으로 취급하지 않는다.

export type Screen =
  | "onboarding"
  | "main"
  | "settings"
  | "pricing"
  | "checkout";

// 슬라이더 UI 는 1~5 를 유지하되, 5 는 어떤 플랜에서도 불가(미지원) 구간.
const SLIDER_MAX = 5;

interface PersistedPrefs {
  onboarded: boolean;
  traitIds: string[];
  hotkey: string;
  chatCount: number;
  plan: PlanId;
}

const PREFS_KEY = "prefs";

const DEFAULT_PREFS: PersistedPrefs = {
  onboarded: false,
  traitIds: [],
  hotkey: "Space",
  chatCount: 1,
  plan: "free",
};

interface UiState {
  screen: Screen;
  plan: PlanId;
  checkoutPlan: PlanId | null; // 결제 확인 화면에서 볼 플랜
  planNotice: string | null; // 슬라이더 업그레이드 안내

  onboarded: boolean;
  traitIds: string[];
  hotkey: string;
  chatCount: number;

  goTo: (screen: Screen) => void;
  openCheckout: (plan: PlanId) => void;
  setPlan: (plan: PlanId) => void;
  clearPlanNotice: () => void;

  toggleTrait: (id: string) => void;
  setHotkey: (hotkey: string) => void;
  requestChatCount: (value: number) => void;

  completeOnboarding: () => void;
  resetOnboarding: () => void;
}

const persistedRaw = loadJson<PersistedPrefs>(PREFS_KEY, DEFAULT_PREFS);
// 이전 버전(plan: basic/plus)과의 호환: 알 수 없는 값은 free 로.
const initialPlan: PlanId =
  persistedRaw.plan === "pro" || persistedRaw.plan === "mega"
    ? persistedRaw.plan
    : "free";

// 이전 버전 hotkey 값 호환: 빈 값/과거 "CapsLock" 표기를 정규화.
function normalizeHotkey(raw: unknown): string {
  if (typeof raw !== "string" || !raw.trim()) return "Space";
  if (raw === "CapsLock") return "Caps Lock";
  return raw;
}
const initialHotkey = normalizeHotkey(persistedRaw.hotkey);

function persistFrom(s: UiState) {
  const toSave: PersistedPrefs = {
    onboarded: s.onboarded,
    traitIds: s.traitIds,
    hotkey: s.hotkey,
    chatCount: s.chatCount,
    plan: s.plan,
  };
  saveJson(PREFS_KEY, toSave);
}

export const useUiStore = create<UiState>((set, get) => ({
  screen: persistedRaw.onboarded ? "main" : "onboarding",
  plan: initialPlan,
  checkoutPlan: null,
  planNotice: null,

  onboarded: persistedRaw.onboarded,
  traitIds: persistedRaw.traitIds,
  hotkey: initialHotkey,
  chatCount: Math.min(persistedRaw.chatCount, planMaxChats(initialPlan)),

  goTo: (screen) => set({ screen }),

  openCheckout: (plan) => set({ checkoutPlan: plan, screen: "checkout" }),

  setPlan: (plan) =>
    set((s) => {
      const max = planMaxChats(plan);
      const next = { ...s, plan, chatCount: Math.min(s.chatCount, max) };
      persistFrom(next);
      return { plan, chatCount: next.chatCount, planNotice: null };
    }),

  clearPlanNotice: () => set({ planNotice: null }),

  toggleTrait: (id) =>
    set((s) => {
      const traitIds = s.traitIds.includes(id)
        ? s.traitIds.filter((t) => t !== id)
        : [...s.traitIds, id];
      const next = { ...s, traitIds };
      persistFrom(next);
      return { traitIds };
    }),

  setHotkey: (hotkey) =>
    set((s) => {
      const next = { ...s, hotkey };
      persistFrom(next);
      return { hotkey };
    }),

  requestChatCount: (value) => {
    const s = get();
    const clamped = Math.max(1, Math.min(SLIDER_MAX, Math.round(value)));

    // 5명: 어떤 플랜에서도 지원하지 않는 구간. 업그레이드로도 불가 안내.
    if (clamped > ABSOLUTE_MAX_CHATS) {
      set({
        planNotice:
          "5명은 현재 모든 플랜에서 지원하지 않아요. 최대 4명(MEGA)까지 이용할 수 있어요.",
      });
      return;
    }

    const max = planMaxChats(s.plan);
    if (clamped > max) {
      // 현재 플랜 한도 초과 — 값은 유지하고 업그레이드 안내
      const needed = clamped <= planMaxChats("pro") ? "PRO" : "MEGA";
      set({
        planNotice: `${clamped}명은 ${needed} 플랜부터 사용할 수 있어요. 현재 플랜에서는 ${max}명까지 가능합니다.`,
      });
      return;
    }

    const next = { ...s, chatCount: clamped };
    persistFrom(next);
    set({ chatCount: clamped, planNotice: null });
  },

  completeOnboarding: () =>
    set((s) => {
      const next = { ...s, onboarded: true };
      persistFrom(next);
      return { onboarded: true, screen: "main" };
    }),

  resetOnboarding: () =>
    set((s) => {
      const next = { ...s, onboarded: false };
      persistFrom(next);
      return { onboarded: false, screen: "onboarding" };
    }),
}));
