// 가벼운 localStorage 영속화 헬퍼. 설정/온보딩 상태 유지에 사용한다.
const PREFIX = "streamcast.";

export function loadJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    if (raw == null) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function saveJson(key: string, value: unknown): void {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    /* 저장 실패는 무시 (프라이빗 모드 등) */
  }
}
