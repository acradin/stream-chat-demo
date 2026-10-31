import type { ReactNode } from "react";

interface SettingsSectionProps {
  title: string;
  children: ReactNode;
}

export function SettingsSection({ title, children }: SettingsSectionProps) {
  return (
    <section>
      <h3 className="mb-2.5 text-[15px] font-bold text-ink">{title}</h3>
      {children}
    </section>
  );
}
