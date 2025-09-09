"use client";
import useStore from "../lib/store";

export default function Preview() {
  const { project } = useStore();
  const W = project?.width || 1080;
  const H = project?.height || 1920;
  return (
    <div style={{ border: "1px solid #1e242d", borderRadius: 8, padding: 8, background: "#0f1318", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ width: 270, height: 480, background: "#0b0f14", border: "1px solid #283244", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", color: "#64748b" }}>
        {project ? (
          <div style={{ textAlign: "center", fontSize: 12 }}>
            <div>{project.name}</div>
            <div>{W}x{H}, {project.fps}fps</div>
            <div>길이 {project.duration}s</div>
            <div style={{ marginTop: 6 }}>타임라인 저장 후 렌더하세요</div>
          </div>
        ) : (
          <div>프로젝트를 선택하세요</div>
        )}
      </div>
    </div>
  );
}

