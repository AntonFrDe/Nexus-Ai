"use client";

import { Handle, NodeResizer, Position, type NodeProps, type NodeTypes } from "@xyflow/react";

import { useExecution, useWorkflow } from "@/components/shell/providers";
import { NodeIcon } from "@/components/workflow/node-icon";
import { findType, type StudioNode } from "@/core/workflow/graph";
import type { PortSpec } from "@/core/workflow/types";

function Ports({ ports, side }: { ports: PortSpec[]; side: "in" | "out" }) {
  return (
    <div className="node-ports" data-side={side}>
      {ports.map((port) => (
        <div className="node-port" key={port.id} title={`${port.label} (${port.type})`}>
          <Handle
            id={port.id}
            type={side === "in" ? "target" : "source"}
            position={side === "in" ? Position.Left : Position.Right}
            data-port-type={port.type}
          />
          <span>{port.label}</span>
        </div>
      ))}
    </div>
  );
}

function ExecutableNode({ id, data, selected }: NodeProps<StudioNode>) {
  const catalog = useWorkflow((state) => state.catalog);
  const activeWorkflow = useWorkflow((state) => state.meta?.id);
  const severity = useWorkflow((state) => {
    const issues = state.issues.filter((issue) => issue.node_id === id);
    if (issues.some((issue) => issue.severity === "error")) return "error";
    return issues.length ? "warning" : null;
  });
  const runStatus = useExecution((state) => {
    const execution = state.current;
    if (!execution || execution.workflow_id !== activeWorkflow) return undefined;
    return execution.nodes.findLast((row) => row.node_id === id)?.status;
  });
  const type = findType(catalog, data.nodeType);

  return (
    <div
      className="flow-node"
      data-run={runStatus?.toLowerCase()}
      data-shape={type?.shape ?? "card"}
      data-selected={selected}
      data-severity={severity ?? undefined}
      data-testid={`node-${data.nodeType}`}
    >
      <div className="flow-node-title">
        <NodeIcon name={type?.icon ?? "box"} className="size-3.5" />
        <span>{data.label || type?.title || data.nodeType}</span>
        {severity && <span className="flow-node-status" aria-label={`Has ${severity}s`} />}
      </div>
      {!type && <p className="flow-node-unknown">Unknown type: {data.nodeType}</p>}
      {type && (type.inputs.length > 0 || type.outputs.length > 0) && (
        <div className="flow-node-ports">
          <Ports ports={type.inputs} side="in" />
          <Ports ports={type.outputs} side="out" />
        </div>
      )}
    </div>
  );
}

function GroupNode({ data, selected }: NodeProps<StudioNode>) {
  return (
    <>
      <NodeResizer isVisible={selected} minWidth={160} minHeight={100} />
      <div className="flow-group" data-selected={selected}>
        <span>{data.label || "Group"}</span>
      </div>
    </>
  );
}

function AnnotationNode({ data, selected }: NodeProps<StudioNode>) {
  return (
    <>
      <NodeResizer isVisible={selected} minWidth={120} minHeight={60} />
      <div className="flow-annotation" data-selected={selected}>
        {(data.config.text as string | undefined) || "Empty note"}
      </div>
    </>
  );
}

/** Shapes the canvas can draw. A node type picks one by name in its catalog entry. */
export const NODE_RENDERERS: NodeTypes = {
  card: ExecutableNode,
  diamond: ExecutableNode,
  pill: ExecutableNode,
  group: GroupNode,
  annotation: AnnotationNode,
};
