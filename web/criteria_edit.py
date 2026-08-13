"""기준 카드 웹 편집 (docs/35_웹_대시보드_설계.md 6절, 2026-08-14 설계 반영).

흐름은 두 단계로 나뉜다 — 절대 한 번에 파일을 고치지 않는다:
  1. propose_edit — 사람의 자연어 요청을 받아 LLM이 "이렇게 바꾸면 됩니다"라는
     제안(변경 전/변경 후 diff)만 만든다. 이 단계는 파일을 쓰지 않는다
     — `--disallowedTools`로 Write류를 실제로 막는다(프롬프트 지침만으로는
     안 된다: docs/90 리스크 62가 이미 확인했듯 이 환경의 무인 실행에서
     Write/Edit은 승인 없이 그냥 동작한다 — "쓰지 말라"는 말만 믿는 건
     CLAUDE.md가 경계하는 거짓 안전장치와 같은 종류다).
  2. apply_edit — 사람이 화면에서 그 제안을 확인하고 "적용"을 눌렀을 때만
     실제로 파일을 고친다. 이건 LLM 호출이 아니라 평범한 텍스트 치환이다
     (제안 단계에서 이미 정확한 old/new 문자열을 받았으므로 다시 LLM에게
     맡길 이유가 없다). 쓰기 직후 이 함수가 직접 G12 검토를 호출한다 —
     H9(Claude Code 자체 PostToolUse 훅)에 기대지 않는다. 이 화면의 파일
     쓰기는 웹 서버 프로세스가 직접 하는 것이라 Claude Code의 Edit 도구를
     거치지 않고, 그래서 H9가 걸린다는 보장이 없다(H9는 Claude Code 안에서
     편집할 때만 작동하는 것으로 이미 확인돼 있다, `Harness/hook/h09-*.md`).
     대신 H9와 완전히 같은 질문 템플릿을 그대로 재사용해 호출하므로,
     결과 로그는 기존 `is_h9_origin`/`h9_target_file` 판별에 그대로 잡히고
     기준 카드 화면에 똑같이 뜬다 — 새 스키마를 만들지 않는다.
"""
import os
import re
import subprocess

from data_source import read_criteria, write_criteria, criteria_root

_PROPOSE_TEMPLATE = """다음은 `기준/{file}` 파일의 현재 전체 내용이다.

---
{content}
---

사용자 수정 요청: "{instruction}"

이 요청대로 위 파일에서 정확히 어느 부분을 어떻게 바꿔야 하는지 제안해라.
**파일을 직접 쓰거나 고치지 마라 — 이건 제안 단계이고, 실제 적용은 사람이 화면에서 확인한 뒤 별도로 한다.**

아래 형식으로만 답해라(다른 설명을 앞뒤에 붙이지 마라):

[변경 전]
(원문에서 정확히 그대로 가져온 텍스트 — 파일 안에서 이 문자열이 정확히 한 번만 나타나야 한다. 수정 대상 부분만, 필요하면 앞뒤 맥락을 조금 포함해라)

[변경 후]
(요청대로 고친 텍스트)

[설명]
(무엇을 왜 이렇게 바꿨는지 한 줄)

요청이 모호하거나 원문에서 대상을 하나로 특정할 수 없으면 위 형식 대신 다음처럼만 답해라:

[불가]
(이유)
"""


def _dispatch_mode() -> str:
    return os.environ.get("DISPATCH_MODE", "mock")


