import { create } from "zustand";
import { flushSync } from "react-dom";
import { fetchConfig, postDisplay, postTrigger } from "@/api/endpoints";
import { ApiError } from "@/api/types";
import type { ServerConfig } from "@/api/types";
import { newId } from "@/lib/ids";
import { loadJson, saveJson } from "@/lib/storage";
import type {
  ChatRecord,
  ConnectionState,
  Feedback,
  VideoSource,
} from "@/types/domain";

// 방송 설명/활성 페르소나는 로컬에 영속화한다 (온보딩/설정에서 유지).
const SESSION_PREFS_KEY = "session";
interface SessionPrefs {
  channelContext: string;
  selectedPersona: string;
}
const sessionPrefs = loadJson<SessionPrefs>(SESSION_PREFS_KEY, {
  channelContext: "",
  selectedPersona: "witty_friend",
});
function persistSessionPrefs(channelContext: string, selectedPersona: string) {
  saveJson(SESSION_PREFS_KEY, { channelContext, selectedPersona });
}

// 표시된 채팅 중 최근 것은 요청 당시 서버가 recent_comments 로 조립하지만,
// 클라이언트도 중복 UI 판단을 위해 마지막 몇 개를 참고할 수 있다.

const STATUS_MESSAGES: Record<string, string> = {
  busy: "이미 생성 중인 요청이 있어요. 잠시 뒤 눌러주세요.",
  cooldown: "연속 입력을 잠깐 쉬고 있어요.",
  expired: "응답이 늦어 이번 채팅은 표시하지 않았어요.",
  duplicate: "같은 내용이 반복돼 이번 채팅은 표시하지 않았어요.",
  error: "생성하지 못했어요. 실행 터미널과 연결 설정을 확인해 주세요.",
};

/** 생성 시 외부(비디오 패널)에서 넘겨주는 순간 스냅샷 */
export interface TriggerContext {
  clickedAt: number; // performance.now()
  videoSessionId: string | null;
  clickedVideoS: number | null;
  contextVersion: number;
  /** 표시 직전 현재 영상 시점을 다시 읽기 위한 콜백 */
  readVideoTime: () => number | null;
}

interface SessionState {
  config: ServerConfig | null;
  connection: ConnectionState;
  selectedPersona: string;
  channelContext: string;

  inFlight: boolean;
  cooldownUntil: number; // performance.now() 기준
  contextVersion: number; // 영상 seek / 탭 숨김 시 증가

  messages: ChatRecord[];
  displayedCount: number;
  lastButtonMs: number | null;
  lastApiMs: number | null;

  videoSource: VideoSource;
  videoSessionId: string | null;

  feedback: Feedback;

  // actions
  loadConfig: () => Promise<void>;
  setPersona: (id: string) => void;
  setChannelContext: (text: string) => void;
  bumpContextVersion: () => void;
  setVideo: (source: VideoSource, sessionId: string | null) => void;
  generate: (ctx: TriggerContext) => Promise<void>;
  canGenerate: () => boolean;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  config: null,
  connection: "loading",
  selectedPersona: sessionPrefs.selectedPersona,
  channelContext: sessionPrefs.channelContext,

  inFlight: false,
  cooldownUntil: 0,
  contextVersion: 0,

  messages: [],
  displayedCount: 0,
  lastButtonMs: null,
  lastApiMs: null,

  videoSource: "none",
  videoSessionId: null,

  feedback: { kind: "idle", message: "실행 환경을 확인하고 있어요." },

  canGenerate: () => {
    const s = get();
    const remaining = s.cooldownUntil - performance.now();
    return !!s.config && !s.inFlight && remaining <= 0;
  },

  loadConfig: async () => {
    set({ connection: "loading", config: null });
    try {
      const config = await fetchConfig();
      const valid =
        typeof config.session_token === "string" &&
        config.session_token.length > 0 &&
        Number.isFinite(config.max_age_s) &&
        config.max_age_s > 0 &&
        Array.isArray(config.personas) &&
        config.personas.length > 0 &&
        config.personas.every(
          (p) =>
            typeof p.id === "string" &&
            typeof p.name === "string" &&
            typeof p.description === "string",
        );
      if (!valid) throw new ApiError("실행 설정을 불러오지 못했어요.");

      const prev = get().selectedPersona;
      const persona = config.personas.some((p) => p.id === prev)
        ? prev
        : config.default_persona;

      set({
        config,
        connection: "ready",
        selectedPersona: persona,
        feedback: {
          kind: "ready",
          message:
            "준비됐어요. 페르소나를 골라두고 원하는 순간에 버튼을 눌러주세요.",
        },
      });
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : "서버에 연결하지 못했어요.";
      set({ connection: "error", feedback: { kind: "error", message } });
    }
  },

  setPersona: (id) => {
    persistSessionPrefs(get().channelContext, id);
    set({ selectedPersona: id });
  },
  setChannelContext: (text) => {
    persistSessionPrefs(text, get().selectedPersona);
    set({ channelContext: text });
  },
  bumpContextVersion: () =>
    set((s) => ({ contextVersion: s.contextVersion + 1 })),
  setVideo: (source, sessionId) =>
    set((s) => ({
      videoSource: source,
      videoSessionId: sessionId,
      contextVersion: s.contextVersion + 1,
    })),

