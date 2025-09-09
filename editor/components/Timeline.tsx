"use client";
import useStore from "../lib/store";

export default function Timeline() {
  const { project, setProject } = useStore();
  const addText = () => {
    if (!project) return;
    const p = { ...project } as any;
    const t = p.tracks.find((t: any) => t.kind === "text");
    if (!t) return;
    const id = Math.random().toString(36).slice(2, 8);
    t.clips.push({ id, type: "text", start: 0, duration: 3, transform: { x: 0.5, y: 0.8, scale: 1, opacity: 1, rotation: 0 }, text: "텍스트", text_size: 48, text_color: "#ffffff", text_align: "center" });
    setProject(p);
  };
  const addImage = () => {
    if (!project) return;
    const p = { ...project } as any;
    const v = p.tracks.find((t: any) => t.kind === "image");
    const firstAssetPath = Object.values(p.assets || {})[0] as string | undefined;
    if (!v || !firstAssetPath) return alert("먼저 에셋을 업로드하세요.");
    const id = Math.random().toString(36).slice(2, 8);
    v.clips.push({ id, type: "image", src: firstAssetPath, start: 0, duration: 3, transform: { x: 0.5, y: 0.5, scale: 1, opacity: 1, rotation: 0 } });
    setProject(p);
  };
  const save = async () => {
    if (!project) return;
    const backend = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
    const res = await fetch(`${backend}/projects/${project.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(project) });
    if (!res.ok) alert("저장 실패");
  };
  return (
    <div style={{ border: "1px solid #1e242d", borderRadius: 8, padding: 8, background: "#0f1318" }}>
      <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
        <button onClick={addImage} style={btn}>이미지 클립 추가</button>
        <button onClick={addText} style={btn}>텍스트 클립 추가</button>
        <button onClick={save} style={{ ...btn, background: "#1f6feb" }}>타임라인 저장</button>
      </div>
      <div style={{ fontSize: 12, color: "#9fb1c9" }}>트랙</div>
      <div>
        {(project?.tracks || []).map((t) => (
          <TrackRow key={t.id} t={t} />
        ))}
      </div>
    </div>
  );
}

function TrackRow({ t }: { t: any }) {
  const { project, setProject } = useStore();
  const removeClip = (id: string) => {
    if (!project) return;
    const p = { ...project } as any;
    const tt = p.tracks.find((x: any) => x.id === t.id);
    tt.clips = tt.clips.filter((c: any) => c.id !== id);
    setProject(p);
  };
  return (
    <div style={{ borderTop: "1px solid #1e242d", padding: "6px 0" }}>
      <div style={{ fontSize: 12, color: "#94a3b8" }}>{t.kind}</div>
      <div style={{ display: "flex", gap: 6, overflowX: "auto" }}>
        {t.clips.map((c: any) => (
          <div key={c.id} style={{ minWidth: 140, background: "#1a2230", border: "1px solid #283244", borderRadius: 6, padding: 6 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#9fb1c9" }}>
              <span>{c.type}</span>
              <button onClick={() => removeClip(c.id)} style={{ ...btn, padding: "2px 6px" }}>삭제</button>
            </div>
            <div style={{ fontSize: 11, color: "#64748b" }}>start {c.start}s / dur {c.duration}s</div>
            {c.text && <div style={{ fontSize: 12, color: "#cbd5e1", paddingTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.text}</div>}
          </div>
        ))}
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

