export type ConnectionState = "loading" | "ready" | "error";

export type VideoSource = "none" | "sample" | "local";

/** 화면에 표시된(또는 폐기된) 하나의 채팅 기록 */
export interface ChatRecord {
  requestId: string;
  persona: string;
  comment: string;
  isMock: boolean;
  videoAtInsertion: number | null;
  buttonToDisplayMs: number | null;
  apiLatencyMs: number | null;
  createdAt: number; // Date.now()
}

/** 상태 피드백 메시지 */
export type FeedbackKind = "idle" | "working" | "ready" | "error";

export interface Feedback {
  kind: FeedbackKind;
  message: string;
}
