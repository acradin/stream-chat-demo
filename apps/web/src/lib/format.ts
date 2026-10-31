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
