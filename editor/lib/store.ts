"use client";
import create from "zustand";

type Transform = { x: number; y: number; scale: number; opacity: number; rotation: number };
type Clip = { id: string; type: "video" | "image" | "audio" | "text"; src?: string; start: number; duration: number; transform: Transform; text?: string; text_size?: number; text_color?: string; text_align?: "left"|"center"|"right" };
type Track = { id: string; kind: Clip["type"]; clips: Clip[] };
type Project = { id: string; name: string; width: number; height: number; fps: number; duration: number; tracks: Track[]; script: any; assets: Record<string,string> };

type Store = {
  project?: Project;
  setProject: (p?: Project) => void;
  updateProject: (backend: string, p: Project) => Promise<void>;
  createProject: (backend: string, name: string) => Promise<Project>;
  loadProjectList: (backend: string) => Promise<any[]>;
};

const useStore = create<Store>((set, get) => ({
  project: undefined,
  setProject: (p) => set({ project: p }),
  updateProject: async (backend, p) => {
    try {
      const res = await fetch(`${backend}/projects/${p.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(p) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      set({ project: data });
    } catch (err) {
      console.error("updateProject failed", err);
    }
  },
  createProject: async (backend, name) => {
    try {
      const res = await fetch(`${backend}/projects`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return data;
    } catch (err) {
      console.error("createProject failed", err);
      return Promise.reject(err);
    }
  },
  loadProjectList: async (backend) => {
    try {
      const res = await fetch(`${backend}/projects`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return data?.projects || [];
    } catch (err) {
      console.error("loadProjectList failed", err);
      return [];
    }
  },
}));

export default useStore;
