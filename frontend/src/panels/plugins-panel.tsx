"use client";

import { useState, type FormEvent } from "react";

import { FieldForm } from "@/components/forms/field-form";
import { usePlugins, useStudio } from "@/components/shell/providers";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { Plugin } from "@/core/models/plugin-types";

const PERMISSION_TEXT: Record<string, string> = {
  filesystem: "Keep files in its own private folder",
  network: "Connect to the network, including this machine",
  shell: "Run programs on this computer",
};

const describePermission = (permission: string) =>
  PERMISSION_TEXT[permission] ??
  `Read the environment variable ${permission.replace("env:", "")}`;

function EnableDialog({ plugin, onClose }: { plugin: Plugin | null; onClose(): void }) {
  const { plugins } = useStudio();
  return (
    <Dialog open={plugin !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Enable {plugin?.name}?</DialogTitle>
        </DialogHeader>
        {plugin?.permissions.length ? (
          <>
            <p className="muted">This plugin asks to:</p>
            <ul className="permission-list">
              {plugin.permissions.map((permission) => (
                <li key={permission}>{describePermission(permission)}</li>
              ))}
            </ul>
          </>
        ) : (
          <p className="muted">This plugin asks for no permissions and runs fully isolated.</p>
        )}
        <DialogFooter>
          <Button variant="outline" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={() => {
              if (plugin) void plugins.getState().enable(plugin.id, plugin.permissions);
              onClose();
            }}
          >
            Enable
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PluginRow({ plugin, onEnable }: { plugin: Plugin; onEnable(): void }) {
  const { plugins } = useStudio();
  const actions = plugins.getState();
  const contributed = Object.values(plugin.contributions).flat();

  return (
    <div className="runtime-row" data-testid={`plugin-${plugin.id}`}>
      <span className="runtime-title">
        {plugin.name}
        <span className="badge">v{plugin.version}</span>
        <span className="badge">{plugin.enabled ? "enabled" : "disabled"}</span>
      </span>
      {plugin.description && <span className="field-help">{plugin.description}</span>}
      {contributed.length > 0 && (
        <span className="field-help">Adds: {contributed.join(", ")}</span>
      )}
      {plugin.problem && <span className="field-error">{plugin.problem}</span>}
      {!plugin.compatible && !plugin.problem && (
        <span className="field-error">Needs NEXUS API {plugin.nexus_api}</span>
      )}
      <div className="registry-actions">
        {plugin.enabled ? (
          <Button size="xs" variant="outline" onClick={() => void actions.disable(plugin.id)}>
            Disable
          </Button>
        ) : (
          <Button size="xs" variant="outline" disabled={!plugin.compatible} onClick={onEnable}>
            Enable
          </Button>
        )}
        <Button size="xs" variant="ghost" onClick={() => void actions.uninstall(plugin.id)}>
          Uninstall
        </Button>
      </div>
      {plugin.config_fields.length > 0 && (
        <FieldForm
          fields={plugin.config_fields}
          values={plugin.config}
          onChange={(config) => void actions.configure(plugin.id, config)}
        />
      )}
    </div>
  );
}

export function PluginsPanel() {
  const { plugins } = useStudio();
  const list = usePlugins((state) => state.plugins);
  const sandbox = usePlugins((state) => state.sandbox);
  const needsReload = usePlugins((state) => state.needsReload);
  const error = usePlugins((state) => state.error);
  const [path, setPath] = useState("");
  const [enabling, setEnabling] = useState<Plugin | null>(null);

  const install = (event: FormEvent) => {
    event.preventDefault();
    void plugins.getState().install(path.trim());
    setPath("");
  };

  return (
    <div className="panel">
      <form className="inline-form" onSubmit={install}>
        <input
          aria-label="Plugin folder"
          placeholder="Path to a plugin folder"
          required
          value={path}
          onChange={(event) => setPath(event.target.value)}
        />
        <Button type="submit" size="xs" variant="outline">
          Install
        </Button>
      </form>
      <p className="field-help">
        Installing runs nothing. Only install plugins you trust, even with the sandbox on.
        {!sandbox && " No sandbox is available here, so plugin code cannot run."}
      </p>
      {needsReload && (
        <p className="result-ok" role="status">
          <button type="button" className="text-button" onClick={() => location.reload()}>
            Reload to apply changes
          </button>
        </p>
      )}
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      {list.length === 0 && <p className="muted">No plugins installed.</p>}
      {list.map((plugin) => (
        <PluginRow key={plugin.id} plugin={plugin} onEnable={() => setEnabling(plugin)} />
      ))}
      <EnableDialog plugin={enabling} onClose={() => setEnabling(null)} />
    </div>
  );
}
