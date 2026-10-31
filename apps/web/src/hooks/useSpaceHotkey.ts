import { useEffect, useRef } from "react";
import { useUiStore } from "@/store/uiStore";

// 설정된 단축키(브라우저 범위)로 생성을 트리거한다.
// 입력창/버튼 등에 포커스가 있으면 가로채지 않는다.
// OS 전역 단축키가 아니라 이 창 내 단축키다.

/** 저장된 hotkey 문자열을 수식키/주 키로 분해 */
function parseHotkey(hotkey: string) {
  const parts = hotkey.split(" + ");
  return {
    key: parts[parts.length - 1],
    ctrl: parts.includes("Ctrl"),
    alt: parts.includes("Alt"),
    shift: parts.includes("Shift"),
    meta: parts.includes("Meta"),
  };
}

function matches(e: KeyboardEvent, hotkey: string): boolean {
  const spec = parseHotkey(hotkey);

  // CapsLock 은 토글 키라 수식키 상태를 엄격히 비교하지 않는다.
  // (브라우저가 켜짐/꺼짐 전환 시 keydown 을 보내며, shiftKey 등은 무관)
  const isCapsLock = spec.key === "Caps Lock";
  if (!isCapsLock) {
    if (e.ctrlKey !== spec.ctrl) return false;
    if (e.altKey !== spec.alt) return false;
    if (e.shiftKey !== spec.shift) return false;
    if (e.metaKey !== spec.meta) return false;
  }

  if (spec.key === "Space") return e.code === "Space";
  if (isCapsLock) return e.code === "CapsLock";
  const codeLabel = e.code.replace(/^Key/, "").replace(/^Digit/, "");
  return e.code === spec.key || codeLabel === spec.key;
}

const EDITABLE_SELECTOR =
  'input,textarea,select,video,button,a,[contenteditable="true"],[data-hotkey-capture]';

export function useSpaceHotkey(onTrigger: () => void): void {
  const hotkey = useUiStore((s) => s.hotkey);
  // onTrigger 가 매 렌더 새로 와도 리스너를 재등록하지 않도록 ref 로 고정.
  const triggerRef = useRef(onTrigger);
  triggerRef.current = onTrigger;

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      // 자동 반복(키 누름 유지)로 인한 중복 트리거 방지.
      // CapsLock 은 repeat 이 없지만, 다른 키는 보호 필요.
      if (event.repeat || event.defaultPrevented || event.isComposing) return;
      if (!matches(event, hotkey)) return;

      const target = event.target;
      if (
        target instanceof Element &&
        (target.closest(EDITABLE_SELECTOR) ||
          (target as HTMLElement).isContentEditable)
      ) {
        return;
      }

      event.preventDefault();
      triggerRef.current();
    };

    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [hotkey]);
}
