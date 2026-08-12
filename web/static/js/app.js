// 승인 대기함 액션 + G12 채팅 — 서버 API를 순수 fetch로만 호출한다.
document.addEventListener("click", async (e) => {
  const btn = e.target.closest(".btn.approve, .btn.reject");
  if (!btn) return;
  const panel = btn.closest(".approval-item");
  const file = panel.dataset.file;
  const company = panel.dataset.company;
  const decision = btn.dataset.decision;
  let reason = "";
  if (decision === "거부") {
    reason = prompt("거부 사유를 입력하세요 (선택):", "") || "";
  }
  const resultEl = panel.querySelector(".action-result");
  resultEl.textContent = "처리 중...";
  const body = new URLSearchParams({ file, company_id: company, decision, reason });
  const res = await fetch("/approvals/decide", { method: "POST", body });
  const data = await res.json();
  if (data.ok) {
    resultEl.textContent = `완료 — ${decision} 처리됨` + (data.dispatch ? ` (발송 트리거: ${data.dispatch.mode} 모드)` : "");
    setTimeout(() => location.reload(), 900);
  } else {
    resultEl.textContent = `오류: ${data.error || "알 수 없는 오류"}`;
  }
});

const chatForm = document.getElementById("chat-form");
if (chatForm) {
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("chat-input");
    const q = input.value.trim();
    if (!q) return;
    const log = document.getElementById("chat-log");
    log.insertAdjacentHTML("beforeend", `<div class="msg user">${q}</div>`);
    input.value = "";
    const body = new URLSearchParams({ question: q });
    const res = await fetch("/qna/ask", { method: "POST", body });
    const data = await res.json();
    log.insertAdjacentHTML("beforeend", `<div class="msg bot">${data.answer}</div>`);
    log.scrollTop = log.scrollHeight;
  });
}
