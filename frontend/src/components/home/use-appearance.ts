"use client";

import { useEffect } from "react";

import { apiClient } from "@/lib/api";

export function useAppearance() {
  useEffect(() => {
    void apiClient
      .getSetting("appearance")
      .then((value) => {
        const appearance = value as { accent?: string; density?: string } | null;
        if (appearance?.accent) document.documentElement.dataset.accent = appearance.accent;
        if (appearance?.density) document.documentElement.dataset.density = appearance.density;
      })
      .catch(() => undefined);
  }, []);
}
