let ws = null;
const listeners = new Set();

export function subscribeWS(cb) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

export function ensureWS() {
  if (ws && ws.readyState <= 1) return;
  const token = localStorage.getItem("neris_token");
  if (!token) return;
  const base = (process.env.REACT_APP_BACKEND_URL || "").replace(/^http/, "ws");
  try {
    ws = new WebSocket(`${base}/api/ws?token=${token}`);
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        listeners.forEach((cb) => cb(msg));
      } catch (err) { /* ignore malformed */ }
    };
    ws.onclose = () => {
      ws = null;
      if (localStorage.getItem("neris_token")) setTimeout(ensureWS, 5000);
    };
    ws.onerror = () => { try { ws.close(); } catch (e) { /* noop */ } };
  } catch (e) { ws = null; }
}

export function closeWS() {
  const sock = ws;
  ws = null;
  if (sock) { try { sock.close(); } catch (e) { /* noop */ } }
}
