/* Web Worker: runs the Iron & Ash Python game under Pyodide.
 *
 * The game is unmodified CPython that calls blocking input()/print(). To make
 * that work in a browser we:
 *   - stream stdout/stderr to the page via postMessage;
 *   - back stdin with a SharedArrayBuffer: input() blocks the worker on
 *     Atomics.wait until the main thread writes a line and notifies;
 *   - persist saves in IndexedDB via Pyodide's IDBFS, flushed before each prompt.
 */
importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.2/full/pyodide.js");

let pyodide = null;
let control = null;      // Int32Array [flag, length] over the shared buffer
let dataBytes = null;    // Uint8Array payload region of the shared buffer
const decoder = new TextDecoder();

function out(text) { postMessage({ type: "out", text }); }

function stdin() {
  // flush any just-written save files to IndexedDB before we block for input
  try { pyodide.FS.syncfs(false, () => {}); } catch (e) { /* ignore */ }
  postMessage({ type: "awaiting" });
  // wait while the flag is 0 (no input ready)
  Atomics.wait(control, 0, 0);
  const len = control[1];
  const text = decoder.decode(dataBytes.slice(0, len));
  Atomics.store(control, 0, 0);      // consume
  return text;                        // main includes the trailing newline
}

async function boot(sharedBuffer) {
  control = new Int32Array(sharedBuffer, 0, 2);
  dataBytes = new Uint8Array(sharedBuffer, 8);

  out("Loading the game engine (first run downloads ~10 MB)...\n");
  pyodide = await loadPyodide();

  // persistent saves in IndexedDB
  pyodide.FS.mkdir("/iaa_saves");
  pyodide.FS.mount(pyodide.FS.filesystems.IDBFS, {}, "/iaa_saves");
  await new Promise((res) => pyodide.FS.syncfs(true, res));

  // fetch and unpack the game package
  const resp = await fetch("iron_and_ash.zip");
  const buf = await resp.arrayBuffer();
  await pyodide.unpackArchive(buf, "zip");

  pyodide.setStdout({ batched: out });
  pyodide.setStderr({ batched: out });
  pyodide.setStdin({ stdin, autoEOF: false });

  pyodide.runPython(`
import os, sys
sys.path.insert(0, "/home/pyodide")
os.environ["IRON_AND_ASH_HOME"] = "/iaa_saves"
os.environ["IRON_AND_ASH_NO_PYDANTIC"] = "1"   # pure-stdlib path in the browser
`);

  postMessage({ type: "ready" });
  try {
    await pyodide.runPythonAsync("import iron_and_ash.app as a; a.main()");
  } catch (e) {
    out("\n[the game ended: " + e.message + "]\n");
  }
  try { pyodide.FS.syncfs(false, () => {}); } catch (e) { /* ignore */ }
  postMessage({ type: "exit" });
}

onmessage = (ev) => {
  if (ev.data && ev.data.type === "boot") boot(ev.data.buffer);
};
