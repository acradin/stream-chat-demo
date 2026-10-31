import { ChevronRight, Crown } from "lucide-react";
import { useUiStore } from "@/store/uiStore";

/**
 * 메인 하단 업그레이드 CTA. 클릭하면 PricingPage 로 이동.
 * 기존 Plus 안내 박스를 대체한다. 민트 계열 배경 + 왕관 + 화살표.
 */
export function UpgradeCta() {
  const goTo = useUiStore((s) => s.goTo);
  const plan = useUiStore((s) => s.plan);

  return (
    <button
      type="button"
      onClick={() => goTo("pricing")}
      aria-label="요금제 업그레이드 보기"
      className="group flex w-full items-center gap-3 rounded-2xl border border-brand/25 bg-brand/10 px-4 py-3 text-left transition hover:bg-brand/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"
    >
      <span className="grid h-9 w-9 flex-none place-items-center rounded-xl bg-brand/20 text-brand">
        <Crown className="h-4.5 w-4.5" style={{ width: 18, height: 18 }} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[13px] font-bold text-ink">
          더 많은 AI 채팅 멤버가 필요하신가요?
        </span>
        <span className="mt-0.5 block text-[11px] text-ink-faint">
          PRO 최대 2명 · MEGA 최대 4명
          {plan !== "free" && (
            <span className="ml-1 text-brand">· 현재 {plan.toUpperCase()}</span>
          )}
        </span>
      </span>
      <ChevronRight className="h-5 w-5 flex-none text-brand transition group-hover:translate-x-0.5" />
    </button>
  );
}
