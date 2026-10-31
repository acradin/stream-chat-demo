import { useRef } from "react";
import { Lock } from "lucide-react";
import { useUiStore } from "@/store/uiStore";
import { planMaxChats } from "@/lib/plans";
import { cn } from "../ui/cn";

/**
 * 연속형 채팅 멤버 슬라이더. UI 는 1~5 를 유지한다.
 * - 현재 플랜 한도 초과: 값 유지 + 업그레이드 안내 + "플랜 비교하기"
 * - 5명: 어떤 플랜에서도 미지원 구간 (업그레이드로도 불가 안내)
 */
const STEPS = [1, 2, 3, 4, 5];
const UNSUPPORTED_FROM = 5; // 5 이상은 전 플랜 미지원

export function MemberSlider() {
  const plan = useUiStore((s) => s.plan);
  const chatCount = useUiStore((s) => s.chatCount);
  const request = useUiStore((s) => s.requestChatCount);
  const notice = useUiStore((s) => s.planNotice);
  const goTo = useUiStore((s) => s.goTo);
  const trackRef = useRef<HTMLDivElement>(null);

  const max = planMaxChats(plan);
  const pct = ((chatCount - 1) / (STEPS.length - 1)) * 100;

  function valueFromClientX(clientX: number): number {
    const el = trackRef.current;
    if (!el) return chatCount;
    const rect = el.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    return Math.round(ratio * (STEPS.length - 1)) + 1;
  }

  return (
    <div className="w-full">
      <div className="mb-3 flex items-baseline justify-between">
        <span className="text-[17px] font-bold text-ink">채팅 멤버</span>
        <span className="text-[17px] font-bold text-ink">{chatCount}명</span>
      </div>

      {/* 트랙 */}
      <div
        ref={trackRef}
        role="slider"
        aria-label="채팅 멤버 수"
        aria-valuemin={1}
        aria-valuemax={5}
        aria-valuenow={chatCount}
        tabIndex={0}
        onClick={(e) => request(valueFromClientX(e.clientX))}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight" || e.key === "ArrowUp") {
            e.preventDefault();
            request(chatCount + 1);
          } else if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
            e.preventDefault();
            request(chatCount - 1);
          }
        }}
        className="relative h-2.5 cursor-pointer rounded-full"
        style={{ background: "#626262" }}
      >
        <div
          className="absolute left-0 top-0 h-full rounded-full"
          style={{
            width: `${pct}%`,
            background: "linear-gradient(90deg, #03FFD5, #2DFF8F)",
          }}
        />
        {STEPS.slice(1, -1).map((n) => (
          <span
            key={n}
            className="absolute top-1/2 h-2.5 w-px -translate-y-1/2 bg-black/25"
            style={{ left: `${((n - 1) / (STEPS.length - 1)) * 100}%` }}
          />
        ))}
        <span
          className="absolute top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-white"
          style={{
            left: `${pct}%`,
            background: "#2DFF8F",
            boxShadow: "0 2px 8px rgba(0,0,0,0.4)",
          }}
        />
      </div>

      {/* 숫자 + 자물쇠 */}
      <div className="mt-2 flex justify-between px-0.5">
        {STEPS.map((n) => {
          const lockedByPlan = n > max;
          const unsupported = n >= UNSUPPORTED_FROM;
          return (
            <button
              key={n}
              type="button"
              onClick={() => request(n)}
              title={
                unsupported
                  ? "모든 플랜 미지원"
                  : lockedByPlan
                    ? "상위 플랜 필요"
                    : `${n}명`
              }
              className={cn(
                "flex flex-col items-center gap-0.5 text-[13px] font-semibold tabular-nums",
                n === chatCount ? "text-ink" : "text-ink-faint",
                unsupported && "opacity-45",
              )}
            >
              {n}
              {(lockedByPlan || unsupported) && (
                <Lock className="h-2.5 w-2.5 text-ink-faint" />
              )}
            </button>
          );
        })}
      </div>

      {/* 업그레이드 안내 (한도 초과 시도 시) */}
      {notice && (
        <div className="mt-3 flex items-center justify-between gap-2 rounded-lg bg-brand/10 px-3 py-2">
          <span className="text-[11px] leading-snug text-brand">{notice}</span>
          <button
            type="button"
            onClick={() => goTo("pricing")}
            className="flex-none rounded-md bg-brand/20 px-2.5 py-1 text-[11px] font-semibold text-brand transition hover:bg-brand/30"
          >
            플랜 비교하기
          </button>
        </div>
      )}
    </div>
  );
}
