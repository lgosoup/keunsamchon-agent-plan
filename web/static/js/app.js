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
  const actionButtons = panel.querySelectorAll(".btn.approve, .btn.reject");
  actionButtons.forEach((b) => (b.disabled = true));
  const resultEl = panel.querySelector(".action-result");
  resultEl.classList.add("pending");
  resultEl.textContent = "처리 중...";
  try {
    const body = new URLSearchParams({ file, company_id: company, decision, reason });
    const res = await fetch("/approvals/decide", { method: "POST", body });
    const data = await res.json();
    resultEl.classList.remove("pending");
    if (data.ok) {
      const d = data.dispatch;
      if (d && d.mode === "resend") {
        // 실제 메일이 나가는 유일한 모드 — 결과를 요약하지 않고 그대로 보여준다.
        if (d.status === "sent") {
          resultEl.innerHTML =
            `<span class="send-ok">✓ ${decision} 처리 + <strong>실제 발송 완료</strong></span>` +
            `<div class="send-detail">수신: <code>${d.to_actual}</code>` +
            (d.to_original ? ` <em>(원래 수신자 <code>${d.to_original}</code> 대신 데모 주소로 치환됨)</em>` : "") +
            `<br>message_id: <code>${d.message_id}</code></div>`;
        } else {
          resultEl.innerHTML =
            `<span class="send-fail">⚠ ${decision}은 기록됐으나 <strong>발송 실패</strong></span>` +
            `<div class="send-detail">${d.reason || "알 수 없는 오류"}</div>`;
        }
        return; // 결과를 읽을 시간을 준다 — 자동 새로고침하지 않는다
      }
      resultEl.textContent = `완료 — ${decision} 처리됨` + (d ? ` (발송 트리거: ${d.mode} 모드)` : "");
      setTimeout(() => location.reload(), 900);
    } else {
      resultEl.textContent = `오류: ${data.error || "알 수 없는 오류"}`;
      actionButtons.forEach((b) => (b.disabled = false));
    }
  } catch (err) {
    resultEl.classList.remove("pending");
    resultEl.textContent = `오류: ${err}`;
    actionButtons.forEach((b) => (b.disabled = false));
  }
});

const chatForm = document.getElementById("chat-form");
if (chatForm) {
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("chat-input");
    const q = input.value.trim();
    if (!q) return;
    const submitBtn = chatForm.querySelector("button[type=submit]");
    const log = document.getElementById("chat-log");
    log.insertAdjacentHTML("beforeend", `<div class="msg user">${q}</div>`);
    input.value = "";
    submitBtn.disabled = true;
    const thinkingId = `thinking-${Date.now()}`;
    log.insertAdjacentHTML("beforeend", `<div class="msg bot" id="${thinkingId}">…</div>`);
    log.scrollTop = log.scrollHeight;
    try {
      const body = new URLSearchParams({ question: q });
      const res = await fetch("/qna/ask", { method: "POST", body });
      if (!res.ok) throw new Error(`서버 오류 (${res.status})`);
      const data = await res.json();
      document.getElementById(thinkingId).textContent = data.answer;
    } catch (err) {
      document.getElementById(thinkingId).textContent = `⚠ 답변을 받지 못했습니다 (${err}).`;
    } finally {
      submitBtn.disabled = false;
      log.scrollTop = log.scrollHeight;
    }
  });
}
