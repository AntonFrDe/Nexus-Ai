/** Saves a JSON document through the browser, named `<slug>.nexus-<kind>.json`. */
export async function downloadJson(document_: unknown, name: string, kind: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(document_, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `${name.replace(/[^\w-]+/g, "-").toLowerCase()}.nexus-${kind}.json`;
  link.click();
  URL.revokeObjectURL(url);
}
