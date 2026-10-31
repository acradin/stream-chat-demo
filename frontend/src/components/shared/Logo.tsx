import { useSessionStore } from "@/store/sessionStore";

/** tiki 공식 로고(에셋) + Online/Offline 상태 배지. */
export function Logo({ showStatus = true }: { showStatus?: boolean }) {
  const connection = useSessionStore((s) => s.connection);
  const isMock = useSessionStore((s) => s.config?.is_mock ?? false);
  const online = connection === "ready";

  return (
    <div className="flex items-center gap-2.5">
      <img
        src="/tiki-logo.svg"
        alt="tiki"
        className="h-[26px] w-auto select-none"
        draggable={false}
      />
      {showStatus && (
        <span
          className="flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold text-white"
          style={{ background: online ? "#EF454F" : "#5a5a5a" }}
          title={isMock ? "MOCK 연결" : online ? "연결됨" : "연결 필요"}
        >
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-white" />
          {online ? (isMock ? "Online · MOCK" : "Online") : "Offline"}
        </span>
      )}
    </div>
  );
}
