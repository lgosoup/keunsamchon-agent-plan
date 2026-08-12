"""큰삼촌컴퍼니 대시보드 — docs/35_웹_대시보드_설계.md 구현.
실행: python web/app.py  (환경변수 DASHBOARD_DATA_ROOT, DISPATCH_MODE로 조정)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
import uvicorn

import parsers
import dispatch
from data_source import read_text, data_root

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


async def home(request):
    return templates.TemplateResponse(request, "home.html", {"counts": parsers.overview_counts()})


async def candidates(request):
    return templates.TemplateResponse(request, "candidates.html", {
        "items": parsers.parse_candidates(), "holdlist": parsers.parse_holdlist(),
    })


async def segments(request):
    return templates.TemplateResponse(request, "segments.html", {"segments": parsers.parse_segments()})


async def contacts(request):
    return templates.TemplateResponse(request, "contacts.html", {"items": parsers.parse_contacts()})


async def approvals_view(request):
    return templates.TemplateResponse(request, "approvals.html", {"items": parsers.parse_approvals()})


async def approvals_decide(request):
    import os
    form = await request.form()
    file_rel = form.get("file")
    company_id = form.get("company_id")
    decision = form.get("decision")
    reason = form.get("reason", "")
    # 승인자를 항상 문자열 "담당자"로 남기던 것을 정정(project-critic 2026-08-13
    # 지적) — 화면에 로그인이 없어 클릭한 사람을 특정할 수는 없지만, 최소한
    # 이 서버를 띄운 담당자 이름은 환경변수로 남길 수 있게 한다.
    approver = os.environ.get("DASHBOARD_OPERATOR_NAME", "담당자")
    result = dispatch.decide(file_rel, company_id, decision, approver=approver, reason=reason)
    return JSONResponse(result)


async def sent(request):
    return templates.TemplateResponse(request, "sent.html", {"items": parsers.parse_sent()})


async def replies(request):
    return templates.TemplateResponse(request, "replies.html", {"items": parsers.parse_replies()})


async def scores(request):
    return templates.TemplateResponse(request, "scores.html", {"data": parsers.parse_scores()})


async def queue(request):
    return templates.TemplateResponse(request, "queue.html", {"data": parsers.parse_queue()})


async def aggregation(request):
    return templates.TemplateResponse(request, "aggregation.html", {"items": parsers.parse_aggregation()})


async def qna_page(request):
    return templates.TemplateResponse(request, "qna.html", {"logs": _qna_logs()})


def _qna_logs():
    from data_source import list_md_files
    out = []
    for rel in list_md_files("질의응답로그"):
        raw = read_text(rel)
        out.append({"file": rel, "raw": raw, "html": parsers.render_markdown(raw)})
    return list(reversed(out))


async def qna_ask(request):
    """G12(질의응답) 호출 — mock 모드에서는 로그만 남기고 안내 문구를 돌려준다.
    실제 모드는 dispatch.py와 같은 전환 원칙: DISPATCH_MODE=real이면 claude -p 호출."""
    import os
    form = await request.form()
    question = form.get("question", "")
    mode = os.environ.get("DISPATCH_MODE", "mock")
    if mode == "real":
        import subprocess
        try:
            proc = subprocess.run(
                ["claude", "-p", f"/g12-질의응답 {question}"],
                cwd=str(data_root().parent), capture_output=True, text=True, timeout=120,
            )
            answer = proc.stdout or proc.stderr
        except Exception as e:  # noqa: BLE001
            answer = f"(실제 호출 실패: {e})"
    else:
        answer = (
            "(mock) 실제 환경에서는 /g12-질의응답 스킬이 G1~G11 산출물을 조회해 답합니다. "
            f"질문: “{question}” — 지금은 DISPATCH_MODE=real로 켜야 실제로 조회합니다."
        )
    return JSONResponse({"answer": answer})


async def detail(request):
    rel = request.query_params.get("path", "")
    raw = read_text(rel)
    return templates.TemplateResponse(request, "detail.html", {
        "path": rel, "html": parsers.render_markdown(raw) if raw else "<p>(파일 없음)</p>",
    })


async def healthz(request):
    return PlainTextResponse("ok")


routes = [
    Route("/", home),
    Route("/candidates", candidates),
    Route("/segments", segments),
    Route("/contacts", contacts),
    Route("/approvals", approvals_view),
    Route("/approvals/decide", approvals_decide, methods=["POST"]),
    Route("/sent", sent),
    Route("/replies", replies),
    Route("/scores", scores),
    Route("/queue", queue),
    Route("/aggregation", aggregation),
    Route("/qna", qna_page),
    Route("/qna/ask", qna_ask, methods=["POST"]),
    Route("/detail", detail),
    Route("/healthz", healthz),
    Mount("/static", app=StaticFiles(directory=str(Path(__file__).parent / "static")), name="static"),
]

app = Starlette(routes=routes)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8420)
