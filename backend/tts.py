from __future__ import annotations
import os

def synthesize(text: str, out_path: str, backend: str = "auto", edge_voice: str = "ko-KR-SunHiNeural", rate_pct: int = 0) -> str | None:
    text = (text or "").strip()
    if not text:
        return None
    backend = (backend or "auto").lower()

    def _edge() -> str | None:
        try:
            import asyncio
            import edge_tts  # type: ignore

            async def _run():
                comm = edge_tts.Communicate(text, voice=edge_voice, rate=f"{int(rate_pct):+d}%")
                await comm.save(out_path)

            try:
                asyncio.run(_run())
            except RuntimeError:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(_run())
            return out_path
        except Exception:
            return None

    def _pyttsx3() -> str | None:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 185)
            # try to pick korean voice
            for v in engine.getProperty("voices"):
                name = (getattr(v, "name", "") or "").lower()
                langs = (getattr(v, "languages", []) or [])
                if "ko" in str(langs).lower() or "korean" in name:
                    engine.setProperty("voice", v.id)
                    break
            engine.save_to_file(text, out_path)
            engine.runAndWait()
            return out_path
        except Exception:
            return None

    if backend in ("auto", "edge-tts"):
        return _edge() or _pyttsx3()
    if backend == "pyttsx3":
        return _pyttsx3()
    return None

