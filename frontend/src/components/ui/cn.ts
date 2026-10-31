/** 조건부 클래스 병합용 경량 헬퍼 (clsx 대체). */
export function cn(
  ...parts: Array<string | false | null | undefined>
): string {
  return parts.filter(Boolean).join(" ");
}
