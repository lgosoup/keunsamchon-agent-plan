// 승인 대기함 액션 + G12 채팅 — 서버 API를 순수 fetch로만 호출한다.

function renderResendResult(resultEl, decision, d) {
  resultEl.textContent = "";
  const line1 = document.createElement("span");
  const line2 = document.createElement("div");
  line2.className = "send-detail";
  if (d.status === "sent") {
    line1.className = "send-ok";
    line1.textContent = `✓ ${decision} 처리 + 실제 발송 완료`;
    const toLine = document.createElement("div");
    toLine.append("수신: ", document.createElement("code"));
    toLine.querySelector("code").textContent = d.to_actual || "";
    if (d.to_original) {
      const em = document.createElement("em");
      em.textContent = ` (원래 수신자 ${d.to_original} 대신 데모 주소로 치환됨)`;
      toLine.append(em);
    }
    const midLine = document.createElement("div");
    midLine.append("message_id: ");
    const code = document.createElement("code");
    code.textContent = d.message_id || "";
    midLine.append(code);
    line2.append(toLine, midLine);
  } else {
    line1.className = "send-fail";
    line1.textContent = `⚠ ${decision}은 기록됐으나 발송되지 않음 (${d.status || "오류"})`;
    line2.textContent = d.reason || "알 수 없는 오류";
  }
  resultEl.append(line1, line2);
}

function pollSendStatus(companyId, file, resultEl, attempt = 0) {
  const MAX_ATTEMPTS = 30; // 4초 간격 × 30 = 최대 2분 대기
  setTimeout(async () => {
    try {
      const params = new URLSearchParams({ company_id: companyId, file });
      const res = await fetch(`/approvals/status?${params}`);
      const d = await res.json();
      if (d.status === "processing") {
        if (attempt + 1 >= MAX_ATTEMPTS) {
          resultEl.textContent = "확인 필요 — 아직 처리 중입니다. 발송 이력(/sent)에서 나중에 직접 확인하세요.";
          return;
        }
        pollSendStatus(companyId, file, resultEl, attempt + 1);
        return;
      }
      renderResendResult(resultEl, "승인", { ...d, mode: "resend" });
    } catch (err) {
      resultEl.textContent = `상태 확인 실패: ${err} — 발송 이력(/sent)에서 직접 확인하세요.`;
    }
  }, 4000);
}

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
      if (d && d.mode === "resend" && d.status === "processing") {
        // 스킬을 백그라운드로 던졌을 뿐 아직 결과가 없다 — 즉시 "완료"로 단정하지
        // 않는다(스킬 실행은 LLM 호출이라 몇 초~몇 분 걸린다). resend_watcher.py가
        // 실제 발송을 처리한 뒤에야 결과가 나오므로 폴링으로 기다린다.
        resultEl.textContent = "처리 중 — 스킬이 게이트를 확인하고 있습니다...";
        pollSendStatus(company, file, resultEl);
        return;
      }
      if (d && d.mode === "resend") {
        renderResendResult(resultEl, decision, d);
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

// ---------- 기준 카드 수정 제안 (docs/35 6절) ----------

document.addEventListener("submit", async (e) => {
  const form = e.target.closest(".criteria-propose-form");
  if (!form) return;
  e.preventDefault();
  const card = form.closest(".criteria-card");
  const file = card.dataset.file;
  const input = card.querySelector(".criteria-instruction");
  const instruction = input.value.trim();
  if (!instruction) return;

  const errorEl = card.querySelector(".criteria-propose-error");
  const proposalEl = card.querySelector(".criteria-proposal");
  errorEl.textContent = "";
  proposalEl.hidden = true;
  const submitBtn = form.querySelector("button[type=submit]");
  submitBtn.disabled = true;
  submitBtn.textContent = "제안 만드는 중...";

  try {
    const body = new URLSearchParams({ file, instruction });
    const res = await fetch("/criteria/propose", { method: "POST", body });
    const data = await res.json();
    if (!data.ok) {
      errorEl.textContent = `제안 실패: ${data.error || "알 수 없는 오류"}`;
      return;
    }
    if (data.mock) {
      errorEl.textContent = "지금은 mock 모드입니다 — DISPATCH_MODE=real(또는 resend)로 켜야 실제 제안이 만들어집니다.";
    }
    proposalEl.querySelector(".criteria-diff-old pre").textContent = data.old;
    proposalEl.querySelector(".criteria-diff-new pre").textContent = data.new;
    proposalEl.querySelector(".criteria-explanation").textContent = data.explanation || "";
    proposalEl.querySelector(".criteria-apply-result").textContent = "";
    proposalEl.dataset.old = data.old;
    proposalEl.dataset.new = data.new;
    proposalEl.hidden = false;
  } catch (err) {
    errorEl.textContent = `제안 요청 실패: ${err}`;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "수정 제안받기";
  }
});

document.addEventListener("click", async (e) => {
  const cancelBtn = e.target.closest(".criteria-proposal .cancel");
  if (cancelBtn) {
    const proposalEl = cancelBtn.closest(".criteria-proposal");
    proposalEl.hidden = true;
    return;
  }

  const applyBtn = e.target.closest(".criteria-proposal .apply");
  if (!applyBtn) return;
  const proposalEl = applyBtn.closest(".criteria-proposal");
  const card = applyBtn.closest(".criteria-card");
  const file = card.dataset.file;
  const old = proposalEl.dataset.old;
  const newText = proposalEl.dataset.new;
  const resultEl = proposalEl.querySelector(".criteria-apply-result");

  const buttons = proposalEl.querySelectorAll("button");
  buttons.forEach((b) => (b.disabled = true));
  resultEl.textContent = "적용 중...";

  try {
    const body = new URLSearchParams({ file, old, new: newText });
    const res = await fetch("/criteria/apply", { method: "POST", body });
    const data = await res.json();
    if (!data.ok) {
      resultEl.textContent = `적용 실패: ${data.error || "알 수 없는 오류"}`;
      buttons.forEach((b) => (b.disabled = false));
      return;
    }
    const review = data.review || {};
    resultEl.textContent = `✓ 적용됨 — ${review.reason || "검토가 곧 시작됩니다."}`;
    setTimeout(() => location.reload(), 1500);
  } catch (err) {
    resultEl.textContent = `적용 요청 실패: ${err}`;
    buttons.forEach((b) => (b.disabled = false));
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
    // 사용자 입력을 그대로 마크업으로 삽입하지 않는다 — insertAdjacentHTML은
    // q에 <img onerror=...> 같은 태그가 들어오면 그대로 실행한다(XSS).
    const userDiv = document.createElement("div");
    userDiv.className = "msg user";
    userDiv.textContent = q;
    log.appendChild(userDiv);
    input.value = "";
    submitBtn.disabled = true;
    const thinkingId = `thinking-${Date.now()}`;
    const botDiv = document.createElement("div");
    botDiv.className = "msg bot";
    botDiv.id = thinkingId;
    botDiv.textContent = "…";
    log.appendChild(botDiv);
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
