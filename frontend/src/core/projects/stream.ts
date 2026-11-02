export const PROPOSAL_MARKER = "```nexus-proposal";

/** Hides the proposal block while it streams; it comes back as a card once it is complete. */
export function visibleText(text: string): string {
  const start = text.indexOf(PROPOSAL_MARKER);
  return (start === -1 ? text : text.slice(0, start)).trimEnd();
}

export interface ChatEvents {
  onDelta(text: string): void;
  onFailure(message: string): void;
}

function dispatch(block: string, events: ChatEvents) {
  const name = block.match(/^event: (.+)$/m)?.[1];
  const data = block.match(/^data: (.+)$/m)?.[1];
  if (!name || !data) return;
  const body = JSON.parse(data);
  if (name === "delta") events.onDelta(body.text);
  if (name === "failure") events.onFailure(body.message);
}

export async function readChatStream(response: Response, events: ChatEvents): Promise<void> {
  const reader = response.body!.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += value;
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    blocks.forEach((block) => dispatch(block, events));
  }
}
