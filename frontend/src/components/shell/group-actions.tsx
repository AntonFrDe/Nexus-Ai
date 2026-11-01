"use client";

import type { IDockviewHeaderActionsProps } from "dockview-react";
import { AppWindow, Maximize2, Minimize2, PanelTop, PictureInPicture2 } from "lucide-react";
import { useEffect, useState, type ComponentType } from "react";

function Action({
  label,
  icon: Icon,
  onClick,
}: {
  label: string;
  icon: ComponentType<{ className?: string }>;
  onClick(): void;
}) {
  return (
    <button type="button" className="icon-button" title={label} aria-label={label} onClick={onClick}>
      <Icon className="size-3.5" />
    </button>
  );
}

export function GroupActions({ api, containerApi, group }: IDockviewHeaderActionsProps) {
  const [, rerender] = useState(0);
  const [location, setLocation] = useState(api.location.type);

  useEffect(() => {
    const locationChange = api.onDidLocationChange((event) => setLocation(event.location.type));
    const layoutChange = containerApi.onDidMaximizedGroupChange(() => rerender((n) => n + 1));
    return () => {
      locationChange.dispose();
      layoutChange.dispose();
    };
  }, [api, containerApi]);

  if (location !== "grid") {
    return (
      <div className="group-actions">
        <Action
          label="Dock back into the layout"
          icon={PanelTop}
          onClick={() => api.moveTo({ position: "right" })}
        />
      </div>
    );
  }

  const maximized = api.isMaximized();
  return (
    <div className="group-actions">
      {!maximized && (
        <>
          <Action
            label="Float group"
            icon={PictureInPicture2}
            onClick={() => containerApi.addFloatingGroup(group)}
          />
          <Action
            label="Open group in a new window"
            icon={AppWindow}
            onClick={() => void containerApi.addPopoutGroup(group)}
          />
        </>
      )}
      <Action
        label={maximized ? "Restore group" : "Maximize group"}
        icon={maximized ? Minimize2 : Maximize2}
        onClick={() => (maximized ? api.exitMaximized() : api.maximize())}
      />
    </div>
  );
}
