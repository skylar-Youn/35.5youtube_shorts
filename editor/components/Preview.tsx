"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import useStore from "../lib/store";

export default function Preview() {
  const { project } = useStore();
  const W = project?.width || 1080;
  const H = project?.height || 1920;

  // Measure available space and fit the preview while keeping aspect ratio.
  const hostRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<{ w: number; h: number }>({ w: 270, h: 480 });

  const ratio = useMemo(() => (W > 0 && H > 0 ? W / H : 9 / 16), [W, H]);

  useEffect(() => {
    const el = hostRef.current;
    if (!el) return;
    const ro = new (window as any).ResizeObserver((entries: any[]) => {
      const cr = entries[0]?.contentRect;
      if (!cr) return;
      const maxW = Math.max(0, cr.width - 2); // padding/border safety
      const maxH = Math.max(0, cr.height - 2);
      if (maxW <= 0 || maxH <= 0) return;
      const containerRatio = maxW / maxH;
      if (containerRatio > ratio) {
        // container is wider than video
        const h = Math.floor(maxH);
        const w = Math.floor(h * ratio);
        setSize({ w, h });
      } else {
        const w = Math.floor(maxW);
        const h = Math.floor(w / ratio);
        setSize({ w, h });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [ratio]);

  return (
    <div ref={hostRef} style={{ border: "1px solid #1e242d", borderRadius: 8, padding: 8, background: "#0f1318", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
      <div style={{ width: size.w, height: size.h, background: "#0b0f14", border: "1px solid #283244", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", color: "#64748b" }}>
        {project ? (
          <div style={{ textAlign: "center", fontSize: 12 }}>
            <div>{project.name}</div>
            <div>
              {W}x{H}, {project.fps}fps
            </div>
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
