import { useEffect } from "react";
import { useUiStore } from "@/store/uiStore";

// 설정된 단축키(브라우저 범위)로 생성을 트리거한다.
// 입력창/버튼 등에 포커스가 있으면 가로채지 않는다.
// OS 전역 단축키가 아니라 이 창 내 단축키다.

function matches(e: KeyboardEvent, hotkey: string): boolean {
  const parts = hotkey.split(" + ");
  const key = parts[parts.length - 1];
  const needCtrl = parts.includes("Ctrl");
  const needAlt = parts.includes("Alt");
  const needShift = parts.includes("Shift");
  const needMeta = parts.includes("Meta");

  if (e.ctrlKey !== needCtrl) return false;
  if (e.altKey !== needAlt) return false;
  if (e.shiftKey !== needShift) return false;
  if (e.metaKey !== needMeta) return false;

  // 표시되는 단축키와 실제 키 코드를 일치시킨다.
  if (key === "Space") return e.code === "Space";
  if (key === "Caps Lock") return e.code === "CapsLock";
  const codeLabel = e.code.replace(/^Key/, "").replace(/^Digit/, "");
  return e.code === key || codeLabel === key;
}

export function useSpaceHotkey(onTrigger: () => void): void {
  const hotkey = useUiStore((s) => s.hotkey);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.repeat) return;
      if (!matches(event, hotkey)) return;
      const target = event.target;
      if (
        target instanceof Element &&
        (target.closest(
          'input,textarea,select,video,button,a,[contenteditable="true"],[data-hotkey-capture]',
        ) ||
          (target as HTMLElement).isContentEditable)
      ) {
        return;
      }
      event.preventDefault();
      onTrigger();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onTrigger, hotkey]);
}
