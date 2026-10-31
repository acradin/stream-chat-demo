import type { ReactNode } from "react";
import { cn } from "../ui/cn";

interface AppWindowProps {
  width?: number;
  children: ReactNode;
  className?: string;
}

/**
 * 데스크톱 유틸리티 앱 '창'. 브라우저 배경(backdrop) 위 중앙에 떠 있는 작은 창.
 * 차콜 배경 + 큰 라운드 + 소프트 섀도. 데스크톱 앱 확장 시 그대로 재사용.
 */
export function AppWindow({ width = 420, children, className }: AppWindowProps) {
  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-canvas p-4">
      <div
        className={cn(
          "flex w-full flex-col overflow-hidden rounded-window bg-window shadow-window",
          className,
        )}
        style={{ maxWidth: width }}
      >
        {children}
      </div>
    </div>
  );
}
