import dagre from "@dagrejs/dagre";
import type { Connection, Edge, Node } from "@xyflow/react";

import type {
  NodeCatalog,
  NodeType,
  PortSpec,
  WorkflowDocument,
  WorkflowEdge,
  WorkflowNode,
} from "@/core/workflow/types";

export interface StudioNodeData extends Record<string, unknown> {
  nodeType: string;
  label: string;
  config: Record<string, unknown>;
  runtime: Record<string, unknown>;
  permissions: string[];
  input_schema: Record<string, unknown> | null;
  output_schema: Record<string, unknown> | null;
}

export type StudioNode = Node<StudioNodeData>;
export type StudioEdge = Edge<{ portType: string }>;
export const GROUP_TYPE = "core.group";
const GRID = 16;

export const findType = (catalog: NodeCatalog | null, type: string): NodeType | undefined =>
  catalog?.node_types.find((nodeType) => nodeType.type === type);

const newId = (prefix: string) => `${prefix}_${crypto.randomUUID().slice(0, 8)}`;

function defaultsOf(nodeType: NodeType | undefined): Record<string, unknown> {
  return Object.fromEntries(
    (nodeType?.fields ?? [])
      .filter((field) => field.default !== null && field.default !== undefined)
      .map((field) => [field.name, field.default]),
  );
}

function portTypeOf(edge: WorkflowEdge, sourceType: NodeType | undefined): string {
  return sourceType?.outputs.find((port) => port.id === edge.source_port)?.type ?? "any";
}

export function toFlow(
  document: Pick<WorkflowDocument, "nodes" | "edges">,
  catalog: NodeCatalog | null,
): { nodes: StudioNode[]; edges: StudioEdge[] } {
  // React Flow needs a parent to appear before its children.
  const ordered = [...document.nodes].sort(
    (a, b) => Number(b.type === GROUP_TYPE) - Number(a.type === GROUP_TYPE),
  );
  const nodes = ordered.map((node): StudioNode => ({
    id: node.id,
    type: findType(catalog, node.type)?.shape ?? "card",
    position: node.position,
    parentId: node.parent_id ?? undefined,
    ...(node.width && node.height ? { width: node.width, height: node.height } : {}),
    data: {
      nodeType: node.type,
      label: node.label,
      config: node.config,
      runtime: node.runtime,
      permissions: node.permissions,
      input_schema: node.input_schema,
      output_schema: node.output_schema,
    },
  }));
  const typeOfNode = new Map(document.nodes.map((node) => [node.id, node.type]));
  const edges = document.edges.map((edge): StudioEdge => {
    const portType = portTypeOf(edge, findType(catalog, typeOfNode.get(edge.source) ?? ""));
    return {
      id: edge.id,
      source: edge.source,
      sourceHandle: edge.source_port,
      target: edge.target,
      targetHandle: edge.target_port,
      label: edge.label || undefined,
      data: { portType },
      className: `edge-${portType}`,
    };
  });
  return { nodes, edges };
}

export function fromFlow(
  nodes: StudioNode[],
  edges: StudioEdge[],
): Pick<WorkflowDocument, "nodes" | "edges"> {
  return {
    nodes: nodes.map((node): WorkflowNode => ({
      id: node.id,
      type: node.data.nodeType,
      position: node.position,
      label: node.data.label,
      config: node.data.config,
      runtime: node.data.runtime,
      permissions: node.data.permissions,
      input_schema: node.data.input_schema,
      output_schema: node.data.output_schema,
      parent_id: node.parentId ?? null,
      width: node.width ?? null,
      height: node.height ?? null,
    })),
    edges: edges.map((edge): WorkflowEdge => ({
      id: edge.id,
      source: edge.source,
      source_port: edge.sourceHandle ?? "",
      target: edge.target,
      target_port: edge.targetHandle ?? "",
      label: typeof edge.label === "string" ? edge.label : "",
    })),
  };
}

const compatible = (catalog: NodeCatalog, source: string, target: string) =>
  source === "any" ||
  target === "any" ||
  source === target ||
  (catalog.port_compatibility[source] ?? []).includes(target);

/** Instant feedback while dragging a wire. The backend validator remains authoritative. */
export function connectionProblem(
  connection: {
    source: string;
    target: string;
    sourceHandle?: string | null;
    targetHandle?: string | null;
  },
  nodes: StudioNode[],
  edges: StudioEdge[],
  catalog: NodeCatalog,
): string | null {
  if (connection.source === connection.target) return "A node cannot connect to itself";
  const portOf = (nodeId: string, side: "inputs" | "outputs", portId: string | null | undefined) => {
    const node = nodes.find((candidate) => candidate.id === nodeId);
    const type = node && findType(catalog, node.data.nodeType);
    return type?.[side].find((port: PortSpec) => port.id === portId);
  };
  const output = portOf(connection.source, "outputs", connection.sourceHandle);
  const input = portOf(connection.target, "inputs", connection.targetHandle);
  if (!output || !input) return "Unknown port";
  if (!compatible(catalog, output.type, input.type)) {
    return `Cannot connect ${output.type} to ${input.type}`;
  }
  const toSamePort = edges.filter(
    (edge) => edge.target === connection.target && edge.targetHandle === connection.targetHandle,
  );
  if (toSamePort.some((edge) => edge.source === connection.source && edge.sourceHandle === connection.sourceHandle)) {
    return "These ports are already connected";
  }
  if (toSamePort.length > 0 && !input.multiple) return `${input.label} accepts one connection`;
  return null;
}

