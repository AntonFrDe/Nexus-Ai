"use client";

import { useCallback, useSyncExternalStore } from "react";

import { useStudio } from "@/components/shell/providers";
import type { PanelDefinition } from "@/core/panels/registry";

const NONE = "";

/** Sorted ids of the panels currently in the dock, kept live through Dockview events. */
export function useOpenPanels(): Set<string> {
  const { dock } = useStudio();
  const subscribe = useCallback(
    (listener: () => void) => {
      if (!dock) return () => undefined;
      const added = dock.onDidAddPanel(listener);
      const removed = dock.onDidRemovePanel(listener);
      return () => {
        added.dispose();
        removed.dispose();
      };
    },
    [dock],
  );
  const snapshot = useSyncExternalStore(
    subscribe,
    () => (dock ? dock.panels.map((panel) => panel.id).sort().join("\n") : NONE),
    () => NONE,
  );
  return new Set(snapshot ? snapshot.split("\n") : []);
}

export function useRevealPanel() {
  const { dock } = useStudio();
  return useCallback(
    (definition: PanelDefinition, options?: { besidePanel?: string }) => {
      if (!dock) return;
      const existing = dock.getPanel(definition.id);
      if (existing) {
        existing.api.setActive();
        return;
      }
      const beside = options?.besidePanel ? dock.getPanel(options.besidePanel) : undefined;
      const otherGroup = dock.groups.find(
        (group) => group !== beside?.group && group.api.location.type === "grid",
      );
      dock.addPanel({
        id: definition.id,
        component: definition.id,
        title: definition.title,
        // Never cover the panel that requested this one.
        position:
          beside &&
          (otherGroup
            ? { referenceGroup: otherGroup }
            : { referencePanel: beside, direction: "left" }),
      });
    },
    [dock],
  );
}
