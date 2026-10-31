import { useSessionStore } from "@/store/sessionStore";
import { useUiStore } from "@/store/uiStore";
import { TRAITS, traitById } from "@/lib/traits";

/**
 * 현재 선택된 페르소나 요약(아이콘 + 이름 + 2줄 설명 + 수정).
 * 수정 → 온보딩의 페르소나 선택 화면으로 이동.
 * 설정 화면에서 6개 카드를 펼치지 않는다.
 */
export function PersonaSummary() {
  const selected = useSessionStore((s) => s.selectedPersona);
  const traitIds = useUiStore((s) => s.traitIds);
  const goTo = useUiStore((s) => s.goTo);

  const chosenTraits = traitIds.map(traitById).filter((trait) => trait != null);
  const fallback = TRAITS.find((trait) => trait.mapsTo === selected) ?? TRAITS[0];
  const presentations = chosenTraits.length ? chosenTraits : [fallback];

  return (
    <div className="flex items-start gap-4">
      <div className="min-w-0 flex-1 space-y-4">
        {presentations.map((trait) => (
          <div key={trait.id} className="flex items-start gap-3">
            <img src={trait.image} alt="" aria-hidden="true" width={51} height={48}
              className="h-12 w-12 flex-none select-none object-contain" draggable={false} />
            <div className="min-w-0 flex-1">
              <p className="text-[15px] font-bold text-ink">{trait.label}</p>
              <p className="mt-0.5 break-keep text-[12px] leading-snug text-ink-faint">{trait.description}</p>
            </div>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={() => goTo("onboarding")}
        className="h-10 flex-none rounded-xl px-5 text-[14px] font-semibold text-ink transition hover:brightness-110"
        style={{ background: "#484848" }}
      >
        수정
      </button>
    </div>
  );
}
