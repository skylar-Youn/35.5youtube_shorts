"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import useStore from "../lib/store";

export default function Timeline() {
  const { project, setProject, selected, setSelected, pxPerSec, setPxPerSec, updateSelectedClip, deleteSelected, updateProject, selectedAssetId } = useStore();
  const backend = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  const addText = async () => {
    if (!project) return;
    const p = { ...project, tracks: project.tracks.map((t) => ({ ...t, clips: [...t.clips] })) } as any;
    let t = p.tracks.find((t: any) => t.kind === "text");
    if (!t) {
      t = { id: "t1", kind: "text", clips: [] };
      p.tracks.push(t);
    }
    const id = Math.random().toString(36).slice(2, 8);
    t.clips.push({ id, type: "text", start: 0, duration: 3, transform: { x: 0.5, y: 0.8, scale: 1, opacity: 1, rotation: 0 }, text: "텍스트", text_size: 48, text_color: "#ffffff", text_align: "center" });
    setProject(p);
  };
  const addImage = async () => {
    if (!project) return;
    const p = { ...project, tracks: project.tracks.map((t) => ({ ...t, clips: [...t.clips] })) } as any;
    let v = p.tracks.find((t: any) => t.kind === "image");
    if (!v) {
      v = { id: "v1", kind: "image", clips: [] };
      p.tracks.unshift(v);
    }
    const assetPath = selectedAssetId ? (p.assets || {})[selectedAssetId] : (Object.values(p.assets || {})[0] as string | undefined);
    if (!v || !assetPath) return alert("먼저 에셋을 업로드하거나 선택하세요.");
    const id = Math.random().toString(36).slice(2, 8);
    v.clips.push({ id, type: "image", src: assetPath, start: 0, duration: 3, transform: { x: 0.5, y: 0.5, scale: 1, opacity: 1, rotation: 0 } });
    setProject(p);
  };
  const save = async () => {
    if (!project) return alert("프로젝트를 먼저 선택하세요.");
    try {
      await updateProject(backend, project as any);
      // Optionally toast here; keeping minimal alert for now
      // alert("저장 완료");
    } catch {
      alert("저장 실패");
    }
  };

  // Keyboard shortcuts
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!selected) return;
      if (e.key === "Delete") {
        e.preventDefault();
        deleteSelected();
      }
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        const delta = (e.shiftKey ? 1.0 : 0.1) * (e.key === "ArrowLeft" ? -1 : 1);
        updateSelectedClip((c: any) => ({ ...c, start: Math.max(0, +(c.start + delta).toFixed(3)) }));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selected, updateSelectedClip, deleteSelected]);

  return (
    <div style={{ border: "1px solid #1e242d", borderRadius: 8, padding: 8, background: "#0f1318" }}>
      <div style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center" }}>
        <button disabled={!project} onClick={addImage} style={btn}>이미지 클립 추가</button>
        <button disabled={!project} onClick={addText} style={btn}>텍스트 클립 추가</button>
        <button disabled={!project} onClick={save} style={{ ...btn, background: "#1f6feb" }}>타임라인 저장</button>
        <div style={{ marginLeft: 12, color: "#9fb1c9", fontSize: 12 }}>줌</div>
        <input type="range" min={20} max={600} value={pxPerSec} onChange={(e) => setPxPerSec(parseInt(e.target.value, 10))} />
        <div style={{ color: "#64748b", fontSize: 12 }}>{pxPerSec} px/s</div>
      </div>
      <div style={{ fontSize: 12, color: "#9fb1c9" }}>트랙</div>
      <div style={{ overflowX: "auto", border: "1px solid #1e242d", borderRadius: 6 }}>
        {(project?.tracks || []).map((t) => (
          <TrackRow key={t.id} t={t} duration={project?.duration || 0} />
        ))}
      </div>
    </div>
  );
}

function TrackRow({ t, duration }: { t: any; duration: number }) {
  const { selected, setSelected, updateSelectedClip, pxPerSec } = useStore();
  const railRef = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<null | { mode: "move" | "l" | "r"; startX: number; origStart: number; origDur: number }>(null);

  const width = Math.max(600, Math.round(duration * pxPerSec));
  const snap = (t: number) => Math.max(0, Math.round(t * 10) / 10); // 0.1s

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!drag || !selected) return;
      const dx = e.clientX - drag.startX;
      const dt = dx / pxPerSec;
      if (drag.mode === "move") {
        updateSelectedClip((c: any) => ({ ...c, start: snap(drag.origStart + dt) }));
      } else if (drag.mode === "l") {
        const newStart = snap(Math.min(drag.origStart + drag.origDur, Math.max(0, drag.origStart + dt)));
        let newDur = snap(drag.origDur + (drag.origStart - newStart));
        if (newDur < 0.1) newDur = 0.1;
        updateSelectedClip((c: any) => ({ ...c, start: newStart, duration: newDur }));
      } else if (drag.mode === "r") {
        let newDur = snap(Math.max(0.1, drag.origDur + dt));
        updateSelectedClip((c: any) => ({ ...c, duration: newDur }));
      }
    };
    const onUp = () => setDrag(null);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [drag, selected, pxPerSec, updateSelectedClip]);

  return (
    <div style={{ borderTop: "1px solid #1e242d", padding: 6 }}>
      <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 4 }}>{t.kind}</div>
      <div ref={railRef} style={{ position: "relative", height: 40, minWidth: width, background: "#0b0f14" }}>
        {(t.clips || []).map((c: any) => {
          const left = Math.round(c.start * pxPerSec);
          const w = Math.max(12, Math.round(c.duration * pxPerSec));
          const sel = selected && selected.trackId === t.id && selected.clipId === c.id;
          return (
            <div key={c.id}
              onMouseDown={(e) => {
                setSelected({ trackId: t.id, clipId: c.id });
                const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
                const x = e.clientX - rect.left;
                if (x < 8) {
                  setDrag({ mode: "l", startX: e.clientX, origStart: c.start, origDur: c.duration });
                } else if (x > w - 8) {
                  setDrag({ mode: "r", startX: e.clientX, origStart: c.start, origDur: c.duration });
                } else {
                  setDrag({ mode: "move", startX: e.clientX, origStart: c.start, origDur: c.duration });
                }
              }}
              style={{ position: "absolute", left, top: 6, height: 28, width: w, background: sel ? "#1f6feb" : "#1a2230", border: "1px solid #283244", borderRadius: 4, color: "#cbd5e1", fontSize: 12, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 6px", boxSizing: "border-box", cursor: "grab", userSelect: "none" }}>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.type}{c.text ? `: ${c.text}` : ""}</span>
              <span style={{ color: "#9fb1c9" }}>{c.start.toFixed(1)}s/{c.duration.toFixed(1)}s</span>
              <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 6, cursor: "ew-resize" }} />
              <div style={{ position: "absolute", right: 0, top: 0, bottom: 0, width: 6, cursor: "ew-resize" }} />
            </div>
          );
        })}
      </div>
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
