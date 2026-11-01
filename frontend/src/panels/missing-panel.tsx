import type { IDockviewPanelProps } from "dockview-react";

export function MissingPanel({ params }: IDockviewPanelProps<{ missingComponent?: string }>) {
  return (
    <div className="panel planned">
      <p className="panel-heading">Panel unavailable</p>
      <p className="muted">
        This layout references <code>{params.missingComponent ?? "an unknown panel"}</code>, which
        is not registered. Close this tab or reset the layout.
      </p>
    </div>
  );
}
