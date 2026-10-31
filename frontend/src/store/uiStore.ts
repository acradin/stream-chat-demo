import { create } from "zustand";
import { loadJson, saveJson } from "@/lib/storage";

// 앱 화면 라우팅 + 스트리머 선호/플랜 상태. UI 전용이며 API 흐름(sessionStore)과 분리.
// 결제/구독 검증은 미연동 — plan 은 UI 게이팅 구조만 제공한다.

export type Screen = "onboarding" | "main" | "settings";
export type Plan = "basic" | "plus";

interface PersistedPrefs {
  onboarded: boolean;
  traitIds: string[]; // 복수 선택된 성향
  hotkey: string; // 생성 단축키 (브라우저 범위)
  chatCount: number; // AI 채팅 계정 수 (1~5)
}

const PREFS_KEY = "prefs";

const DEFAULT_PREFS: PersistedPrefs = {
  onboarded: false,
  traitIds: [],
  hotkey: "Space",
  chatCount: 1,
};

// 플랜별 최대 AI 채팅 수
export const PLAN_MAX_CHATS: Record<Plan, number> = {
  basic: 1,
  plus: 5,
};

interface UiState {
  screen: Screen;
  plan: Plan; // 데모: 기본 basic. 실제 구독 검증 미연동
  planNotice: string | null; // Plus 안내 메시지

  // persisted prefs
  onboarded: boolean;
  traitIds: string[];
  hotkey: string;
  chatCount: number;

  // actions
  goTo: (screen: Screen) => void;
  setPlan: (plan: Plan) => void;
  clearPlanNotice: () => void;

  toggleTrait: (id: string) => void;
  setHotkey: (hotkey: string) => void;
  /** 슬라이더로 채팅 수 변경 시도. 플랜 한도 초과면 거부하고 안내. */
  requestChatCount: (value: number) => void;

  completeOnboarding: () => void;
  resetOnboarding: () => void;
}

const persisted = loadJson<PersistedPrefs>(PREFS_KEY, DEFAULT_PREFS);

function persist(state: UiState) {
  const toSave: PersistedPrefs = {
    onboarded: state.onboarded,
    traitIds: state.traitIds,
    hotkey: state.hotkey,
    chatCount: state.chatCount,
  };
  saveJson(PREFS_KEY, toSave);
}

export const useUiStore = create<UiState>((set, get) => ({
  screen: persisted.onboarded ? "main" : "onboarding",
  plan: "basic",
  planNotice: null,

  onboarded: persisted.onboarded,
  traitIds: persisted.traitIds,
  hotkey: persisted.hotkey,
  chatCount: Math.min(
    persisted.chatCount,
    PLAN_MAX_CHATS.basic, // 로드 시 현재 플랜 한도로 클램프
  ),

  goTo: (screen) => set({ screen }),
  setPlan: (plan) =>
    set((s) => {
      const max = PLAN_MAX_CHATS[plan];
      const next = { ...s, plan, chatCount: Math.min(s.chatCount, max) };
      persist(next);
      return { plan, chatCount: next.chatCount, planNotice: null };
    }),
  clearPlanNotice: () => set({ planNotice: null }),

  toggleTrait: (id) =>
    set((s) => {
      const has = s.traitIds.includes(id);
      const traitIds = has
        ? s.traitIds.filter((t) => t !== id)
        : [...s.traitIds, id];
      const next = { ...s, traitIds };
      persist(next);
      return { traitIds };
    }),

  setHotkey: (hotkey) =>
    set((s) => {
      const next = { ...s, hotkey };
      persist(next);
      return { hotkey };
    }),

  requestChatCount: (value) => {
    const s = get();
    const clamped = Math.max(1, Math.min(5, Math.round(value)));
    const max = PLAN_MAX_CHATS[s.plan];
    if (clamped > max) {
      // 플랜 한도 초과 — 값 변경하지 않고 안내만 표시
      set({
        planNotice:
          "2명 이상의 AI 채팅은 Plus 플랜에서 사용할 수 있어요. 현재 플랜에서는 1명까지 가능합니다.",
      });
      return;
    }
    const next = { ...s, chatCount: clamped };
    persist(next);
    set({ chatCount: clamped, planNotice: null });
  },

  completeOnboarding: () =>
    set((s) => {
      const next = { ...s, onboarded: true };
      persist(next);
      return { onboarded: true, screen: "main" };
    }),

  resetOnboarding: () =>
    set((s) => {
      const next = { ...s, onboarded: false };
      persist(next);
      return { onboarded: false, screen: "onboarding" };
    }),
}));
