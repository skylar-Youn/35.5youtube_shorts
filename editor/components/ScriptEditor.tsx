"use client";
import useStore from "../lib/store";

export default function ScriptEditor() {
  const { project, setProject } = useStore();
  if (!project) return <div style={panel}>프로젝트 없음</div>;
  const s = project.script || { title: "", price: "", features: [], cta: "" };
  const update = (k: string, v: any) => setProject({ ...project, script: { ...s, [k]: v } });
  return (
    <div style={panel}>
      <div style={title}>대본 편집</div>
      <div style={row}><label>제목</label><input value={s.title} onChange={(e) => update("title", e.target.value)} /></div>
      <div style={row}><label>가격</label><input value={s.price || ""} onChange={(e) => update("price", e.target.value)} /></div>
      <div style={row}><label>CTA</label><input value={s.cta || ""} onChange={(e) => update("cta", e.target.value)} /></div>
      <div style={{ marginTop: 6 }}>
        <div style={{ fontSize: 12, color: "#9fb1c9" }}>특징(줄바꿈으로 구분)</div>
        <textarea value={(s.features || []).join("\n")} rows={6} style={{ width: "100%", background: "#0b0f14", color: "#d7dde6", border: "1px solid #283244", borderRadius: 6, padding: 6 }} onChange={(e) => update("features", e.target.value.split(/\n+/).filter(Boolean))} />
      </div>
    </div>
  );
}

const panel: React.CSSProperties = { border: "1px solid #1e242d", borderRadius: 8, padding: 8, background: "#0f1318" };
const title: React.CSSProperties = { fontSize: 13, color: "#cbd5e1", marginBottom: 8 };
const row: React.CSSProperties = { display: "flex", alignItems: "center", gap: 8, marginBottom: 6 };

