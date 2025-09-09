"use client";
import { useEffect, useMemo, useState } from "react";
import useStore from "../lib/store";
import TopBar from "../components/TopBar";
import AssetPanel from "../components/AssetPanel";
import Timeline from "../components/Timeline";
import Preview from "../components/Preview";
import Properties from "../components/Properties";
import ScriptEditor from "../components/ScriptEditor";

export default function Page() {
  const backend = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const { project, setProject, createProject, loadProjectList } = useStore();
  const [projects, setProjects] = useState<any[]>([]);

  useEffect(() => {
    loadProjectList(backend).then(setProjects);
  }, [backend, loadProjectList]);

  const handleNewProject = async () => {
    const name = prompt("새 프로젝트 이름", "My Project");
    if (!name) return;
    const p = await createProject(backend, name);
    setProject(p);
    const list = await loadProjectList(backend);
    setProjects(list);
  };

  return (
    <div style={{ display: "grid", gridTemplateRows: "48px 1fr", height: "100vh" }}>
      <TopBar onNew={handleNewProject} projects={projects} onSelect={async (id) => {
        const res = await fetch(`${backend}/projects/${id}`);
        const data = await res.json();
        setProject(data);
      }} onRender={async () => {
        if (!project?.id) return;
        const res = await fetch(`${backend}/render`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project_id: project.id }) });
        const data = await res.json();
        alert(data?.path ? `렌더 완료: ${data.path}` : "렌더 실패");
      }} />
      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr 320px", gap: 8, padding: 8 }}>
        <AssetPanel />
        <div style={{ display: "grid", gridTemplateRows: "1fr 240px", gap: 8 }}>
          <Preview />
          <Timeline />
        </div>
        <div style={{ display: "grid", gridTemplateRows: "1fr 1fr", gap: 8 }}>
          <Properties />
          <ScriptEditor />
        </div>
      </div>
    </div>
  );
}

