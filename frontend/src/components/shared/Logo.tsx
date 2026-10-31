import { useSessionStore } from "@/store/sessionStore";

/** tiki 공식 로고(에셋) + Online/Offline 상태 배지. */
export function Logo({ showStatus = true }: { showStatus?: boolean }) {
  const connection = useSessionStore((s) => s.connection);
  const isMock = useSessionStore((s) => s.config?.is_mock ?? false);
  const online = connection === "ready";

  return (
    <div className="flex items-center gap-2.5">
      <img
        src="/brand/app-header.svg"
        alt="tiki"
        width={70}
        height={21}
        className="h-[26px] w-auto select-none object-contain"
        draggable={false}
      />
      {showStatus && (
        <span
          className="inline-flex items-center justify-center gap-2 rounded-full px-2.5 py-1 text-[11px] font-semibold leading-none text-white"
          style={{ background: online ? "#EF454F" : "#5a5a5a" }}
          title={isMock ? "MOCK 연결" : online ? "연결됨" : "연결 필요"}
        >
          <span className="h-2 w-2 shrink-0 rounded-full bg-white" />
          <span className="leading-none">
            {online ? (isMock ? "Online · MOCK" : "Online") : "Offline"}
          </span>
        </span>
      )}
    </div>
  );
}
