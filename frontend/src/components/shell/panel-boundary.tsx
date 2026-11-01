"use client";

import { Component, type ReactNode } from "react";

interface Props {
  title: string;
  children: ReactNode;
}

/** A failing panel must not take the rest of the workspace down with it. */
export class PanelBoundary extends Component<Props, { error: Error | null }> {
  state = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    const { error } = this.state as { error: Error | null };
    if (!error) return this.props.children;
    return (
      <div className="panel" role="alert">
        <p className="panel-heading">{this.props.title} crashed</p>
        <pre className="code-block">{error.message}</pre>
      </div>
    );
  }
}
