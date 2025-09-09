"use client";
import useStore from "../lib/store";

export default function Properties() {
  const { project, setProject } = useStore();
  if (!project) return <div style={panel}>프로젝트 없음</div>;
  return (
    <div style={panel}>
      <div style={title}>프로젝트 속성</div>
      <div style={row}><label>이름</label><input value={project.name} onChange={(e) => setProject({ ...project, name: e.target.value })} /></div>
      <div style={row}><label>해상도</label><input value={project.width} style={{ width: 80 }} onChange={() => {}} /> x <input value={project.height} style={{ width: 80 }} onChange={() => {}} /></div>
      <div style={row}><label>FPS</label><input value={project.fps} style={{ width: 80 }} onChange={() => {}} /></div>
      <div style={row}><label>길이(s)</label><input value={project.duration} style={{ width: 120 }} onChange={() => {}} /></div>
      <div style={{ height: 1, background: "#1e242d", margin: "10px 0" }} />
      <div style={title}>템플릿</div>
      <div style={{ fontSize: 12, color: "#9fb1c9" }}>상단바/색/텍스트는 렌더 시 적용</div>
    </div>
  );
}

const panel: React.CSSProperties = { border: "1px solid #1e242d", borderRadius: 8, padding: 8, background: "#0f1318" };
const title: React.CSSProperties = { fontSize: 13, color: "#cbd5e1", marginBottom: 8 };
const row: React.CSSProperties = { display: "flex", alignItems: "center", gap: 8, marginBottom: 6 };