export function createEdge(connection: Connection, catalog: NodeCatalog, nodes: StudioNode[]): StudioEdge {
  const source = nodes.find((node) => node.id === connection.source);
  const type = source && findType(catalog, source.data.nodeType);
  const portType = type?.outputs.find((port) => port.id === connection.sourceHandle)?.type ?? "any";
  return {
    id: newId("edge"),
    source: connection.source,
    sourceHandle: connection.sourceHandle,
    target: connection.target,
    targetHandle: connection.targetHandle,
    data: { portType },
    className: `edge-${portType}`,
  };
}

export function createNode(
  type: string,
  position: { x: number; y: number },
  catalog: NodeCatalog,
): StudioNode {
  const nodeType = findType(catalog, type);
  const framed = nodeType?.shape === "group" || nodeType?.shape === "annotation";
  return {
    id: newId("node"),
    type: nodeType?.shape ?? "card",
    position,
    ...(framed ? { width: 320, height: 200 } : {}),
    data: {
      nodeType: type,
      label: "",
      config: defaultsOf(nodeType),
      runtime: {},
      permissions: [],
      input_schema: null,
      output_schema: null,
    },
  };
}

export function duplicateSelection(
  nodes: StudioNode[],
  edges: StudioEdge[],
): { nodes: StudioNode[]; edges: StudioEdge[] } {
  const selected = nodes.filter((node) => node.selected);
  const ids = new Map(selected.map((node) => [node.id, newId("node")]));
  const copies = selected.map((node): StudioNode => ({
    ...node,
    id: ids.get(node.id)!,
    parentId: node.parentId && (ids.get(node.parentId) ?? node.parentId),
    position: { x: node.position.x + GRID * 2, y: node.position.y + GRID * 2 },
    data: structuredClone(node.data),
    selected: true,
  }));
  const copiedEdges = edges
    .filter((edge) => ids.has(edge.source) && ids.has(edge.target))
    .map((edge): StudioEdge => ({
      ...edge,
      id: newId("edge"),
      source: ids.get(edge.source)!,
      target: ids.get(edge.target)!,
      selected: false,
    }));
  return {
    nodes: [...nodes.map((node) => ({ ...node, selected: false })), ...copies],
    edges: [...edges, ...copiedEdges],
  };
}

const size = (node: StudioNode) => ({
  width: node.measured?.width ?? node.width ?? 220,
  height: node.measured?.height ?? node.height ?? 100,
});

export function groupSelection(nodes: StudioNode[], catalog: NodeCatalog): StudioNode[] {
  const members = nodes.filter(
    (node) => node.selected && !node.parentId && node.data.nodeType !== GROUP_TYPE,
  );
  if (members.length < 2) return nodes;
  const padding = GRID * 2;
  const left = Math.min(...members.map((node) => node.position.x)) - padding;
  const top = Math.min(...members.map((node) => node.position.y)) - padding * 2;
  const right = Math.max(...members.map((node) => node.position.x + size(node).width)) + padding;
  const bottom = Math.max(...members.map((node) => node.position.y + size(node).height)) + padding;
  const group: StudioNode = {
    ...createNode(GROUP_TYPE, { x: left, y: top }, catalog),
    width: right - left,
    height: bottom - top,
  };
  const memberIds = new Set(members.map((node) => node.id));
  return [
    group,
    ...nodes.map((node) =>
      memberIds.has(node.id)
        ? {
            ...node,
            parentId: group.id,
            selected: false,
            position: { x: node.position.x - left, y: node.position.y - top },
          }
        : node,
    ),
  ];
}

/** Dissolves selected groups, keeping members where they appear on the canvas. */
export function ungroupSelection(nodes: StudioNode[]): StudioNode[] {
  const groups = new Map(
    nodes
      .filter((node) => node.selected && node.data.nodeType === GROUP_TYPE)
      .map((node) => [node.id, node]),
  );
  return nodes
    .filter((node) => !groups.has(node.id))
    .map((node) => {
      const parent = node.parentId ? groups.get(node.parentId) : undefined;
      if (!parent) return node;
      return {
        ...node,
        parentId: undefined,
        position: {
          x: node.position.x + parent.position.x,
          y: node.position.y + parent.position.y,
        },
      };
    });
}

export function autoLayout(nodes: StudioNode[], edges: StudioEdge[]): StudioNode[] {
  const graph = new dagre.graphlib.Graph();
  graph.setGraph({ rankdir: "LR", nodesep: GRID * 3, ranksep: GRID * 6 });
  graph.setDefaultEdgeLabel(() => ({}));
  const movable = nodes.filter(
    (node) => !node.parentId && node.data.nodeType !== GROUP_TYPE && node.type !== "annotation",
  );
  const ids = new Set(movable.map((node) => node.id));
  movable.forEach((node) => graph.setNode(node.id, size(node)));
  edges
    .filter((edge) => ids.has(edge.source) && ids.has(edge.target))
    .forEach((edge) => graph.setEdge(edge.source, edge.target));
  dagre.layout(graph);
  return nodes.map((node) => {
    if (!ids.has(node.id)) return node;
    const { x, y } = graph.node(node.id);
    const { width, height } = size(node);
    return { ...node, position: { x: x - width / 2, y: y - height / 2 } };
  });
}

export const matchesSearch = (
  node: StudioNode,
  query: string,
  catalog: NodeCatalog | null,
): boolean => {
  const needle = query.trim().toLowerCase();
  const title = findType(catalog, node.data.nodeType)?.title ?? "";
  return `${node.data.label} ${title}`.toLowerCase().includes(needle);
};
