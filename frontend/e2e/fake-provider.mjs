// Test double for Ollama and OpenAI-style servers. Never used outside the end-to-end tests.
import { createServer } from "node:http";

const KEY = "e2e-test-key";

const send = (response, status, body) => {
  response.writeHead(status, { "Content-Type": "application/json" });
  response.end(JSON.stringify(body));
};

createServer((request, response) => {
  let raw = "";
  request.on("data", (chunk) => (raw += chunk));
  request.on("end", () => {
    const authorized = request.headers.authorization === `Bearer ${KEY}`;
    if (request.url === "/api/tags") {
      return send(response, 200, { models: [{ name: "local-coder:latest" }] });
    }
    if (request.url === "/api/chat") {
      const body = JSON.parse(raw);
      return send(response, 200, {
        model: body.model,
        message: { role: "assistant", content: "ready" },
        done: true,
        prompt_eval_count: 4,
        eval_count: 1,
      });
    }
    if (!authorized) return send(response, 401, { error: { message: "bad key" } });
    if (request.url === "/v1/models") return send(response, 200, { data: [{ id: "hosted-model" }] });
    if (request.url === "/v1/chat/completions") {
      return send(response, 200, {
        id: "1",
        object: "chat.completion",
        created: 1,
        model: JSON.parse(raw).model,
        choices: [{ index: 0, finish_reason: "stop", message: { role: "assistant", content: "ready" } }],
        usage: { prompt_tokens: 4, completion_tokens: 1, total_tokens: 5 },
      });
    }
    return send(response, 404, {});
  });
}).listen(11999, "127.0.0.1");
