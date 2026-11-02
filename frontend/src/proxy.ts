import { readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { NextResponse, type NextRequest } from "next/server";

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);
const dataDir = process.env.NEXUS_DATA_DIR ?? path.join(os.homedir(), ".nexus");

const hostname = (value: string) => value.replace(/:\d+$/, "");

/** A cross-site page or rebinding domain must not borrow this server's access to the API. */
function isTrusted(request: NextRequest): boolean {
  const host = request.headers.get("host") ?? "";
  if (!LOCAL_HOSTS.has(hostname(host))) return false;
  const origin = request.headers.get("origin");
  if (origin && new URL(origin).host !== host) return false;
  return request.headers.get("sec-fetch-site") !== "cross-site";
}

export async function proxy(request: NextRequest) {
  if (!isTrusted(request)) {
    return NextResponse.json({ detail: "Cross-site access is refused" }, { status: 403 });
  }
  const headers = new Headers(request.headers);
  try {
    const token = await readFile(path.join(dataDir, "api-token"), "utf8");
    headers.set("authorization", `Bearer ${token.trim()}`);
  } catch {
    // The backend is not running yet; it answers 401 or the rewrite fails visibly.
    headers.delete("authorization");
  }
  return NextResponse.next({ request: { headers } });
}

export const config = { matcher: "/api/:path*" };
