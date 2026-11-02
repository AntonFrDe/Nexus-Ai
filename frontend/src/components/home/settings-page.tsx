"use client";

import { useEffect, useState } from "react";

import { AppHeader } from "@/components/home/app-header";
import { StudioProvider, useStudio, useWorkspace } from "@/components/shell/providers";
import { createPanelRegistry } from "@/panels";
import { AgentsPanel } from "@/panels/agents-panel";
import { AppearancePanel } from "@/panels/appearance-panel";
import { ModelRegistryPanel } from "@/panels/model-registry-panel";

function SettingsBody() {
  const { store, models, agents } = useStudio();
  const appearance = useWorkspace((state) => state.appearance);
  const setAppearance = useWorkspace((state) => state.setAppearance);

  useEffect(() => {
    void store.getState().init();
    void models.getState().load();
    void agents.getState().load();
  }, [store, models, agents]);

  useEffect(() => {
    document.documentElement.dataset.accent = appearance.accent;
    document.documentElement.dataset.density = appearance.density;
  }, [appearance]);

  return (
    <main className="settings">
      <h1>Réglages</h1>
      <section aria-label="Modèles">
        <h2>Modèles</h2>
        <p className="muted">Ajoute Ollama pour des modèles gratuits sur ta machine, ou une clé API.</p>
        <div className="settings-frame">
          <ModelRegistryPanel />
        </div>
      </section>
      <section aria-label="Agents">
        <h2>Agents</h2>
        <div className="settings-frame">
          <AgentsPanel />
        </div>
      </section>
      <section aria-label="Apparence">
        <h2>Apparence</h2>
        <AppearancePanel />
        <label className="row">
          <input
            type="checkbox"
            checked={appearance.experimental}
            onChange={(event) =>
              void setAppearance({ ...appearance, experimental: event.target.checked })
            }
          />
          Afficher les fonctions expérimentales (plugins, runtimes cloud, Langfuse)
        </label>
      </section>
    </main>
  );
}

export function SettingsPage() {
  const [registry] = useState(createPanelRegistry);
  return (
    <div className="app-page">
      <AppHeader />
      <StudioProvider registry={registry}>
        <SettingsBody />
      </StudioProvider>
    </div>
  );
}
