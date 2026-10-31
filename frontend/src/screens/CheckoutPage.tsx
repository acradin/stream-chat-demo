import { ArrowLeft, Check, Info, Lock } from "lucide-react";
import { useUiStore } from "@/store/uiStore";
import { PLANS } from "@/lib/plans";
import { AppWindow } from "@/components/window/AppWindow";
import { WindowControls } from "@/components/window/WindowControls";
import { Logo } from "@/components/shared/Logo";

/**
 * 결제 확인 화면. 선택 플랜 요약 + 자동 갱신 안내.
 * 실제 결제 API 미연동 — 버튼은 "결제 연동 준비 중"으로 비활성.
 * 카드 정보 입력/결제 완료 처리를 하지 않는다.
 */
export function CheckoutPage() {
  const goTo = useUiStore((s) => s.goTo);
  const checkoutPlan = useUiStore((s) => s.checkoutPlan);

  // 잘못된 진입(플랜 미선택) 방어
  if (!checkoutPlan || !PLANS[checkoutPlan].paid) {
    return (
      <AppWindow width={460}>
        <div className="px-6 py-10 text-center">
          <p className="text-[13px] text-ink-soft">
            선택된 유료 플랜이 없어요.
          </p>
          <button
            type="button"
            onClick={() => goTo("pricing")}
            className="mt-4 rounded-xl bg-surface px-4 py-2 text-[13px] font-semibold text-ink"
          >
            요금제로 돌아가기
          </button>
        </div>
      </AppWindow>
    );
  }

  const plan = PLANS[checkoutPlan];

  return (
    <AppWindow width={460}>
      <header className="flex items-center justify-between px-6 pt-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => goTo("pricing")}
            title="요금제로"
            className="grid h-7 w-7 place-items-center rounded-md text-ink-soft transition hover:text-white"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <Logo />
        </div>
        <WindowControls />
      </header>

      <div className="px-6 py-6">
        <h2 className="text-[18px] font-bold text-ink">결제 확인</h2>
        <p className="mt-1 text-[12px] text-ink-faint">
          선택한 플랜 내용을 확인하세요.
        </p>

        {/* 선택 플랜 요약 */}
        <div className="mt-4 rounded-2xl border border-brand/30 bg-brand/[0.06] p-4">
          <div className="flex items-baseline justify-between">
            <span className="text-[16px] font-extrabold tracking-wide text-ink">
              {plan.name}
            </span>
            <span className="text-[18px] font-bold text-ink">
              {plan.priceLabel}
              <span className="ml-1 text-[11px] font-normal text-ink-faint">
                {plan.priceSub}
              </span>
            </span>
          </div>

          <ul className="mt-3 space-y-1.5 border-t border-line-soft pt-3">
            {plan.features.map((f) => (
              <li
                key={f}
                className="flex items-start gap-1.5 text-[12px] text-ink-soft"
              >
                <Check className="mt-0.5 h-3.5 w-3.5 flex-none text-brand" />
                {f}
              </li>
            ))}
          </ul>
        </div>

        {/* 자동 갱신 안내 */}
        <div className="mt-3 flex items-start gap-2 rounded-xl bg-base-850 px-3 py-2.5 text-[11px] leading-relaxed text-ink-faint">
          <Info className="mt-px h-3.5 w-3.5 flex-none" />
          <span>
            구독은 매월 자동 갱신되며 언제든 해지할 수 있어요. 해지 전까지 월{" "}
            {plan.priceLabel}이 청구되는 조건입니다(데모 안내).
          </span>
        </div>

        {/* 결제 버튼 — 미연동 명시 */}
        <button
          type="button"
          disabled
          aria-disabled="true"
          className="mt-4 flex w-full cursor-not-allowed items-center justify-center gap-2 rounded-xl bg-surface py-3 text-[14px] font-bold text-ink-faint"
        >
          <Lock className="h-4 w-4" />
          결제 연동 준비 중
        </button>
        <p className="mt-2 text-center text-[10px] text-ink-faint">
          실제 결제 수단 연동은 준비 중입니다. 카드 정보를 입력받거나 결제를
          완료 처리하지 않습니다.
        </p>

        <button
          type="button"
          onClick={() => goTo("pricing")}
          className="mt-3 w-full rounded-xl py-2.5 text-[13px] font-semibold text-ink-soft transition hover:text-ink"
        >
          플랜 다시 선택
        </button>
      </div>
    </AppWindow>
  );
}
