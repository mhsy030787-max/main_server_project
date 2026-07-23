const MailApp = (() => {
  const BOX_TITLES = {
    inbox: "받은 메일함",
    sent: "보낸 메일함",
    draft: "임시보관함",
    trash: "휴지통",
  };
  const DELIVERY_LABELS = {
    pending: "발송 중",
    sent: "발송 완료",
    delivered: "전달 완료",
    delayed: "전달 지연",
    failed: "발송 실패",
    bounced: "반송",
    complained: "스팸 신고",
    suppressed: "발송 차단",
  };
  const MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024;

  let apiRequest;
  let escapeHTML;
  let showToast;
  let addLog;
  let activeBox = "inbox";
  let activeMail = null;

  const select = (selector) => document.querySelector(selector);

  async function requestJSON(path, options = {}) {
    const response = await apiRequest(path, options);
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.ok) {
      throw new Error(result.message || "메일 요청을 처리하지 못했습니다.");
    }
    return result;
  }

  function setView(view) {
    select("[data-mail-list-view]")?.classList.toggle("active", view === "list");
    select("[data-mail-detail-view]")?.classList.toggle("active", view === "detail");
    select("[data-mail-compose-view]")?.classList.toggle("active", view === "compose");
    select("[data-mail-compose]")?.classList.toggle("active", view === "compose");
  }

  function setActiveBox(box) {
    activeBox = box;
    document.querySelectorAll("[data-mail-box]").forEach((button) => {
      button.classList.toggle("active", button.dataset.mailBox === box);
    });
  }

  function formatDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleString("ko-KR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }

  function deliveryLabel(status) {
    return DELIVERY_LABELS[status] || status || "확인 중";
  }

  async function renderRecipients() {
    const result = await requestJSON("/api/mail/recipients");
    const target = select("[data-mail-recipients]");
    if (target) {
      target.innerHTML = result.recipients.map((recipient) => (
        `<option value="${escapeHTML(recipient.address)}" label="${escapeHTML(recipient.name)}"></option>`
      )).join("");
    }

    const note = select("[data-mail-capability]");
    if (!note) return;
    const capabilities = result.capabilities || {};
    const sendText = capabilities.externalTestMode
      ? "외부 시험 발송 가능(발송 서비스에 등록된 주소만)"
      : (capabilities.externalSend ? "외부 발송 가능" : "외부 발송 설정 필요");
    const receiveText = capabilities.externalReceive
      ? `외부 수신 주소: 사용자ID@${escapeHTML(capabilities.publicDomain)}`
      : "외부 수신 도메인 설정 필요";
    note.innerHTML = `<strong>@datavault.local</strong> 사내메일 · ${sendText} · ${receiveText}`;
  }

  function emptyListMessage(box) {
    if (box === "draft") return "저장한 임시 메일이 없습니다.";
    if (box === "trash") return "휴지통이 비어 있습니다.";
    return box === "sent" ? "보낸 메일이 없습니다." : "받은 메일이 없습니다.";
  }

  function messageStatus(mail) {
    if (mail.mailbox === "draft" || mail.direction === "draft") return "임시 저장";
    if (mail.direction === "outbound") return deliveryLabel(mail.deliveryStatus);
    return "";
  }

  async function renderMessages(box = activeBox) {
    const list = select("[data-mail-list]");
    const title = select("[data-mail-title]");
    if (!list || !title) return;

    setActiveBox(box);
    setView("list");
    title.textContent = BOX_TITLES[box] || BOX_TITLES.inbox;
    list.innerHTML = '<li class="mail-item"><strong>메일을 불러오는 중입니다.</strong></li>';

    const result = await requestJSON(`/api/mail/messages?box=${encodeURIComponent(box)}`);
    if (!result.messages.length) {
      list.innerHTML = `<li class="mail-item"><strong>${emptyListMessage(box)}</strong></li>`;
      return;
    }

    list.innerHTML = result.messages.map((mail) => {
      const status = messageStatus(mail);
      const subject = mail.subject || "(제목 없음)";
      return `
        <li>
          <button class="mail-item" type="button" data-mail-id="${mail.id}">
            <strong>${mail.read ? "" : "● "}${escapeHTML(subject)}${mail.hasAttachment ? " · 첨부" : ""}</strong>
            <span class="mail-meta">${escapeHTML(mail.otherName || "")} &lt;${escapeHTML(mail.otherAddress || "")}&gt; · ${formatDate(mail.sentAt)} · ${escapeHTML(mail.grade || "내부")}</span>
            ${status ? `<span class="mail-item-status">${escapeHTML(status)}</span>` : ""}
          </button>
        </li>
      `;
    }).join("");
  }

  function attachmentButtons(mail) {
    const attachments = mail.attachments || (mail.attachment ? [mail.attachment] : []);
    if (!attachments.length) return '<span class="mail-meta">첨부 없음</span>';
    return attachments.map((item) => `
      <button class="secondary-button small-button" type="button"
        data-mail-attachment-id="${item.id}"
        data-mail-attachment-name="${escapeHTML(item.name)}">
        첨부 다운로드 · ${escapeHTML(item.name)}
      </button>
    `).join("");
  }

  function detailActions(mail) {
    const actions = ['<button class="secondary-button small-button" type="button" data-mail-back>목록으로</button>'];
    if (mail.mailbox === "trash") {
      actions.unshift(
        '<button class="secondary-button small-button" type="button" data-mail-action="restore">복원</button>',
        '<button class="secondary-button small-button mail-danger-button" type="button" data-mail-action="delete">영구 삭제</button>',
      );
      return actions.join("");
    }
    if (mail.canEdit) {
      actions.unshift('<button class="secondary-button small-button" type="button" data-mail-compose-action="edit">계속 작성</button>');
    } else {
      if (mail.viewerRole === "recipient") {
        actions.unshift('<button class="secondary-button small-button" type="button" data-mail-compose-action="reply">답장</button>');
      }
      actions.unshift('<button class="secondary-button small-button" type="button" data-mail-compose-action="forward">전달</button>');
    }
    if (mail.canRetry) {
      actions.unshift('<button class="secondary-button small-button" type="button" data-mail-action="retry">재전송</button>');
    }
    actions.unshift('<button class="secondary-button small-button mail-danger-button" type="button" data-mail-action="trash">휴지통</button>');
    return actions.join("");
  }

  async function showMessageDetail(messageId) {
    const detail = select("[data-mail-detail]");
    if (!detail) return;
    setView("detail");
    detail.innerHTML = "<p>메일을 불러오는 중입니다.</p>";

    const result = await requestJSON(`/api/mail/messages/${messageId}`);
    const mail = result.message;
    activeMail = mail;
    const deliveryText = mail.direction === "outbound"
      ? ` · 전달 상태: ${deliveryLabel(mail.deliveryStatus)}`
      : "";
    const dateLabel = mail.direction === "draft" ? "저장 시각" : "발송 시각";

    detail.innerHTML = `
      <div class="mail-detail-header">
        <div>
          <h2>${escapeHTML(mail.subject || "(제목 없음)")}</h2>
          <p class="mail-meta">보낸 사람: ${escapeHTML(mail.senderName || "")} &lt;${escapeHTML(mail.from || "")}&gt;</p>
          <p class="mail-meta">받는 사람: ${escapeHTML(mail.recipientName || "미지정")} &lt;${escapeHTML(mail.to || "")}&gt;</p>
          <p class="mail-meta">보안 등급: ${escapeHTML(mail.grade || "내부")} · ${dateLabel}: ${formatDate(mail.sentAt)}${escapeHTML(deliveryText)}</p>
        </div>
        <div class="mail-detail-actions">${detailActions(mail)}</div>
      </div>
      <div class="mail-detail-body">
        <p style="white-space: pre-wrap;">${escapeHTML(mail.body || "")}</p>
        <div style="margin-top: 18px;">${attachmentButtons(mail)}</div>
      </div>
    `;
    addLog("메일 열람");
  }

  async function fileAsBase64(file) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = "";
    const chunkSize = 0x8000;
    for (let index = 0; index < bytes.length; index += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
    }
    return btoa(binary);
  }

  function setAttachmentLabel(file, existingName = "") {
    const label = select("[data-mail-attachment-name]");
    if (!label) return;
    if (file) {
      label.textContent = file.name;
    } else if (existingName) {
      label.textContent = `기존 첨부: ${existingName} · 새 파일 선택 시 교체`;
    } else {
      label.textContent = "파일을 끌어다 놓거나 파일 추가를 누르세요";
    }
  }

  function resetComposer() {
    const form = select("[data-mail-form]");
    form?.reset();
    if (form?.elements.messageId) form.elements.messageId.value = "";
    setAttachmentLabel(null);
    const title = select("[data-mail-compose-title]");
    if (title) title.textContent = "메일 작성";
  }

  function quoteOriginal(mail) {
    const date = formatDate(mail.sentAt);
    return `\n\n----- 전달된 메일 -----\n보낸 사람: ${mail.from || ""}\n발송 시각: ${date}\n제목: ${mail.subject || ""}\n\n${mail.body || ""}`;
  }

  function openComposer(mode = "new", mail = null) {
    resetComposer();
    document.querySelectorAll("[data-mail-box]").forEach((button) => button.classList.remove("active"));
    const form = select("[data-mail-form]");
    const title = select("[data-mail-compose-title]");
    if (!form) return;

    if (mode === "edit" && mail) {
      title.textContent = "임시 메일 작성";
      form.elements.messageId.value = mail.id;
      form.elements.to.value = mail.to || "";
      form.elements.subject.value = mail.subject || "";
      form.elements.body.value = mail.body || "";
      form.elements.grade.value = ["내부", "기밀", "최고기밀"].includes(mail.grade) ? mail.grade : "내부";
      setAttachmentLabel(null, mail.attachments?.[0]?.name || mail.attachment?.name || "");
    } else if (mode === "reply" && mail) {
      title.textContent = "답장";
      form.elements.to.value = mail.from || "";
      form.elements.subject.value = mail.subject?.startsWith("Re:") ? mail.subject : `Re: ${mail.subject || ""}`;
      form.elements.body.value = `\n\n----- 원본 메일 -----\n${mail.body || ""}`;
      form.elements.grade.value = ["내부", "기밀", "최고기밀"].includes(mail.grade) ? mail.grade : "내부";
    } else if (mode === "forward" && mail) {
      title.textContent = "메일 전달";
      form.elements.subject.value = mail.subject?.startsWith("Fwd:") ? mail.subject : `Fwd: ${mail.subject || ""}`;
      form.elements.body.value = quoteOriginal(mail);
      form.elements.grade.value = ["내부", "기밀", "최고기밀"].includes(mail.grade) ? mail.grade : "내부";
    }
    setView("compose");
    form.elements.to.focus();
  }

  async function buildPayload(form) {
    const formData = new FormData(form);
    const attachmentFile = form.querySelector("[data-mail-attachment-file]")?.files?.[0];
    if (attachmentFile && attachmentFile.size > MAX_ATTACHMENT_BYTES) {
      throw new Error("첨부 파일은 5MB 이하만 가능합니다.");
    }
    const attachment = attachmentFile ? {
      name: attachmentFile.name,
      contentType: attachmentFile.type || "application/octet-stream",
      data: await fileAsBase64(attachmentFile),
    } : null;
    return {
      to: String(formData.get("to") || "").trim(),
      subject: String(formData.get("subject") || "").trim(),
      body: String(formData.get("body") || "").trim(),
      grade: String(formData.get("grade") || "내부"),
      attachment,
      messageId: String(formData.get("messageId") || ""),
    };
  }

  async function submitComposer({ draft }) {
    const form = select("[data-mail-form]");
    if (!form) return;
    if (!draft && !form.reportValidity()) return;

    const sendButton = select("[data-mail-send]");
    const draftButton = select("[data-mail-save-draft]");
    sendButton.disabled = true;
    draftButton.disabled = true;
    const originalText = draftButton.textContent;
    if (draft) draftButton.textContent = "저장 중...";
    else sendButton.textContent = "보내는 중...";

    try {
      const payload = await buildPayload(form);
      const path = draft ? "/api/mail/drafts" : "/api/mail/messages";
      if (!draft) {
        payload.draftId = payload.messageId;
        delete payload.messageId;
      }
      const result = await requestJSON(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      resetComposer();
      addLog(draft ? "메일 임시 저장" : "메일 발송");
      showToast(result.message);
      await renderMessages(draft ? "draft" : "sent");
    } finally {
      sendButton.disabled = false;
      draftButton.disabled = false;
      sendButton.textContent = "메일 보내기";
      draftButton.textContent = originalText;
    }
  }

  async function runMessageAction(action) {
    if (!activeMail) return;
    if (action === "delete" && !window.confirm("이 메일을 영구 삭제할까요? 이 작업은 되돌릴 수 없습니다.")) {
      return;
    }
    const result = await requestJSON(`/api/mail/messages/${activeMail.id}/${action}`, { method: "POST" });
    const logNames = { trash: "메일 휴지통 이동", restore: "메일 복원", delete: "메일 영구 삭제", retry: "메일 재전송" };
    addLog(logNames[action] || "메일 처리");
    showToast(result.message);
    if (action === "retry") {
      await showMessageDetail(activeMail.id);
    } else {
      activeMail = null;
      await renderMessages(activeBox);
    }
  }

  async function downloadAttachment(id, name) {
    const response = await apiRequest(`/api/mail/attachments/${id}`);
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.message || "첨부 파일을 다운로드하지 못했습니다.");
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = name || "attachment";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    addLog("메일 첨부 다운로드");
  }

  function bindAttachmentPicker() {
    const drop = select("[data-mail-attachment-drop]");
    const input = select("[data-mail-attachment-file]");
    input?.addEventListener("change", (event) => setAttachmentLabel(event.currentTarget.files?.[0]));
    drop?.addEventListener("dragover", (event) => {
      event.preventDefault();
      drop.classList.add("drag-over");
    });
    drop?.addEventListener("dragleave", () => drop.classList.remove("drag-over"));
    drop?.addEventListener("drop", (event) => {
      event.preventDefault();
      drop.classList.remove("drag-over");
      const file = event.dataTransfer.files?.[0];
      if (!file || !input) return;
      const transfer = new DataTransfer();
      transfer.items.add(file);
      input.files = transfer.files;
      setAttachmentLabel(file);
    });
  }

  function bindEvents() {
    document.querySelectorAll("[data-mail-box]").forEach((button) => {
      button.addEventListener("click", () => {
        renderMessages(button.dataset.mailBox).catch((error) => showToast(error.message));
      });
    });
    select("[data-mail-compose]")?.addEventListener("click", () => openComposer());
    select("[data-mail-form]")?.addEventListener("submit", (event) => {
      event.preventDefault();
      submitComposer({ draft: false }).catch((error) => showToast(error.message));
    });
    select("[data-mail-save-draft]")?.addEventListener("click", () => {
      submitComposer({ draft: true }).catch((error) => showToast(error.message));
    });

    document.addEventListener("click", (event) => {
      const back = event.target.closest("[data-mail-back]");
      if (back) {
        renderMessages(activeBox).catch((error) => showToast(error.message));
        return;
      }
      const attachment = event.target.closest("[data-mail-attachment-id]");
      if (attachment) {
        downloadAttachment(attachment.dataset.mailAttachmentId, attachment.dataset.mailAttachmentName)
          .catch((error) => showToast(error.message));
        return;
      }
      const action = event.target.closest("[data-mail-action]");
      if (action) {
        runMessageAction(action.dataset.mailAction).catch((error) => showToast(error.message));
        return;
      }
      const composeAction = event.target.closest("[data-mail-compose-action]");
      if (composeAction) {
        openComposer(composeAction.dataset.mailComposeAction, activeMail);
        return;
      }
      const item = event.target.closest("[data-mail-id]");
      if (item) showMessageDetail(item.dataset.mailId).catch((error) => showToast(error.message));
    });
  }

  async function init(dependencies) {
    ({ apiRequest, escapeHTML, showToast, addLog } = dependencies);
    bindAttachmentPicker();
    bindEvents();
    try {
      await Promise.all([renderRecipients(), renderMessages("inbox")]);
    } catch (error) {
      showToast(error.message);
    }
  }

  return { init };
})();

window.MailApp = MailApp;
