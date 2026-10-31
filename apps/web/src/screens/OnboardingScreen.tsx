import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowLeft, ArrowRight, Check, Sparkles } from "lucide-react";
import { useUiStore } from "@/store/uiStore";
import { useSessionStore } from "@/store/sessionStore";
import { primaryPersonaFromTraits, traitById } from "@/lib/traits";
import { AppWindow } from "@/components/window/AppWindow";
import { WindowControls } from "@/components/window/WindowControls";
import { Logo } from "@/components/shared/Logo";
import { TraitSelect } from "@/components/shared/TraitSelect";
import { ContextInput } from "@/components/controls/ContextInput";
import { cn } from "@/components/ui/cn";

const STEPS = ["AI 페르소나", "방송 설명", "확인"];

export function OnboardingScreen() {
  const [step, setStep] = useState(0);
  const traitIds = useUiStore((s) => s.traitIds);
  const completeOnboarding = useUiStore((s) => s.completeOnboarding);
  const onboarded = useUiStore((s) => s.onboarded);
  const goTo = useUiStore((s) => s.goTo);

  const config = useSessionStore((s) => s.config);
  const channelContext = useSessionStore((s) => s.channelContext);
  const setPersona = useSessionStore((s) => s.setPersona);

  const canNext = step === 0 ? traitIds.length > 0 : true;

  function finish() {
    if (config) {
      const primary = primaryPersonaFromTraits(
        traitIds,
        config.personas.map((p) => p.id),
      );
      if (primary) setPersona(primary);
    }
    completeOnboarding();
  }

  return (
    <AppWindow width={460}>
      <header className="flex items-center justify-between px-6 pt-6">
        <div className="flex items-center gap-3">
          {/* 이미 온보딩을 마친 사용자가 '수정'으로 들어온 경우 뒤로가기 제공 */}
          {onboarded && (
            <button
              type="button"
              onClick={() => goTo("settings")}
              title="설정으로"
              className="grid h-7 w-7 place-items-center rounded-md text-ink-soft transition hover:text-white"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
          )}
          <Logo />
        </div>
        <WindowControls />
      </header>

      <div className="px-6 py-6">
        {/* 스텝 인디케이터 */}
        <div className="mb-5 flex items-center justify-center gap-2">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <div
                className={cn(
                  "flex items-center gap-1.5 text-[11px] font-medium",
                  i === step
                    ? "text-brand"
                    : i < step
                      ? "text-brand-soft"
                      : "text-ink-faint",
                )}
              >
                <span
                  className={cn(
                    "grid h-4 w-4 place-items-center rounded-full text-[9px] font-bold",
                    i <= step ? "text-base-950" : "bg-surface text-ink-faint",
                  )}
                  style={
                    i <= step
                      ? { background: "linear-gradient(135deg,#03FFD5,#2DFF8F)" }
                      : undefined
                  }
                >
                  {i < step ? <Check className="h-2.5 w-2.5" /> : i + 1}
                </span>
                {s}
              </div>
              {i < STEPS.length - 1 && <span className="text-line-strong">—</span>}
            </div>
          ))}
        </div>

        <motion.div
          key={step}
          initial={{ opacity: 0, x: 10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.18 }}
        >
          {step === 0 && (
            <div>
              <h2 className="text-[17px] font-bold text-ink">
                AI 페르소나를 골라주세요
              </h2>
              <p className="mb-4 mt-1 text-[12px] text-ink-faint">
                원하는 말투와 분위기를 여러 개 선택할 수 있어요.
              </p>
              <TraitSelect />
            </div>
          )}

          {step === 1 && (
            <div>
              <h2 className="text-[17px] font-bold text-ink">
                이번 방송을 설명해 주세요
              </h2>
              <p className="mt-1 text-[12px] text-ink-faint">
                게임·콘텐츠·분위기·닉네임 등을 적어두면 AI가 맥락에 맞게
                반응해요.
              </p>
              <ContextInput />
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 className="text-[17px] font-bold text-ink">
                이대로 시작할까요?
              </h2>
              <p className="mb-4 mt-1 text-[12px] text-ink-faint">
                설정은 저장되며 언제든 바꿀 수 있어요.
              </p>
              <dl
                className="space-y-3 rounded-2xl p-4"
                style={{ background: "#3d3d3d" }}
              >
                <div>
                  <dt className="text-[11px] text-ink-faint">선택한 성향</dt>
                  <dd className="mt-1 text-[14px] text-ink">
                    {traitIds.length
                      ? traitIds.map((id) => traitById(id)?.label).join(" · ")
                      : "선택 없음"}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] text-ink-faint">방송 설명</dt>
                  <dd className="mt-1 whitespace-pre-wrap text-[14px] text-ink">
                    {channelContext.trim() || "입력 없음 (일반 맥락으로 반응)"}
                  </dd>
                </div>
              </dl>
            </div>
          )}
        </motion.div>

        {/* 네비게이션 */}
        <div className="mt-6 flex items-center justify-between">
          <button
            type="button"
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0}
            className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-[13px] text-ink-soft transition hover:text-ink disabled:opacity-40"
          >
            <ArrowLeft className="h-4 w-4" />
            이전
          </button>

          {step < STEPS.length - 1 ? (
            <button
              type="button"
              onClick={() => setStep((s) => s + 1)}
              disabled={!canNext}
              className="flex items-center gap-1.5 rounded-xl px-5 py-2.5 text-[13px] font-bold text-base-950 transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-40"
              style={{ background: "linear-gradient(135deg,#03FFD5,#2DFF8F)" }}
            >
              다음
              <ArrowRight className="h-4 w-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={finish}
              className="flex items-center gap-1.5 rounded-xl px-5 py-2.5 text-[13px] font-bold text-base-950 transition hover:brightness-105"
              style={{ background: "linear-gradient(135deg,#03FFD5,#2DFF8F)" }}
            >
              <Sparkles className="h-4 w-4" />
              시작하기
            </button>
          )}
        </div>
      </div>
    </AppWindow>
  );
}
