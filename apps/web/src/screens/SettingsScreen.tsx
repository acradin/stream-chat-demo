import { ArrowLeft } from "lucide-react";
import { useUiStore } from "@/store/uiStore";
import { AppWindow } from "@/components/window/AppWindow";
import { WindowControls } from "@/components/window/WindowControls";
import { Logo } from "@/components/shared/Logo";
import { SettingsSection } from "@/components/settings/SettingsSection";
import { ShortcutEditor } from "@/components/settings/ShortcutEditor";
import { BroadcastDescription } from "@/components/settings/BroadcastDescription";
import { PersonaSummary } from "@/components/settings/PersonaSummary";
import { UsageProgress } from "@/components/settings/UsageProgress";

export function SettingsScreen() {
  const goTo = useUiStore((s) => s.goTo);

  return (
    <AppWindow width={480}>
      {/* 헤더 */}
      <header className="flex items-center justify-between px-6 pt-6">
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

      {/* 본문 */}
      <div className="space-y-6 px-6 py-6">
        <SettingsSection title="단축키 설정">
          <ShortcutEditor />
        </SettingsSection>

        <SettingsSection title="방송 설명">
          <BroadcastDescription />
        </SettingsSection>

        <SettingsSection title="페르소나">
          <PersonaSummary />
        </SettingsSection>

        <SettingsSection title="사용량">
          <UsageProgress />
        </SettingsSection>
      </div>
    </AppWindow>
  );
}
