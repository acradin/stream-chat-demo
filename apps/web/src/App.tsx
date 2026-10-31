import { useEffect } from "react";
import { useSessionStore } from "./store/sessionStore";
import { useUiStore } from "./store/uiStore";
import { MainScreen } from "./screens/MainScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { OnboardingScreen } from "./screens/OnboardingScreen";

export default function App() {
  const loadConfig = useSessionStore((s) => s.loadConfig);
  const screen = useUiStore((s) => s.screen);

  useEffect(() => {
    void loadConfig();
  }, [loadConfig]);

  // 탭 전환 시 컨텍스트 무효화 (표시 직전 폐기 판정에 사용).
  useEffect(() => {
    const onVis = () => {
      if (document.hidden) useSessionStore.getState().bumpContextVersion();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  if (screen === "onboarding") return <OnboardingScreen />;
  if (screen === "settings") return <SettingsScreen />;
  return <MainScreen />;
}
