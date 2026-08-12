"""데이터 소스 접근 — specs/(또는 test-fixtures/) 아래 마크다운 파일을 읽고 쓴다.
docs/35_웹_대시보드_설계.md 6절: DB 없이 파일을 직접 읽는다."""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def data_root() -> Path:
    override = os.environ.get("DASHBOARD_DATA_ROOT")
    if override:
        return Path(override)
    return REPO_ROOT / "specs"


def _safe_path(relpath: str) -> Path:
    """data_root() 밖으로 못 나가게 막는다 — relpath에 '..'가 섞여 들어오면
    (예: /detail?path=../../.env) 저장소 루트의 비공개 파일(.env 등)을 읽을 수
    있었다(project-critic 2026-08-13 지적, CLAUDE.md 6절 위반)."""
    root = data_root().resolve()
    p = (root / relpath).resolve()
    if not (p == root or root in p.parents):
        raise ValueError(f"data_root() 밖 경로 접근 거부: {relpath}")
    return p


def read_text(relpath: str) -> str:
    try:
        p = _safe_path(relpath)
    except ValueError:
        return ""
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def write_text(relpath: str, content: str) -> None:
    p = _safe_path(relpath)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def list_md_files(subdir: str, exclude_dirs=()):
    base = data_root() / subdir
    if not base.exists():
        return []
    out = []
    for p in sorted(base.rglob("*.md")):
        rel = p.relative_to(data_root())
        if any(part in exclude_dirs for part in rel.parts):
            continue
        out.append(rel.as_posix())
    return out
