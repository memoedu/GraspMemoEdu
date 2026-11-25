// SPDX-License-Identifier: AGPL-3.0-or-later
import { createEffect } from "solid-js";
import { render } from "solid-js/web";
import { CollapseSurfaceContext } from "../src/components/Block";
import { BlockList } from "../src/components/BlockList";
import { readOnlyFold } from "../src/components/block/readOnlyFold";
import { emptyPage, node, pageRoots } from "../src/document";
import { loadSingle } from "../src/document/workingSet";
import { endEdit } from "../src/editorController";
import { initParser } from "../src/render/parse";
import { applyTheme } from "../src/ui";
import type { BlockDto } from "../src/types";
import "../src/styles/theme.css";
import "../src/styles/app.css";
import "katex/dist/katex.min.css";
import "./outline.css";

type Row = { id: string; parent_id: string | null; kind: string; text: string };
type Outline = { format: "topic-outline-v1"; title: string; blocks: Row[] };
const channel = "graspmemoedu-tine-v1";
const pageName = "Topic";
const message = document.querySelector<HTMLElement>("#message")!;

function openOutline(body: Outline, port: MessagePort, editable: boolean) {
  const blocks = new Map<string, BlockDto>();
  const kinds = new Map<string, string>();
  const roots: BlockDto[] = [];
  for (const row of body.blocks) {
    const block = { id: row.id, raw: row.text, collapsed: false, children: [] };
    const parent = row.parent_id === null ? roots : blocks.get(row.parent_id)?.children;
    if (!parent || blocks.has(row.id)) throw Error("大纲中的节点关系无效。");
    parent.push(block);
    blocks.set(row.id, block);
    kinds.set(row.id, row.kind);
  }
  const emptyId = crypto.randomUUID();
  if (!roots.length && editable) roots.push({ id: emptyId, raw: "", collapsed: false, children: [] });
  const page = { ...emptyPage(pageName, "page", "md"), blocks: roots, read_only: !editable };
  if (loadSingle(page)) throw Error("无法载入此 Topic。");
  const snapshot = (): Outline => {
    const rows: Row[] = [];
    const stack = [...pageRoots(pageName)].reverse();
    while (stack.length) {
      const id = stack.pop()!, block = node(id);
      if (id !== emptyId || block.raw || block.children.length || rows.length || stack.length) {
        rows.push({id, parent_id: block.parent, kind: kinds.get(id) ?? "bullet", text: block.raw});
      }
      for (let i = block.children.length - 1; i >= 0; i--) stack.push(block.children[i]);
    }
    return { format: body.format, title: body.title, blocks: rows };
  };
  let previous = JSON.stringify(snapshot());
  const reportChange = () => {
    const document = snapshot(), key = JSON.stringify(document);
    if (key === previous) return;
    previous = key;
    port.postMessage({type: "change", document});
  };
  render(() => {
    if (editable) createEffect(reportChange);
    // TINE's default editable folds write Markdown properties. Use its presentation folds here.
    return (
      <CollapseSurfaceContext.Provider value={readOnlyFold}>
        <div class="page-blocks"><BlockList ids={pageRoots(pageName)} /></div>
      </CollapseSurfaceContext.Provider>
    );
  }, document.querySelector("#outline")!);
  port.onmessage = ({data}) => {
    if (data?.type === "flush") {
      endEdit("page-navigation");
      if (editable) reportChange();
      port.postMessage({type: "flushed", id: data.id});
    }
  };
  message.hidden = true;
  port.postMessage({type: "loaded"});
}

function allowedParent(origin: string) {
  if (origin === "https://memoedu.github.io") return true;
  const local = (url: URL) => url.protocol === "http:" && ["127.0.0.1", "localhost"].includes(url.hostname);
  return origin !== "null" && local(new URL(location.href)) && local(new URL(origin));
}

let connected = false;
window.addEventListener("message", async event => {
  if (connected || window.parent === window || event.source !== window.parent ||
      !allowedParent(event.origin) || event.data?.channel !== channel || event.ports.length !== 1) return;
  connected = true;
  const port = event.ports[0];
  try {
    await initParser();
    applyTheme();
    openOutline(event.data.document, port, event.data.editable === true);
  } catch {
    message.textContent = "编辑器未能载入此大纲。";
    port.postMessage({type: "error"});
  }
});
