"use client";
export default function TopBar({ onNew, projects, onSelect, onRender }: { onNew: () => void; projects: any[]; onSelect: (id: string) => void; onRender: () => void; }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "0 8px", borderBottom: "1px solid #1e242d", background: "#0f1318" }}>
      <button onClick={onNew} style={btn}>새 프로젝트</button>
      <select onChange={(e) => onSelect(e.target.value)} style={{ background: "#11161d", color: "#d7dde6", border: "1px solid #283244", borderRadius: 6, padding: 6 }}>
        <option>프로젝트 선택...</option>
        {projects.map((p) => (
          <option key={p.id} value={p.id}>{p.name}</option>
        ))}
      </select>
      <div style={{ flex: 1 }} />
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

