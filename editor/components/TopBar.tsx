"use client";
import { useMemo, useState } from "react";
import useStore from "../lib/store";

export default function TopBar({ onNew, projects, onSelect, onRender }: { onNew: () => void; projects: any[]; onSelect: (id: string) => void; onRender: () => void; }) {
  const backend = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const { project, setProject, updateProject } = useStore();
  const [progress, setProgress] = useState<number | null>(null);
  const [resPreset, setResPreset] = useState<string>("default");

  const applyPreset = async (w: number, h: number) => {
    if (!project) return;
    const np = { ...project, width: w, height: h } as any;
    // Optimistic local update, then persist to backend.
    setProject(np);
    try { await updateProject(backend, np); } catch {}
  };

  const renderSSE = async () => {
    if (!project?.id) return;
    try {
      const res = await fetch(`${backend}/render/start`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: project.id }) });
      if (!res.ok) throw new Error();
      const { jobId } = await res.json();
      setProgress(0);
      const es = new EventSource(`${backend}/render/sse/${jobId}`);
      es.addEventListener("progress", (ev: any) => {
        try {
          const data = JSON.parse(ev.data);
          setProgress(data.progress);
        } catch {}
      });
      es.addEventListener("message", (ev: any) => {
        try { JSON.parse(ev.data); } catch {}
        setProgress(1);
        es.close();
      });
      es.addEventListener("error", () => {
        es.close();
        setProgress(null);
      });
    } catch {
      alert("렌더 시작 실패 (SSE)");
    }
  };

  const ratio = useMemo(() => {
    if (!project) return 9 / 16;
    return project.width > 0 && project.height > 0 ? project.width / project.height : 9 / 16;
  }, [project]);

  const applyResolutionPreset = async (name: "720p" | "1080p" | "1440p" | "4K") => {
    if (!project) return;
    const level = name;
    const map: Record<typeof level, [number, number]> = {
      "720p": [1280, 720],
      "1080p": [1920, 1080],
      "1440p": [2560, 1440],
      "4K": [3840, 2160],
    } as any;
    const base = map[level];
    let w = project.width;
    let h = project.height;

    const near = (a: number, b: number, eps = 0.02) => Math.abs(a - b) / Math.max(1, b) < eps;
    const r = ratio;

    if (near(r, 1)) {
      // Square
      w = base[1];
      h = base[1];
    } else if (near(r, 16 / 9)) {
      // 16:9 landscape
      w = base[0];
      h = base[1];
    } else if (near(r, 9 / 16)) {
      // 9:16 portrait
      w = base[1];
      h = base[0];
    } else {
      // Arbitrary ratio: scale long edge to the corresponding long value
      const long = base[0]; // 1280,1920,2560,3840
      if (r >= 1) {
        w = long;
        h = Math.round(w / r);
      } else {
        h = long;
        w = Math.round(h * r);
      }
    }

    await applyPreset(w, h);
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "0 8px", borderBottom: "1px solid #1e242d", background: "#0f1318" }}>
      <button onClick={onNew} style={btn}>새 프로젝트</button>
      <select onChange={(e) => onSelect(e.target.value)} style={{ background: "#11161d", color: "#d7dde6", border: "1px solid #283244", borderRadius: 6, padding: 6 }}>
        <option>프로젝트 선택...</option>
        {projects.map((p) => (
          <option key={p.id} value={p.id}>{p.name}</option>
        ))}
      </select>
      <div style={{ display: "flex", gap: 6, marginLeft: 6 }}>
        <button title="9:16 (1080x1920)" disabled={!project} onClick={() => applyPreset(1080, 1920)} style={btn}>9:16</button>
        <button title="1:1 (1080x1080)" disabled={!project} onClick={() => applyPreset(1080, 1080)} style={btn}>1:1</button>
        <button title="16:9 (1920x1080)" disabled={!project} onClick={() => applyPreset(1920, 1080)} style={btn}>16:9</button>
      </div>
      <select
        disabled={!project}
        value={resPreset}
        onChange={async (e) => {
          const v = e.target.value as any;
          setResPreset(v);
          if (v !== "default") {
            await applyResolutionPreset(v);
            setResPreset("default");
          }
        }}
        style={{ background: "#11161d", color: "#d7dde6", border: "1px solid #283244", borderRadius: 6, padding: 6 }}
      >
        <option value="default">해상도</option>
        <option value="720p">720p</option>
        <option value="1080p">1080p</option>
        <option value="1440p">1440p</option>
        <option value="4K">4K</option>
      </select>
      <div style={{ flex: 1 }} />
      {progress != null && (
        <div style={{ width: 220, height: 10, border: "1px solid #283244", borderRadius: 6, background: "#0b0f14", overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${Math.round((progress || 0)*100)}%`, background: "#1f6feb" }} />
        </div>
      )}
      <button onClick={renderSSE} style={btn}>렌더(SSE)</button>
      <button onClick={onRender} style={{ ...btn, background: "#1f6feb" }}>렌더</button>
    </div>
  );
}

const btn: React.CSSProperties = {
  background: "#18202b",
  border: "1px solid #2a3547",
  color: "#d7dde6",
  borderRadius: 6,
  padding: "6px 10px",
  cursor: "pointer"
};
