// apps.web.server API 계약의 TypeScript 표현.
// 로컬 및 공개 웹 API와 같은 계약을 사용한다.

export interface PersonaConfig {
  id: string;
  name: string;
  description: string;
}

/** GET /api/config 응답 */
export interface ServerConfig {
  provider: string;
  model: string;
  is_mock: boolean;
  supports_frames?: boolean;
  session_token: string;
  cooldown_s: number;
  max_age_s: number;
  session_limit?: number;
  remaining_requests?: number;
  default_persona: string;
  personas: PersonaConfig[];
}

/** 영상 체험 시 버튼을 누른 장면의 JPEG 한 장을 추가한다. */
export interface TriggerRequest {
  client_request_id: string;
  persona: string;
  channel_context: string;
  clicked_video_s: number | null;
  video_session_id: string | null;
  frame_jpeg?: string;
  demo_video_id?: string;
}

/**
 * POST /api/trigger 응답.
 * 업무 상태(busy/cooldown/expired/duplicate/error)도 HTTP 200 으로 올 수 있으므로
 * response.ok 가 아니라 status 필드로 분기해야 한다.
 */
export type TriggerStatus =
  | "ready"
  | "busy"
  | "cooldown"
  | "expired"
  | "duplicate"
  | "error";

export interface TriggerResponse {
  status: TriggerStatus;
  request_id?: string;
  comment?: string;
  api_latency_ms?: number | null;
  error?: string | null;
  retry_after_s?: number;
}

/** POST /api/display 요청 본문 — 정확히 이 6개 키만 보낸다. */
export interface DisplayRequest {
  request_id: string;
  button_to_display_ms: number | null;
  displayed_video_s: number | null;
  video_session_id: string | null;
  status: "displayed" | "discarded";
  reason: string;
}

export interface DisplayResponse {
  status: string;
  request_id: string;
}

/** 폐기 사유 (클라이언트 측 판정) */
export type DiscardReason =
  | "video_context_changed"
  | "page_hidden"
  | "client_expired";

export class ApiError extends Error {
  readonly httpStatus: number | null;
  constructor(message: string, httpStatus: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.httpStatus = httpStatus;
  }
}
