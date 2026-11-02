import { describe, expect, it } from "vitest";

import {
  autoLayout,
  connectionProblem,
  createNode,
  duplicateSelection,
  fromFlow,
  GROUP_TYPE,
  groupSelection,
  matchesSearch,
  toFlow,
  ungroupSelection,
  type StudioEdge,
  type StudioNode,
} from "@/core/workflow/graph";
import { catalog, doc, wire, workflowNode } from "@/core/__tests__/workflow-fixtures";

const node = (type: string, x = 0, selected = false): StudioNode => ({
  ...createNode(type, { x, y: 0 }, catalog),
  selected,
});

describe("document conversion", () => {
  it("round-trips nodes and edges without loss", () => {
    const document = doc(
      [
        workflowNode("a", "core.text", { label: "Start", config: { x: 1 }, permissions: ["net"] }),
        workflowNode("b", "core.text"),
      ],
      [wire("a", "b")],
    );
    const { nodes, edges } = toFlow(document, catalog);
    expect(fromFlow(nodes, edges)).toEqual({ nodes: document.nodes, edges: document.edges });
  });

  it("puts groups before their children", () => {
    const document = doc([
      workflowNode("child", "core.text", { parent_id: "g" }),
      workflowNode("g", GROUP_TYPE),
    ]);
    expect(toFlow(document, catalog).nodes.map((n) => n.id)).toEqual(["g", "child"]);
  });

  it("keeps a node whose type is unknown instead of dropping it", () => {
    const { nodes } = toFlow(doc([workflowNode("a", "plugin.gone")]), catalog);
    expect(nodes[0].data.nodeType).toBe("plugin.gone");
  });

  it("applies field defaults to new nodes", () => {
    expect(createNode("core.text", { x: 0, y: 0 }, catalog).data.config).toEqual({ mode: "a" });
  });
});

describe("connectionProblem", () => {
  const a = { ...node("core.text"), id: "a" };
  const b = { ...node("core.text"), id: "b" };
  const memory = { ...node("core.memory"), id: "m" };
  const merge = { ...node("core.merge"), id: "merge" };
  const nodes = [a, b, memory, merge];
  const link = (source: string, target: string, sourceHandle = "out", targetHandle = "in") => ({
    source,
    target,
    sourceHandle,
    targetHandle,
  });
  const existing = (source: string, target: string): StudioEdge => ({
    id: `${source}-${target}`,
    ...link(source, target),
  });

  it("allows compatible ports", () => {
    expect(connectionProblem(link("a", "b"), nodes, [], catalog)).toBeNull();
  });

  it("refuses self, unknown and incompatible connections", () => {
    expect(connectionProblem(link("a", "a"), nodes, [], catalog)).toMatch(/itself/);
    expect(connectionProblem(link("a", "b", "nope"), nodes, [], catalog)).toMatch(/Unknown/);
    expect(connectionProblem(link("m", "b", "memory"), nodes, [], catalog)).toMatch(/memory to text/);
  });

  it("limits single inputs and duplicates but allows multiple inputs", () => {
    const taken = [existing("a", "b")];
    expect(connectionProblem(link("m", "b", "memory"), nodes, taken, catalog)).toBeTruthy();
    expect(connectionProblem(link("a", "b"), nodes, taken, catalog)).toMatch(/already/);
    const into = [existing("a", "merge")];
    expect(connectionProblem(link("b", "merge"), nodes, into, catalog)).toBeNull();
  });
});

describe("selection operations", () => {
  it("duplicates nodes with fresh ids and only internal edges", () => {
    const a = { ...node("core.text", 0, true), id: "a" };
    const b = { ...node("core.text", 300, true), id: "b" };
    const c = { ...node("core.text", 600), id: "c" };
    const edges: StudioEdge[] = [
      { id: "ab", source: "a", target: "b" },
      { id: "bc", source: "b", target: "c" },
    ];
    const result = duplicateSelection([a, b, c], edges);
    expect(result.nodes).toHaveLength(5);
    expect(result.edges).toHaveLength(3);
    const copy = result.nodes.at(-1)!;
    expect(copy.selected).toBe(true);
    expect(copy.id).not.toBe("b");
    expect(result.nodes[0].selected).toBe(false);
    copy.data.config.mode = "changed";
    expect(b.data.config.mode).toBe("a");
  });

  it("groups and ungroups without moving anything on screen", () => {
    const nodes = [node("core.text", 100, true), node("core.text", 400, true)];
    const grouped = groupSelection(nodes, catalog);
    expect(grouped).toHaveLength(3);
    expect(grouped[0].data.nodeType).toBe(GROUP_TYPE);
    expect(grouped[1].parentId).toBe(grouped[0].id);
    const released = ungroupSelection(
      grouped.map((n, i) => ({ ...n, selected: i === 0 })),
    );
    expect(released.map((n) => n.position.x)).toEqual([100, 400]);
    expect(released.every((n) => n.parentId === undefined)).toBe(true);
  });

  it("will not group a single node", () => {
    const nodes = [node("core.text", 0, true)];
    expect(groupSelection(nodes, catalog)).toBe(nodes);
  });
});

describe("layout and search", () => {
  it("places connected nodes left to right", () => {
    const a = { ...node("core.text"), id: "a" };
    const b = { ...node("core.text"), id: "b" };
    const [first, second] = autoLayout([a, b], [{ id: "e", source: "a", target: "b" }]);
    expect(first.position.x).toBeLessThan(second.position.x);
  });

  it("searches labels and type titles", () => {
    const labeled = { ...node("core.text"), data: { ...node("core.text").data, label: "Summarizer" } };
    expect(matchesSearch(labeled, "summ", catalog)).toBe(true);
    expect(matchesSearch(labeled, "text node", catalog)).toBe(true);
    expect(matchesSearch(labeled, "zzz", catalog)).toBe(false);
  });
});
