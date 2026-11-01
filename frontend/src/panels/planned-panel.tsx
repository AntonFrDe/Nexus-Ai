import type { LucideIcon } from "lucide-react";

import type { PanelDefinition } from "@/core/panels/registry";

interface PlannedPanel {
  id: string;
  title: string;
  icon: LucideIcon;
  category: string;
  milestone: number;
  description: string;
}

/** A reserved slot for a later milestone: it states what is coming and does nothing else. */
export function plannedPanel(planned: PlannedPanel): PanelDefinition {
  const { milestone, ...definition } = planned;
  return {
    ...definition,
    component: function Planned() {
      return (
        <div className="panel planned">
          <p className="panel-heading">{planned.title}</p>
          <p className="muted">{planned.description}</p>
          <p className="tag">Not implemented yet · Milestone {milestone}</p>
        </div>
      );
    },
  };
}