def propose_edit(file: str, instruction: str) -> dict:
    current = read_criteria(file)
    if not current:
        return {"ok": False, "error": f"{file} 파일을 찾을 수 없음"}
    if not instruction.strip():
        return {"ok": False, "error": "수정 요청이 비어 있음"}

    mode = _dispatch_mode()
    if mode not in ("real", "resend"):
        return {
            "ok": True, "mock": True,
            "old": "(mock) 실제 환경(DISPATCH_MODE=real)에서는 요청에 맞는 원문 일부가 여기 뜹니다.",
            "new": f"(mock) 요청 반영 결과 미리보기: {instruction}",
            "explanation": "지금은 mock 모드입니다 — LLM을 호출하지 않았습니다.",
        }

    prompt = _PROPOSE_TEMPLATE.format(file=file, content=current, instruction=instruction)
    try:
        # `--disallowedTools <tools...>`는 가변 인자라 공백으로 띄워 쓰면 뒤따르는
        # prompt 인자까지 도구 이름으로 집어삼킨다("Input must be provided..." 오류로
        # 실물 확인, 2026-08-14) — `--flag=값` 한 토큰으로 묶어야 프롬프트가 온전히
        # 남는다.
        #
        # PowerShell·Agent도 함께 막는다(2026-08-14 change-reviewer 지적) — 이
        # 저장소의 스킬 12개 전부가 Bash 하나만으로는 안 되고 PowerShell·Agent까지
        # 막아야 우회가 안 닫힌다는 걸 이미 판례로 남겨 뒀다(`g10-재수집판단/SKILL.md`
        # "Agent도 함께 닫아 웹 권한이 있는 다른 실행체에 우회 위임하지 못하게
        # 했다"). 이 호출은 스킬을 거치지 않고 맨 프롬프트를 던지는 유일한 자리라
        # SKILL.md frontmatter의 방어를 못 받는다 — CLI 플래그가 그 frontmatter와
        # 최소한 같은 목록을 막아야 한다.
        proc = subprocess.run(
            ["claude", "-p",
             "--disallowedTools=Write,Edit,MultiEdit,NotebookEdit,Bash,PowerShell,Agent", prompt],
            cwd=str(criteria_root().parent), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=180,
        )
        raw = proc.stdout or proc.stderr
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"제안 생성 실패: {e}"}
    return _parse_proposal(raw)


def _parse_proposal(raw: str) -> dict:
    if "[변경 전]" not in raw:
        m_fail = re.search(r"\[불가\]\s*\n(.+)", raw, re.S)
        if m_fail:
            return {"ok": False, "error": m_fail.group(1).strip()}
        return {"ok": False, "error": f"제안 형식을 해석하지 못함 — 응답: {raw[:300]}"}

    m_old = re.search(r"\[변경 전\]\s*\n(.*?)\n\[변경 후\]", raw, re.S)
    m_new = re.search(r"\[변경 후\]\s*\n(.*?)\n\[설명\]", raw, re.S)
    m_exp = re.search(r"\[설명\]\s*\n(.*)", raw, re.S)
    if not (m_old and m_new):
        return {"ok": False, "error": f"제안 형식을 해석하지 못함 — 응답: {raw[:300]}"}
    return {
        "ok": True,
        "old": m_old.group(1).strip("\n"),
        "new": m_new.group(1).strip("\n"),
        "explanation": (m_exp.group(1).strip() if m_exp else ""),
    }


def apply_edit(file: str, old: str, new: str) -> dict:
    current = read_criteria(file)
    if not current:
        return {"ok": False, "error": f"{file} 파일을 찾을 수 없음"}

    count = current.count(old)
    if count == 0:
        return {"ok": False, "error": "제안된 원문을 파일에서 찾지 못했습니다 — 그 사이 파일이 바뀌었을 수 있습니다. 다시 제안받아 주세요."}
    if count > 1:
        return {"ok": False, "error": f"제안된 원문이 파일에 {count}번 나타나 어느 곳인지 특정할 수 없습니다. 더 구체적으로 다시 제안받아 주세요."}

    updated = current.replace(old, new, 1)
    write_criteria(file, updated)
    review = _trigger_review(file, old, new)
    return {"ok": True, "review": review}


def _trigger_review(file: str, old: str, new: str) -> dict:
    """H9가 쓰는 것과 완전히 같은 질문 템플릿(`hook_h9_criteria_review.sh` 참조)을
    재사용한다 — 그래야 `parsers.is_h9_origin`·`h9_target_file`이 이 검토 결과도
    똑같이 기준 카드에 잡아 보여준다(새 판별 로직을 만들지 않는다)."""
    question = (
        f"{file}의 내용이 다음과 같이 바뀌었다.\n"
        f"[변경 전]\n{old}\n[변경 후]\n{new}\n"
        f"이 변경이 다른 기준·스펙과 충돌하는지 검토해줘."
    )
    mode = _dispatch_mode()
    if mode not in ("real", "resend"):
        return {"status": "mock", "reason": "DISPATCH_MODE=real(또는 resend)로 켜야 실제 검토가 돕니다."}
    try:
        subprocess.Popen(["claude", "-p", f"/g12-질의응답 {question}"], cwd=str(criteria_root().parent))
        return {"status": "processing", "reason": "검토가 백그라운드로 시작됐습니다 — 잠시 후 새로고침하면 이 카드에 결과가 뜹니다."}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "reason": f"검토 호출 실패: {e}"}
