import { create } from "zustand";
import { api } from "@/lib/api";

const KEY = "codeganak.current_workspace";

export const useWorkspaces = create((set, get) => ({
  workspaces: [],
  currentId: (() => {
    try {
      return localStorage.getItem(KEY) || null;
    } catch {
      return null;
    }
  })(),
  loaded: false,

  setCurrent(id) {
    try {
      if (id) localStorage.setItem(KEY, id);
      else localStorage.removeItem(KEY);
    } catch {
      // no-op
    }
    set({ currentId: id });
  },

  async refresh() {
    const { data } = await api.get("/workspaces");
    const list = data || [];
    let currentId = get().currentId;
    if (!currentId || !list.find((w) => w.id === currentId)) {
      const personal = list.find((w) => w.is_personal) || list[0];
      currentId = personal?.id || null;
      try {
        if (currentId) localStorage.setItem(KEY, currentId);
      } catch {
        // no-op
      }
    }
    set({ workspaces: list, currentId, loaded: true });
    return list;
  },

  current() {
    const s = get();
    return s.workspaces.find((w) => w.id === s.currentId) || null;
  },
}));

export function clearWorkspaceCache() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // no-op
  }
}
