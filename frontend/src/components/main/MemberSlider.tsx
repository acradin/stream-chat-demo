import { useRef } from "react";
import { Crown, Lock } from "lucide-react";
import { PLAN_MAX_CHATS, useUiStore } from "@/store/uiStore";
import { cn } from "../ui/cn";

/**
 * 연속형 채팅 멤버 슬라이더 (1~5).
 * 회색 트랙 + 브랜드 그라데이션 채움 + 흰 테두리 민트 핸들.
 * Basic 은 1명만. 2~5 시도 시 값은 1 유지 + Plus 안내(반복 팝업 방지).
 */
const STEPS = [1, 2, 3, 4, 5];

export function MemberSlider() {
  const plan = useUiStore((s) => s.plan);
  const chatCount = useUiStore((s) => s.chatCount);
  const request = useUiStore((s) => s.requestChatCount);
  const notice = useUiStore((s) => s.planNotice);
  const trackRef = useRef<HTMLDivElement>(null);

  const max = PLAN_MAX_CHATS[plan];
  // 핸들/채움 위치: 1->0%, 5->100%
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
        {/* 채움 */}
        <div
          className="absolute left-0 top-0 h-full rounded-full"
          style={{
            width: `${pct}%`,
            background: "linear-gradient(90deg, #03FFD5, #2DFF8F)",
          }}
        />
        {/* 눈금 구분선 */}
        {STEPS.slice(1, -1).map((n) => (
          <span
            key={n}
            className="absolute top-1/2 h-2.5 w-px -translate-y-1/2 bg-black/25"
            style={{ left: `${((n - 1) / (STEPS.length - 1)) * 100}%` }}
          />
        ))}
        {/* 핸들 */}
        <span
          className="absolute top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-white shadow"
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
          const locked = n > max;
          return (
            <button
              key={n}
              type="button"
              onClick={() => request(n)}
              className={cn(
                "flex flex-col items-center gap-0.5 text-[13px] font-semibold tabular-nums",
                n === chatCount ? "text-ink" : "text-ink-faint",
              )}
            >
              {n}
              {locked && <Lock className="h-2.5 w-2.5 text-ink-faint" />}
            </button>
          );
        })}
      </div>

      {/* 왕관 + Plus 안내 */}
      <div className="mt-3 flex items-center justify-center gap-1.5">
        <Crown className="h-3.5 w-3.5 text-ink-faint" />
        <span
          className={cn(
            "rounded-md px-2 py-0.5 text-[11px]",
            notice
              ? "bg-brand/15 text-brand"
              : "bg-surface text-ink-faint",
          )}
        >
          {notice ?? "2명 이상은 Plus 플랜에서 사용할 수 있어요."}
        </span>
      </div>
    </div>
  );
}
