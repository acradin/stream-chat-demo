import { ArrowLeft, Check, Crown } from "lucide-react";
import { useUiStore } from "@/store/uiStore";
import { PLANS, PLAN_ORDER, type Plan } from "@/lib/plans";
import { AppWindow } from "@/components/window/AppWindow";
import { WindowControls } from "@/components/window/WindowControls";
import { Logo } from "@/components/shared/Logo";
import { cn } from "@/components/ui/cn";

/**
 * 요금제 선택 화면. FREE / PRO / MEGA.
 * FREE 선택 → 결제 없이 메인 복귀. PRO/MEGA → CheckoutPage.
 */
export function PricingPage() {
  const goTo = useUiStore((s) => s.goTo);
  const openCheckout = useUiStore((s) => s.openCheckout);
  const setPlan = useUiStore((s) => s.setPlan);
  const currentPlan = useUiStore((s) => s.plan);

  function choose(plan: Plan) {
    if (!plan.paid) {
      // FREE: 결제 없이 적용 후 메인 복귀
      setPlan(plan.id);
      goTo("main");
      return;
    }
    openCheckout(plan.id);
  }

  return (
    <AppWindow width={720}>
      <header className="flex items-center justify-between px-7 pt-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => goTo("main")}
            title="메인으로"
            className="grid h-7 w-7 place-items-center rounded-md text-ink-soft transition hover:text-white"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <Logo />
        </div>
        <WindowControls />
      </header>

      <div className="px-7 py-6">
        <div className="mb-5 text-center">
          <h2 className="text-[20px] font-bold text-ink">플랜을 선택하세요</h2>
          <p className="mt-1 text-[12px] text-ink-faint">
            더 많은 AI 채팅 멤버와 기능을 사용할 수 있어요.
          </p>
        </div>

        <div className="grid grid-cols-3 gap-3">
          {PLAN_ORDER.map((id) => {
            const plan = PLANS[id];
            const isCurrent = currentPlan === id;
            return (
              <div
                key={id}
                className={cn(
                  "relative flex flex-col rounded-2xl border p-4",
                  plan.recommended
                    ? "border-brand/60 bg-brand/[0.06]"
                    : "border-line-soft bg-base-850",
                )}
                style={
                  plan.recommended
                    ? { boxShadow: "0 0 0 1px rgba(3,255,213,0.25)" }
                    : undefined
                }
              >
                {plan.recommended && (
                  <span className="absolute -top-2.5 left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-full bg-brand px-2.5 py-0.5 text-[10px] font-bold text-base-950">
                    <Crown className="h-3 w-3" />
                    추천
                  </span>
                )}

                <div className="mb-3">
                  <div className="text-[15px] font-extrabold tracking-wide text-ink">
                    {plan.name}
                  </div>
                  <div className="mt-1 flex items-baseline gap-1">
                    <span className="text-[22px] font-bold text-ink">
                      {plan.priceLabel}
                    </span>
                    <span className="text-[11px] text-ink-faint">
                      {plan.priceSub}
                    </span>
                  </div>
                </div>

                <ul className="mb-4 flex-1 space-y-1.5">
                  {plan.features.map((f) => (
                    <li
                      key={f}
                      className="flex items-start gap-1.5 text-[11px] leading-snug text-ink-soft"
                    >
                      <Check className="mt-0.5 h-3 w-3 flex-none text-brand" />
                      {f}
                    </li>
                  ))}
                </ul>

                <button
                  type="button"
                  onClick={() => choose(plan)}
                  disabled={isCurrent}
                  className={cn(
                    "rounded-xl py-2.5 text-[13px] font-bold transition disabled:cursor-not-allowed disabled:opacity-60",
                    plan.recommended
                      ? "text-base-950 hover:brightness-105"
                      : "text-ink hover:brightness-110",
                  )}
                  style={{
                    background: plan.recommended
                      ? "linear-gradient(135deg,#03FFD5,#2DFF8F)"
                      : "#484848",
                  }}
                >
                  {isCurrent
                    ? "현재 플랜"
                    : plan.paid
                      ? `${plan.name} 선택`
                      : "FREE 사용"}
                </button>
              </div>
            );
          })}
        </div>

        <p className="mt-5 text-center text-[10px] text-ink-faint">
          결제는 데모 단계로, 실제 과금은 발생하지 않습니다. 플랜 값은 로컬에만
          저장되며 유료 인증이 아닙니다.
        </p>
      </div>
    </AppWindow>
  );
}