  generate: async (ctx) => {
    const s = get();
    if (!s.config || s.inFlight || performance.now() < s.cooldownUntil) return;

    const { config } = s;
    const persona = s.selectedPersona;
    const requestId = newId();

    set({
      inFlight: true,
      feedback: { kind: "working", message: "짧은 한 줄을 만들고 있어요." },
    });

    let shown = false;
    try {
      const { data: result, httpStatus } = await postTrigger(
        {
          client_request_id: requestId,
          persona,
          channel_context: s.channelContext,
          clicked_video_s: ctx.clickedVideoS,
          video_session_id: ctx.videoSessionId,
        },
        config.session_token,
      );

      // response.ok 가 아니라 status 로 분기한다.
      if (result.status !== "ready" || httpStatus >= 400) {
        if (typeof result.retry_after_s === "number") {
          applyCooldown(set, get, result.retry_after_s);
        }
        set({
          feedback: {
            kind: result.status === "error" ? "error" : "ready",
            message:
              result.error ||
              STATUS_MESSAGES[result.status] ||
              "응답 상태를 확인하지 못했어요.",
          },
        });
        return;
      }

      // ready 형식 검증
      if (
        typeof result.request_id !== "string" ||
        typeof result.comment !== "string" ||
        !result.comment.trim() ||
        result.comment.length > 100
      ) {
        throw new ApiError("채팅 응답 형식이 올바르지 않아 표시하지 않았어요.");
      }

      // 표시 직전 재검증 (영상 컨텍스트 변경 / 페이지 숨김 / 만료)
      let reason = "";
      if (
        get().contextVersion !== ctx.contextVersion ||
        get().videoSessionId !== ctx.videoSessionId
      ) {
        reason = "video_context_changed";
      } else if (document.hidden) {
        reason = "page_hidden";
      } else if (
        performance.now() - ctx.clickedAt >
        config.max_age_s * 1000
      ) {
        reason = "client_expired";
      }

      if (reason) {
        await postDisplay(
          {
            request_id: result.request_id,
            button_to_display_ms: null,
            displayed_video_s: null,
            video_session_id: ctx.videoSessionId,
            status: "discarded",
            reason,
          },
          config.session_token,
        );
        set({
          feedback: {
            kind: "ready",
            message:
              reason === "video_context_changed"
                ? "영상 위치가 바뀌어 이전 순간의 채팅은 표시하지 않았어요."
                : reason === "page_hidden"
                  ? "페이지를 보고 있지 않아 이번 채팅은 표시하지 않았어요."
                  : "응답이 늦어 이번 채팅은 표시하지 않았어요.",
          },
        });
        return;
      }

      // Commit the visible chat before acknowledging display to the server.
      const insertedAt = performance.now();
      const videoAtInsertion = ctx.readVideoTime();
      const buttonToDisplayMs = insertedAt - ctx.clickedAt;
      const apiLatencyMs =
        typeof result.api_latency_ms === "number" ? result.api_latency_ms : null;

      const record: ChatRecord = {
        requestId: result.request_id,
        persona,
        comment: result.comment,
        isMock: config.is_mock,
        videoAtInsertion,
        buttonToDisplayMs,
        apiLatencyMs,
        createdAt: Date.now(),
      };

      flushSync(() => set((prev) => ({
        messages: [...prev.messages, record],
        displayedCount: prev.displayedCount + 1,
        lastButtonMs: buttonToDisplayMs,
        lastApiMs: apiLatencyMs,
        feedback: {
          kind: "ready",
          message: `채팅을 표시했어요. 버튼부터 ${Math.round(
            buttonToDisplayMs,
          )} ms 걸렸어요.`,
        },
      })));
      shown = true;

      const acknowledgement = await postDisplay(
        {
          request_id: result.request_id,
          button_to_display_ms: buttonToDisplayMs,
          displayed_video_s: videoAtInsertion,
          video_session_id: ctx.videoSessionId,
          status: "displayed",
          reason: "",
        },
        config.session_token,
      );
      if (acknowledgement.httpStatus >= 400 || acknowledgement.data.status !== "displayed") {
        throw new ApiError("표시 기록 저장에 실패했어요.");
      }

      // 남은 쿨다운 적용
      const remaining =
        (Number(config.cooldown_s) || 0) -
        (performance.now() - ctx.clickedAt) / 1000;
      applyCooldown(set, get, remaining);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : null;
      set({
        feedback: {
          kind: "error",
          message: shown
            ? "채팅은 표시했지만 표시 기록 저장에 실패했어요. 로그를 확인해 주세요."
            : message || "요청 중 연결이 끊겼어요. 자동으로 재시도하지 않습니다.",
        },
      });
    } finally {
      set({ inFlight: false });
    }
  },
}));

function applyCooldown(
  set: (partial: Partial<SessionState>) => void,
  get: () => SessionState,
  seconds: number,
) {
  if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds <= 0) {
    return;
  }
  const until = Math.max(
    get().cooldownUntil,
    performance.now() + Math.min(seconds, 60) * 1000,
  );
  set({ cooldownUntil: until });
}
