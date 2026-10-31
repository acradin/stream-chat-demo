import { useEffect, useState } from "react";
import { useSessionStore } from "@/store/sessionStore";

/**
 * 쿨다운 남은 시간(초)을 주기적으로 갱신해 버튼 라벨/비활성에 반영한다.
 * cooldownUntil 은 performance.now() 기준이라 스토어 구독만으로는
 * 시간 경과에 따른 리렌더가 발생하지 않으므로 타이머로 틱을 돌린다.
 */
export function useCooldownTick(): number {
  const cooldownUntil = useSessionStore((s) => s.cooldownUntil);
  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const left = Math.max(0, cooldownUntil - performance.now());
      setRemaining(left);
      if (left > 0) {
        raf = window.setTimeout(tick, 100);
      }
    };
    tick();
    return () => window.clearTimeout(raf);
  }, [cooldownUntil]);

  return remaining;
}
