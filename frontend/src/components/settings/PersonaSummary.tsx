import { useSessionStore } from "@/store/sessionStore";
import { useUiStore } from "@/store/uiStore";
import { traitById } from "@/lib/traits";

/**
 * 현재 선택된 페르소나 요약(아이콘 + 이름 + 2줄 설명 + 수정).
 * 수정 → 온보딩의 페르소나 선택 화면으로 이동.
 * 설정 화면에서 6개 카드를 펼치지 않는다.
 */
export function PersonaSummary() {
  const config = useSessionStore((s) => s.config);
  const selected = useSessionStore((s) => s.selectedPersona);
  const traitIds = useUiStore((s) => s.traitIds);
  const goTo = useUiStore((s) => s.goTo);

  const persona = config?.personas.find((p) => p.id === selected);
  // 성향을 골랐으면 그 라벨 조합을 이름으로, 아니면 백엔드 페르소나 이름.
  const traitLabels = traitIds
    .map((id) => traitById(id)?.label)
    .filter(Boolean);
  const name = persona?.name ?? "페르소나";
  const description =
    persona?.description ??
    "재치있는 드립과 적절한 놀림으로 방송을 활발하게 만들어주는 스타일";

  return (
    <div className="flex items-center gap-4">
      {/* 프로필 아이콘 (시안: 둥근 흰 사각형) */}
      <div className="h-16 w-16 flex-none rounded-2xl bg-white" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-[15px] font-bold text-ink">
          {traitLabels.length ? traitLabels.join(" · ") : name}
        </p>
        <p className="mt-0.5 text-[12px] leading-snug text-ink-faint">
          {description}
        </p>
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
