"use client";
import useStore from "../lib/store";
import { useMemo, useRef } from "react";

export default function AssetPanel() {
  const backend = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const { project, setProject, selectedAssetId, setSelectedAssetId, updateProject } = useStore();
  const fileRef = useRef<HTMLInputElement>(null);

  const upload = async (file: File) => {
    if (!project?.id) return;
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`${backend}/projects/${project.id}/assets/upload`, { method: "POST", body: fd });
      if (!res.ok) throw new Error();
      // Reload project from backend to reflect new assets
      const res2 = await fetch(`${backend}/projects/${project.id}`);
      if (res2.ok) setProject(await res2.json());
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

  const assetEntries = useMemo(() => Object.entries(project?.assets || {}), [project]);
  const assetUrl = (id: string) => `${backend}/projects/${project?.id}/assets/${id}`;

  const removeAsset = async (id: string) => {
    if (!project) return;
    const ok = confirm("이 에셋을 삭제하시겠습니까? (타임라인의 참조는 수동으로 정리 필요)");
    if (!ok) return;
    const np: any = { ...project, assets: { ...project.assets } };
    delete np.assets[id];
    setProject(np);
    try { await updateProject(backend, np); } catch {}
    if (selectedAssetId === id) setSelectedAssetId(undefined);
  };

  return (
    <div style={{ border: "1px solid #1e242d", borderRadius: 8, padding: 8, background: "#0f1318" }}>
      <div style={{ display: "flex", gap: 8 }}>
        <button onClick={() => fileRef.current?.click()} style={btn}>업로드</button>
        <button onClick={handleCaptureFromUrl} style={btn}>URL 스크롤 가져오기</button>
        <input ref={fileRef} type="file" hidden onChange={(e) => e.target.files && upload(e.target.files[0])} />
      </div>
      <div style={{ marginTop: 8, display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 6, maxHeight: 520, overflow: "auto" }}>
        {assetEntries.map(([id, path]) => {
          const sel = selectedAssetId === id;
          return (
            <div key={id} style={{ border: sel ? "1px solid #1f6feb" : "1px solid #283244", background: "#0b0f14", borderRadius: 6, padding: 6 }}>
              <div onClick={() => setSelectedAssetId(id)} style={{ cursor: "pointer", marginBottom: 6 }}>
                <img src={assetUrl(id)} alt={path.split("/").slice(-1)[0]} style={{ width: "100%", height: 120, objectFit: "cover", borderRadius: 4, display: "block", background: "#0b0f14" }} />
              </div>
              <div style={{ fontSize: 11, color: "#9fb1c9", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{path.split("/").slice(-1)[0]}</div>
              <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                <a href={assetUrl(id)} target="_blank" rel="noreferrer" style={{ ...btn, display: "inline-block", textAlign: "center", textDecoration: "none" }}>보기</a>
                <button onClick={() => setSelectedAssetId(id)} style={btn}>선택</button>
                <button onClick={() => removeAsset(id)} style={{ ...btn, borderColor: "#72323a", background: "#2a1316", color: "#ffb4b4" }}>삭제</button>
              </div>
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
