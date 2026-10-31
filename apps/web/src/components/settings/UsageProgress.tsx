import { useSessionStore } from "@/store/sessionStore";
import { formatCount } from "@/lib/format";

// 백엔드는 월간 사용량/한도 데이터를 제공하지 않는다.
// 실제 수치인 "이번 세션 생성 횟수"만 사용하고, 한도(1,000)는 데모 기준임을 명시한다.
// 가짜 월간 수치를 실제처럼 노출하지 않는다.
const DEMO_QUOTA = 1000;

export function UsageProgress() {
  const used = useSessionStore((s) => s.displayedCount);
  const pct = Math.min(100, (used / DEMO_QUOTA) * 100);

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <span className="text-[12px] text-ink-faint">
          이번 세션 사용량
          <span className="ml-1.5 rounded bg-surface px-1 py-0.5 text-[9px] font-bold tracking-wide text-ink-faint">
            한도 DEMO
          </span>
        </span>
        <span className="font-mono text-[13px] font-semibold text-ink">
          {formatCount(used)} / {formatCount(DEMO_QUOTA)}회
        </span>
      </div>
      <div
        className="h-3 w-full overflow-hidden rounded-full"
        style={{ background: "#626262" }}
      >
        <div
          className="h-full rounded-full transition-[width] duration-300"
          style={{
            width: `${Math.max(pct, used > 0 ? 3 : 0)}%`,
            background: "linear-gradient(90deg, #03FFD5, #2DFF8F)",
          }}
        />
      </div>
      <p className="mt-1.5 text-[10px] text-ink-faint">
        월간 누적 사용량/요금제 한도는 서비스 연동 시 제공됩니다. 현재 수치는
        이번 세션 기준입니다.
      </p>
    </div>
  );
}
