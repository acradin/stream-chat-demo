/**
 * 창 제어 원형 버튼(close/minimize) — 시안의 coral/yellow 점.
 * 웹 데모에서는 실제 OS 창 제어가 아니므로 동작하는 척하지 않는다.
 * (클릭 시 안내만, title 로 명시)
 */
export function WindowControls() {
  const note = "웹 데모에서는 창 제어가 동작하지 않아요 (데스크톱 앱 전용)";
  return (
    <div className="flex items-center gap-2" aria-hidden="true">
      <span
        title={note}
        className="h-3.5 w-3.5 rounded-full"
        style={{ background: "#EF454F" }}
      />
      <span
        title={note}
        className="h-3.5 w-3.5 rounded-full"
        style={{ background: "#F5C04E" }}
      />
    </div>
  );
}
