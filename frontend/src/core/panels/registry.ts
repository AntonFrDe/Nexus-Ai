import type { LucideIcon } from "lucide-react";
import type { ComponentType } from "react";
import type { IDockviewPanelProps } from "dockview-react";

export type PanelProps = IDockviewPanelProps;

export interface PanelDefinition {
  id: string;
  title: string;
  description: string;
  category: string;
  icon: LucideIcon;
  component: ComponentType<PanelProps>;
}

/** The workspace engine knows panels only through this registry; plugins will extend it. */
export class PanelRegistry {
  private readonly panels = new Map<string, PanelDefinition>();

  register(definition: PanelDefinition): void {
    if (this.panels.has(definition.id)) {
      throw new Error(`Panel already registered: ${definition.id}`);
    }
    this.panels.set(definition.id, definition);
  }

  get(id: string): PanelDefinition | undefined {
    return this.panels.get(id);
  }

  has(id: string): boolean {
    return this.panels.has(id);
  }

  list(): PanelDefinition[] {
    return [...this.panels.values()];
  }
}
