export function formatMs(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return Math.round(value).toLocaleString("ko-KR");
}

export function formatCount(value: number): string {
  return value.toLocaleString("ko-KR");
}

export function formatSeconds(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "영상 없이 생성";
  return `영상 ${value.toFixed(2)}초`;
}

/** 유니코드 문자 수 (한글 1,000자 제한 카운트용) */
export function charCount(text: string): number {
  return Array.from(text).length;
}

/**
 * 단축키 저장값(uiStore.hotkey)을 화면 표시용 라벨로 변환한다.
 * 설정 화면과 메인 버튼이 동일한 규칙을 쓰도록 하는 단일 포매터.
 * 저장값을 그대로 보여준다. (Space -> "Space", Caps Lock -> "Caps Lock",
 * "Ctrl + G" 등 조합키도 저장된 표기 그대로)
 */
export function formatHotkey(hotkey: string): string {
  return hotkey && hotkey.trim() ? hotkey : "Space";
}
