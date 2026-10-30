let token = "";
export async function init() {
  const r = await fetch("/api/session");
  if (!r.ok) throw Error("Local service unavailable");
  const session = await r.json();
  token = session.token;
  return session;
}
export async function api(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<any> {
  const form = body instanceof FormData;
  const r = await fetch("/api/" + path, {
    method,
    headers: {
      "X-Session-Token": token,
      ...(body && !form ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? (form ? body : JSON.stringify(body)) : undefined,
  });
  if (!r.ok) {
    const text = await r.text();
    try {
      throw Error(JSON.parse(text).detail?.toString() || text);
    } catch (e) {
      throw e instanceof SyntaxError ? Error(text) : e;
    }
  }
  if (r.headers.get("content-type")?.includes("application/json"))
    return r.json();
  return r.blob();
}
export function download(blob: Blob, name: string) {
  const u = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = u;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(u), 1000);
}
