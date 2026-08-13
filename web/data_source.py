"""데이터 소스 접근 — specs/(또는 test-fixtures/) 아래 마크다운 파일을 읽고 쓴다.
docs/35_웹_대시보드_설계.md 6절: DB 없이 파일을 직접 읽는다."""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """저장소 루트 .env에서 아직 설정되지 않은 값만 채운다.

    이미 환경변수로 들어온 값은 덮어쓰지 않는다(셸에서 넘긴 쪽이 이긴다).
    `Harness/api/resend_send_api.py`와 같은 방식이며, 값을 출력하지 않는다
    (root CLAUDE.md 6절). 이게 없으면 DISPATCH_MODE=resend일 때 발송에 필요한
    DEMO_RECIPIENT를 셸에서 매번 넘겨야 한다."""
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip().strip('"').strip("'")
    except OSError:
        pass


_load_dotenv()


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


def criteria_root() -> Path:
    """`기준/`은 `specs/`의 하위가 아니라 저장소 루트의 형제 디렉터리라
    `data_root()`(→ `_safe_path`)로는 못 읽는다. `data_root()` 자체를 저장소
    루트로 넓히면 `.env` 등도 다시 열려버려(project-critic 2026-08-13 지적으로
    막아 둔 것), `기준/` 하나만을 위한 별도의 좁은 루트를 둔다(docs/35 6-1절)."""
    return REPO_ROOT / "기준"


def _safe_criteria_path(relpath: str) -> Path:
    root = criteria_root().resolve()
    p = (root / relpath).resolve()
    if not (p == root or root in p.parents):
        raise ValueError(f"criteria_root() 밖 경로 접근 거부: {relpath}")
    return p


def read_criteria(relpath: str) -> str:
    try:
        p = _safe_criteria_path(relpath)
    except ValueError:
        return ""
    if not p.is_file():
        # `relpath=""` 등으로 criteria_root() 자체(디렉터리)를 가리키면
        # exists()는 참이지만 read_text()가 IsADirectoryError를 던진다
        # (2026-08-14 change-reviewer 지적 — 정상 UI 흐름에서는 안 걸리지만
        # API를 직접 두드리면 발생 가능한 처리되지 않은 500 예외였다).
        return ""
    return p.read_text(encoding="utf-8")


def write_criteria(relpath: str, content: str) -> None:
    """기준 카드 웹 편집(docs/35 6절)의 유일한 쓰기 경로 — 반드시 `_safe_criteria_path`를
    거쳐 `기준/` 밖으로 못 나간다. 파일 존재를 전제한다(이 화면은 기존 카드 수정만
    다룬다 — 새 기준 파일 생성은 범위 밖, `기준/` 아래 새 하위 폴더도 만들지 않는다)."""
    p = _safe_criteria_path(relpath)
    if not p.is_file():
        raise ValueError(f"존재하지 않는 기준 파일에는 쓰지 않음: {relpath}")
    p.write_text(content, encoding="utf-8")


def list_criteria_md_files():
    """`README.md`는 판정 기준 카드가 아니라 `기준/` 디렉터리 자체의 안내문이라 뺀다
    (`기준/README.md` 머리: "여기 있는 것은 손잡이다" — 판정 값·문장이 아닌 디렉터리 설명)."""
    base = criteria_root()
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.glob("*.md") if p.name != "README.md")


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
