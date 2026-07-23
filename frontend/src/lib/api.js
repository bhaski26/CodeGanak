import axios from "axios";
import { getToken, clearAuth } from "@/lib/auth";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 60_000,
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      clearAuth();
      if (
        typeof window !== "undefined" &&
        !window.location.pathname.startsWith("/login") &&
        !window.location.pathname.startsWith("/register") &&
        window.location.pathname !== "/"
      ) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  },
);

/** Fetch-based SSE helper for streaming chat responses.
 *  Yields events { type: 'citations'|'delta'|'done'|'error', data }.
 */
export async function* streamChat(repoId, message) {
  const token = getToken();
  const res = await fetch(`${API_BASE}/repositories/${repoId}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: token ? `Bearer ${token}` : "",
    },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Chat failed (${res.status}): ${text}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const raw = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const lines = raw.split("\n");
      let event = "message";
      let dataLine = "";
      for (const l of lines) {
        if (l.startsWith("event:")) event = l.slice(6).trim();
        else if (l.startsWith("data:")) dataLine += l.slice(5).trim();
      }
      let data = dataLine;
      try {
        data = JSON.parse(dataLine);
      } catch (_e) {
        // ignore JSON parse errors, keep string
      }
      yield { type: event, data };
      if (event === "done") return;
    }
  }
}
