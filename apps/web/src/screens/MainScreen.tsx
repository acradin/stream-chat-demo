import { useCallback } from "react";
import { Settings } from "lucide-react";
import { useSessionStore } from "@/store/sessionStore";
import { useUiStore } from "@/store/uiStore";
import { useSpaceHotkey } from "@/hooks/useSpaceHotkey";
import { AppWindow } from "@/components/window/AppWindow";
import { WindowControls } from "@/components/window/WindowControls";
import { Logo } from "@/components/shared/Logo";
import { ChatGenerateOrb } from "@/components/main/ChatGenerateOrb";
import { MemberSlider } from "@/components/main/MemberSlider";
import { UpgradeCta } from "@/components/main/UpgradeCta";

export function MainScreen() {
  const generate = useSessionStore((s) => s.generate);
  const feedback = useSessionStore((s) => s.feedback);
  const connection = useSessionStore((s) => s.connection);
  const config = useSessionStore((s) => s.config);
  const messages = useSessionStore((s) => s.messages);
  const goTo = useUiStore((s) => s.goTo);

  const handleGenerate = useCallback(() => {
    const s = useSessionStore.getState();
    if (!s.canGenerate()) return;
    void generate({
      clickedAt: performance.now(),
      videoSessionId: null,
      clickedVideoS: null,
      contextVersion: s.contextVersion,
      readVideoTime: () => null,
    });
  }, [generate]);

  useSpaceHotkey(handleGenerate);

  return (
    <AppWindow width={420}>
      {/* 헤더 */}
      <header className="flex items-center justify-between px-6 pt-6">
        <Logo />
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => goTo("settings")}
            title="설정"
            className="grid h-7 w-7 place-items-center rounded-md text-ink-soft transition hover:text-white"
          >
            <Settings className="h-5 w-5" />
          </button>
          <WindowControls />
        </div>
      </header>

      {/* 중앙 오브 */}
      <div className="flex flex-col items-center px-6 pb-2 pt-7">
        <ChatGenerateOrb onGenerate={handleGenerate} />
      </div>

      <p role="status" className={`px-6 text-center text-[12px] ${connection === "error" || feedback.kind === "error" ? "text-status-error" : "text-ink-faint"}`}>
        {feedback.message}
      </p>
      {config?.is_mock && (
        <p className="mt-2 px-6 text-center text-[11px] text-status-warn">
          Mock 데모 · 예시 채팅이며 방송으로 전송되지 않습니다.
        </p>
      )}
      <div role="log" aria-label="생성된 채팅" aria-live="polite" className="mt-4 max-h-40 space-y-2 overflow-y-auto px-6">
        {messages.slice(-5).map((message) => (
          <p key={message.requestId} className="rounded-xl bg-surface px-3 py-2 text-[13px] text-ink">
            {message.comment}
          </p>
        ))}
      </div>

      {/* 멤버 슬라이더 */}
      <div className="px-6 pt-4">
        <MemberSlider />
      </div>

      {/* 업그레이드 CTA */}
      <div className="px-6 pb-7 pt-4">
        <UpgradeCta />
      </div>
    </AppWindow>
  );
}
