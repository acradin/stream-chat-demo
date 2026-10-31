import { Check } from "lucide-react";
import { TRAITS } from "@/lib/traits";
import { useUiStore } from "@/store/uiStore";
import { cn } from "../ui/cn";

/**
 * 페르소나 성향 복수 선택 카드. 온보딩 Step 1 과 설정에서 공용.
 * 선택은 uiStore.traitIds 에 저장되며, 생성 시 대표 백엔드 persona 로 매핑된다.
 */
export function TraitSelect() {
  const traitIds = useUiStore((s) => s.traitIds);
  const toggleTrait = useUiStore((s) => s.toggleTrait);

  return (
    <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
      {TRAITS.map((t) => {
        const active = traitIds.includes(t.id);
        return (
          <button
            key={t.id}
            type="button"
            aria-pressed={active}
            onClick={() => toggleTrait(t.id)}
            className={cn(
              "relative flex items-start gap-2.5 rounded-xl border p-3 text-left transition",
              active
                ? "border-transparent"
                : "border-line-soft bg-base-850 hover:border-line-strong",
            )}
            style={
              active
                ? {
                    background: `${t.accent}14`,
                    boxShadow: `inset 0 0 0 1.5px ${t.accent}`,
                  }
                : undefined
            }
          >
            <img
              src={t.image}
              alt=""
              aria-hidden="true"
              width={51}
              height={48}
              className="h-10 w-10 flex-none select-none object-contain"
              draggable={false}
            />
            <span className="min-w-0 flex-1 pr-1">
              <span className="block text-[13px] font-semibold text-ink">{t.label}</span>
              <span className="mt-1 block break-keep text-[10px] leading-snug text-ink-faint">
                {t.description}
              </span>
            </span>
            {active && (
              <span
                className="absolute right-2 top-2 grid h-4 w-4 place-items-center rounded-full"
                style={{ background: t.accent }}
              >
                <Check className="h-2.5 w-2.5 text-base-950" strokeWidth={3} />
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
