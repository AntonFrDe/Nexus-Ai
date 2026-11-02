import { describe, expect, it, vi } from "vitest";

import { readChatStream, visibleText } from "@/core/projects/stream";

function response(chunks: string[]) {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
        controller.close();
      },
    }),
  );
}

describe("chat stream", () => {
  it("hides the proposal block while it arrives", () => {
    expect(visibleText('Voici.\n\n```nexus-proposal\n{"road')).toBe("Voici.");
    expect(visibleText("Bonjour")).toBe("Bonjour");
  });

  it("reads events split across network chunks", async () => {
    const onDelta = vi.fn();
    await readChatStream(
      response(['event: delta\ndata: {"te', 'xt": "Bon"}\n\nevent: delta\ndata: {"text": "jour"}\n\n']),
      { onDelta, onFailure: vi.fn() },
    );
    expect(onDelta.mock.calls.flat()).toEqual(["Bon", "jour"]);
  });

  it("reports a failure", async () => {
    const onFailure = vi.fn();
    await readChatStream(response(['event: failure\ndata: {"message": "down"}\n\n']), {
      onDelta: vi.fn(),
      onFailure,
    });
    expect(onFailure).toHaveBeenCalledWith("down");
  });
});
