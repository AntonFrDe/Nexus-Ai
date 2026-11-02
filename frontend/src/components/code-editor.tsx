"use client";

import Editor, { loader, type Monaco } from "@monaco-editor/react";
import { useEffect, useState } from "react";

let ready: Promise<void> | null = null;

/** Monaco is bundled here; the wrapper's default would fetch it from a CDN at runtime. */
function loadMonaco(): Promise<void> {
  ready ??= (async () => {
    self.MonacoEnvironment = {
      getWorker: () =>
        new Worker(new URL("monaco-editor/editor/editor.worker.js", import.meta.url), {
          type: "module",
        }),
    };
    const monaco = await import("monaco-editor");
    loader.config({ monaco });
  })();
  return ready;
}

function defineTheme(monaco: Monaco) {
  monaco.editor.defineTheme("nexus", {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: { "editor.background": "#1b1d21", "editorGutter.background": "#1b1d21" },
  });
}

interface Props {
  value: string;
  language: string;
  label: string;
  height?: number;
  onChange(value: string): void;
}

export function CodeEditor({ value, language, label, height = 140, onChange }: Props) {
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    void loadMonaco().then(() => alive && setLoaded(true));
    return () => {
      alive = false;
    };
  }, []);

  if (!loaded) return <div className="editor-frame muted" style={{ height }} />;
  return (
    <div className="editor-frame" style={{ height }}>
      <Editor
        value={value}
        language={language}
        theme="nexus"
        beforeMount={defineTheme}
        onChange={(next) => onChange(next ?? "")}
        wrapperProps={{ "aria-label": label }}
        options={{
          minimap: { enabled: false },
          lineNumbers: "off",
          folding: false,
          fontSize: 12,
          fontFamily: "IBM Plex Mono, monospace",
          scrollBeyondLastLine: false,
          overviewRulerLanes: 0,
          automaticLayout: true,
          tabSize: 2,
        }}
      />
    </div>
  );
}
