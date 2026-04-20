// Shared fetch helper — each prototype imports this.
// Hit the same-origin API when FastAPI serves the frontend; fall back to
// a clear error if the API is unreachable.

export async function loadSnapshot() {
  const res = await fetch("/api/snapshot", { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return await res.json();
}

export function fmtPct(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const s = n > 0 ? "+" : "";
  return `${s}${n.toFixed(2)}%`;
}

export function fmtNum(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (Math.abs(n) >= 10)   return n.toFixed(2);
  return n.toFixed(4);
}

export function relTime(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const diff = (Date.now() - then) / 1000;
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff/60)}m ago`;
  if (diff < 86400) return `${Math.round(diff/3600)}h ago`;
  return `${Math.round(diff/86400)}d ago`;
}

export function errorBanner(err) {
  const el = document.createElement("div");
  el.style.cssText = "padding:12px 16px;background:#3b0e12;color:#ffd3d6;border:1px solid #6a1a22;border-radius:8px;font:14px/1.4 system-ui;margin:16px";
  el.textContent = `API unreachable: ${err.message}. Is uvicorn running?`;
  return el;
}
