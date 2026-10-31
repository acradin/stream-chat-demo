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

      {/* 연결 오류만 간결히 표기 (정상/대기 시엔 숨김) */}
      {connection === "error" && (
        <p className="px-6 text-center text-[12px] text-status-error">
          {feedback.message}
        </p>
      )}

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
