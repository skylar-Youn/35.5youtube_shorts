"use client";
import useStore from "../lib/store";
import { useRef } from "react";

export default function AssetPanel() {
  const backend = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const { project, setProject } = useStore();
  const fileRef = useRef<HTMLInputElement>(null);

  const upload = async (file: File) => {
    if (!project?.id) return;
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${backend}/projects/${project.id}/assets/upload`, { method: "POST", body: fd });
      if (!res.ok) throw new Error();
      const res2 = await fetch(`${backend}/projects/${project.id}`);
      setProject(await res2.json());
    } catch {
      alert("업로드 실패. 서버 상태를 확인하세요.");
    }
  };

  const handleCaptureFromUrl = async () => {
    const url = prompt("이미지 가져올 URL", "");
    if (!url || !project?.id) return;
    try {
      const res = await fetch(`${backend}/scroll/capture`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) });
      if (!res.ok) throw new Error();
      const data = await res.json();
      if (data?.urls?.length) {
        await fetch(`${backend}/projects/${project.id}/ingest_urls`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ urls: data.urls }) });
        const res2 = await fetch(`${backend}/projects/${project.id}`);
        setProject(await res2.json());
        alert(`가져온 이미지: ${data.urls.length}개`);
      } else {
        alert("이미지를 찾지 못했습니다.");
      }
    } catch {
      alert("URL 캡처 실패. 서버와 Playwright 설정을 확인하세요.");
    }
  };

  return (
    <div style={{ border: "1px solid #1e242d", borderRadius: 8, padding: 8, background: "#0f1318" }}>
      <div style={{ display: "flex", gap: 8 }}>
        <button onClick={() => fileRef.current?.click()} style={btn}>업로드</button>
        <button onClick={handleCaptureFromUrl} style={btn}>URL 스크롤 가져오기</button>
        <input ref={fileRef} type="file" hidden onChange={(e) => e.target.files && upload(e.target.files[0])} />
      </div>
      <div style={{ marginTop: 8, display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 6, maxHeight: 520, overflow: "auto" }}>
        {Object.entries(project?.assets || {}).map(([id, path]) => (
          <div key={id} style={{ border: "1px solid #283244", background: "#0b0f14", borderRadius: 6, padding: 4 }}>
            <div style={{ fontSize: 11, color: "#9fb1c9", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{id}</div>
            <div style={{ fontSize: 10, color: "#64748b" }}>{path.split("/").slice(-1)[0]}</div>
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
