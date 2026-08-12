"""docs/35 설계 화면 전부를 Playwright로 직접 조작해 검증한다.
서버는 미리 test-fixtures 데이터로 떠 있어야 한다(web/README.md 참조)."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8420"
SHOT_DIR = Path(__file__).parent / "test-screenshots"
SHOT_DIR.mkdir(exist_ok=True)

PAGES = [
    ("home", "/"),
    ("candidates", "/candidates"),
    ("segments", "/segments"),
    ("contacts", "/contacts"),
    ("approvals", "/approvals"),
    ("sent", "/sent"),
    ("replies", "/replies"),
    ("scores", "/scores"),
    ("queue", "/queue"),
    ("aggregation", "/aggregation"),
    ("qna", "/qna"),
]

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)
        print(f"FAIL: {msg}")
    else:
        print(f"ok: {msg}")


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        console_errors = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(str(e)))

        for name, path in PAGES:
            page.goto(BASE + path, wait_until="networkidle")
            check(page.title() != "", f"{name}: 타이틀 존재")
            body_text = page.inner_text("body")
            check("Traceback" not in body_text and "Internal Server Error" not in body_text,
                  f"{name}: 서버 에러 없음")
            page.screenshot(path=str(SHOT_DIR / f"{name}.png"), full_page=True)

        check(len(console_errors) == 0, f"콘솔 에러 없음 (실제: {console_errors})")

        # ---- 연락처 현황: 기업이 직접 요구한 화면, 데이터 실제로 있는지 ----
        page.goto(BASE + "/contacts", wait_until="networkidle")
        check("ingni-store-com" in page.inner_text("body"), "연락처 현황: 실데이터 렌더링")
        check("customer@ingni.com" in page.inner_text("body"), "연락처 현황: 연락처 값 표시")

        # ---- 승인 대기함: 실제 클릭으로 승인 플로우 ----
        page.goto(BASE + "/approvals", wait_until="networkidle")
        check(page.locator(".approval-item").count() >= 1, "승인 대기함: 항목 렌더링")
        approve_btn = page.locator(".approval-item .btn.approve").first
        check(approve_btn.is_visible(), "승인 대기함: 승인 버튼 노출")
        approve_btn.click()
        page.wait_for_timeout(1200)  # fetch + reload
        page.wait_for_load_state("networkidle")
        body_after = page.inner_text("body")
        check("승인" in body_after, "승인 대기함: 승인 후 상태 반영")

        # 실제 파일에 반영됐는지 직접 확인
        fixture = Path(__file__).parent / "test-fixtures/발송대기/S1-2026-08-06.md"
        content = fixture.read_text(encoding="utf-8")
        check("| 승인 / 거부 | 승인 |" in content, "승인 대기함: 파일에 실제로 기록됨")
        check((Path(__file__).parent / "test-fixtures/_dispatch.log").exists(),
              "승인 대기함: 발송 트리거 로그 생성됨")

        # ---- G12 챗봇 ----
        page.goto(BASE + "/qna", wait_until="networkidle")
        page.fill("#chat-input", "후보 순위 어떻게 돼")
        page.click("#chat-form button")
        page.wait_for_timeout(800)
        chat_log = page.inner_text("#chat-log")
        check("후보 순위" in chat_log, "G12: 질문이 로그에 표시됨")
        check(len(chat_log) > len("후보 순위 어떻게 돼"), "G12: 답변이 표시됨")
        page.screenshot(path=str(SHOT_DIR / "qna_after_ask.png"), full_page=True)

        # ---- 상세(원문) 보기 ----
        page.goto(BASE + "/candidates", wait_until="networkidle")
        page.goto(BASE + "/contacts", wait_until="networkidle")
        page.click(".detail-link")
        page.wait_for_load_state("networkidle")
        check("연락처 확보 결과" in page.inner_text("body") or "ingni-store-com" in page.inner_text("body"),
              "상세 보기: 원문 렌더링")
        page.screenshot(path=str(SHOT_DIR / "detail.png"), full_page=True)

        browser.close()

    print(f"\n총 {len(failures)}개 실패")
    for f in failures:
        print(" -", f)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(run())
