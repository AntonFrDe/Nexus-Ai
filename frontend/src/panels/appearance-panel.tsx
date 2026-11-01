"use client";

import { useWorkspace } from "@/components/shell/providers";
import type { Density } from "@/core/workspace/store";

export const ACCENTS = ["amber", "teal", "rose", "slate"];
const DENSITIES: Density[] = ["compact", "comfortable"];

export function AppearancePanel() {
  const appearance = useWorkspace((state) => state.appearance);
  const setAppearance = useWorkspace((state) => state.setAppearance);

  return (
    <div className="panel">
      <fieldset className="choice">
        <legend className="section-label">Accent</legend>
        {ACCENTS.map((accent) => (
          <label key={accent} className="row">
            <input
              type="radio"
              name="accent"
              checked={appearance.accent === accent}
              onChange={() => void setAppearance({ ...appearance, accent })}
            />
            <span className="swatch" data-swatch={accent} />
            <span className="capitalize">{accent}</span>
          </label>
        ))}
      </fieldset>
      <fieldset className="choice">
        <legend className="section-label">Density</legend>
        {DENSITIES.map((density) => (
          <label key={density} className="row">
            <input
              type="radio"
              name="density"
              checked={appearance.density === density}
              onChange={() => void setAppearance({ ...appearance, density })}
            />
            <span className="capitalize">{density}</span>
          </label>
        ))}
      </fieldset>
    </div>
  );
}
