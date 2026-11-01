"use client";

import { useEffect, useState } from "react";

import { useStudio } from "@/components/shell/providers";

export function LayoutInspectorPanel() {
  const { dock } = useStudio();
  const [json, setJson] = useState("");

  useEffect(() => {
    if (!dock) return;
    const update = () => setJson(JSON.stringify(dock.toJSON(), null, 2));
    update();
    const subscription = dock.onDidLayoutChange(update);
    return () => subscription.dispose();
  }, [dock]);

  return <pre className="code-block fill">{json}</pre>;
}
