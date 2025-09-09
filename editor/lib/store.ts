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
    const res = await fetch(`${backend}/projects/${p.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(p) });
    const data = await res.json();
    set({ project: data });
  },
  createProject: async (backend, name) => {
    const res = await fetch(`${backend}/projects`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) });
    const data = await res.json();
    return data;
  },
  loadProjectList: async (backend) => {
    const res = await fetch(`${backend}/projects`);
    const data = await res.json();
    return data?.projects || [];
  },
}));

export default useStore;

