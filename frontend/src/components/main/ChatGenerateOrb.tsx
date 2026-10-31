import { motion } from "framer-motion";
import { Loader2 } from "lucide-react";
import { useSessionStore } from "@/store/sessionStore";
import { useUiStore } from "@/store/uiStore";
import { useCooldownTick } from "@/hooks/useCooldownTick";
import { formatHotkey } from "@/lib/format";

interface ChatGenerateOrbProps {
  onGenerate: () => void;
}

/**
 * 메인의 핵심: 큰 민트/그린 원형 생성 버튼.
 * 흰 말풍선 캐릭터 + 단축키 + "채팅을 생성하세요!".
 * 클릭/단축키로 기존 수동 생성(sessionStore.generate) 실행. 로딩 중 중복 방지.
 */
export function ChatGenerateOrb({ onGenerate }: ChatGenerateOrbProps) {
  const config = useSessionStore((s) => s.config);
  const inFlight = useSessionStore((s) => s.inFlight);
  const hotkey = useUiStore((s) => s.hotkey);
  const remaining = useCooldownTick();

  const cooling = remaining > 0;
  const disabled = !config || inFlight || cooling;

  // 저장값(단일 소스)을 공용 포매터로 표시. 하드코딩 매핑 제거.
  const hotkeyLabel = formatHotkey(hotkey);

  return (
    <motion.button
      type="button"
      onClick={onGenerate}
      disabled={disabled}
      whileHover={disabled ? undefined : { scale: 1.02 }}
      whileTap={disabled ? undefined : { scale: 0.96 }}
      transition={{ type: "spring", stiffness: 400, damping: 26 }}
      aria-label="AI 채팅 생성"
      className="group relative grid aspect-square w-[62%] place-items-center rounded-full outline-none disabled:cursor-not-allowed"
      style={{
        background: disabled
          ? "radial-gradient(circle at 50% 32%, #4a4a4a, #3a3a3a 70%)"
          : "transparent",
        boxShadow: disabled
          ? "inset 0 0 0 1px rgba(255,255,255,0.08)"
          : "0 0 32px -4px rgba(3,255,213,0.18)",
      }}
    >
      {!disabled && (
        <span aria-hidden="true" className="pointer-events-none absolute inset-0">
          <img src="/brand/orb-base.png" alt="" className="absolute inset-0 h-full w-full opacity-[0.72]" draggable={false} />
          <img src="/brand/orb-glow.png" alt="" className="absolute inset-[10%] h-[80%] w-[80%] opacity-[0.72]" draggable={false} />
        </span>
      )}
      {/* 호버 글로우 */}
      {!disabled && (
        <span className="pointer-events-none absolute inset-0 rounded-full opacity-0 transition-opacity duration-200 group-hover:opacity-100"
          style={{ boxShadow: "0 0 70px 2px rgba(45,255,143,0.5)" }}
        />
      )}

      <span className="relative flex w-full flex-col items-center gap-2 text-center">
        {inFlight ? (
          <Loader2 className="h-[46px] w-[46px] animate-spin text-white" />
        ) : (
          <img
            src="/brand/generate-face.svg"
            alt=""
            aria-hidden="true"
            className="h-auto w-[43%] object-contain"
            draggable={false}
          />
        )}
        <span className="mt-1 flex items-center gap-1.5 text-[19px] font-bold leading-none text-white">
          <span className="text-[15px]">⇧</span>
          {inFlight ? "생성 중…" : cooling ? `${(remaining / 1000).toFixed(1)}초` : hotkeyLabel}
        </span>
        <span className="text-[12px] font-medium text-white/85">
          채팅을 생성하세요!
        </span>
      </span>
    </motion.button>
  );
}
