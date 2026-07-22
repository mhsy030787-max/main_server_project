const NoticePage = (() => {
  const filters = ["전체", "읽지 않음", "승인 요청", "보안 이벤트", "시스템 공지"];
  const statusLabels = {
    pending: "처리 대기",
    approved: "승인 완료",
    rejected: "반려",
    acknowledged: "확인 완료",
    confirmed: "확인 완료",
  };

  function init() {
    if (document.body.dataset.page !== "alerts" || typeof App === "undefined" || !App.core) return;

    const { state, save, escapeHTML, showToast, addLog } = App.core;
    const list = document.querySelector("[data-alerts]");
    const title = document.querySelector("[data-alert-title]");
    const count = document.querySelector("[data-alert-count]");
    const search = document.querySelector("[data-alert-search]");
    const detail = document.querySelector("[data-alert-detail]");
    const settingsForm = document.querySelector("[data-notice-form]");
    if (!list || !title || !count || !search || !detail) return;

    const requestedFilter = new URLSearchParams(window.location.search).get("filter");
    let currentFilter = filters.includes(requestedFilter) ? requestedFilter : "전체";
    let searchTerm = "";

    const normalizeAlerts = () => {
      const next = state();
      next.alerts = (next.alerts || []).map((alert, index) => ({
        ...alert,
        id: alert.id || index + 1,
        createdAt: alert.createdAt || new Date(Date.now() - index * 900000).toISOString(),
        priority: alert.priority || (alert.type === "보안 이벤트" ? "높음" : "보통"),
        status: alert.status || (alert.type === "승인 요청" ? "pending" : alert.read ? "confirmed" : "pending"),
        relatedDocumentId: alert.relatedDocumentId || (alert.type === "승인 요청" ? 2 : null),
      }));
      save(next);
      return next;
    };

    const setView = (view) => {
      document.querySelector("[data-alert-list-view]")?.classList.toggle("active", view === "list");
      document.querySelector("[data-alert-detail-view]")?.classList.toggle("active", view === "detail");
      document.querySelector("[data-alert-settings-view]")?.classList.toggle("active", view === "settings");
      document.querySelector("[data-alert-settings]")?.classList.toggle("active", view === "settings");
    };

    const formatDate = (value) => {
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return "시간 정보 없음";
      return date.toLocaleString("ko-KR", {
        month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
      });
    };

    const filteredAlerts = (next) => next.alerts
      .filter((alert) => {
        if (currentFilter === "읽지 않음") return !alert.read;
        if (currentFilter === "전체") return true;
        return alert.type === currentFilter;
      })
      .filter((alert) => {
        const haystack = `${alert.title} ${alert.message} ${alert.type}`.toLowerCase();
        return haystack.includes(searchTerm.toLowerCase());
      })
      .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));

    const renderList = () => {
      const next = state();
      const items = filteredAlerts(next);
      setView("list");
      title.textContent = currentFilter === "전체" ? "전체 알림" : currentFilter;
      count.textContent = `${items.length}개 알림`;
      document.querySelectorAll("[data-alert-filter]").forEach((button) => {
        button.classList.toggle("active", button.dataset.alertFilter === currentFilter);
      });

      if (items.length === 0) {
        list.innerHTML = '<li class="notice-empty"><div><strong>알림이 없습니다.</strong><p>조건에 맞는 알림이 없습니다.</p></div></li>';
        return;
      }

      list.innerHTML = items.map((alert) => `
        <li class="notice-item ${alert.read ? "" : "unread"}" data-alert-id="${alert.id}" tabindex="0">
          <span class="notice-dot" aria-hidden="true"></span>
          <div>
            <strong>${escapeHTML(alert.title)} <span class="${alert.read ? "badge" : "badge warn"}">${alert.read ? statusLabels[alert.status] || "읽음" : "새 알림"}</span></strong>
            <div class="notice-meta">${escapeHTML(alert.type)} · 중요도 ${escapeHTML(alert.priority)}</div>
            <div class="notice-meta">${escapeHTML(alert.message)}</div>
          </div>
          <time class="notice-item-time">${escapeHTML(formatDate(alert.createdAt))}</time>
        </li>
      `).join("");
    };

    const actionButtons = (alert) => {
      if (alert.type === "승인 요청" && alert.status === "pending") {
        return `
          <button class="danger-button" type="button" data-alert-action="reject" data-alert-id="${alert.id}">반려</button>
          <button class="primary-button small-button" type="button" data-alert-action="approve" data-alert-id="${alert.id}">승인</button>
        `;
      }
      if (alert.status === "pending") {
        return `<button class="primary-button small-button" type="button" data-alert-action="acknowledge" data-alert-id="${alert.id}">확인 완료</button>`;
      }
      return "";
    };

    const renderDetail = (alertId) => {
      const next = state();
      const alert = next.alerts.find((item) => String(item.id) === String(alertId));
      if (!alert) return;

      if (!alert.read) {
        alert.read = true;
        save(next);
      }

      detail.innerHTML = `
        <div class="notice-detail-header">
          <div>
            <h2>${escapeHTML(alert.title)}</h2>
            <p class="notice-meta">${escapeHTML(formatDate(alert.createdAt))}</p>
          </div>
          <div class="notice-detail-actions">
            <button class="secondary-button small-button" type="button" data-alert-back>목록으로</button>
            ${actionButtons(alert)}
          </div>
        </div>
        <div class="notice-detail-body">
          <p>${escapeHTML(alert.message)}</p>
          <div class="notice-detail-summary">
            <div><span>분류</span><strong>${escapeHTML(alert.type)}</strong></div>
            <div><span>중요도</span><strong>${escapeHTML(alert.priority)}</strong></div>
            <div><span>처리 상태</span><strong>${escapeHTML(statusLabels[alert.status] || "읽음")}</strong></div>
          </div>
        </div>
      `;
      setView("detail");
    };

    const handleAction = (alertId, action) => {
      const next = state();
      const alert = next.alerts.find((item) => String(item.id) === String(alertId));
      if (!alert) return;

      const actionMap = {
        approve: { status: "approved", message: "승인 요청을 승인했습니다.", log: "문서 승인" },
        reject: { status: "rejected", message: "승인 요청을 반려했습니다.", log: "문서 승인 반려" },
        acknowledge: { status: alert.type === "시스템 공지" ? "confirmed" : "acknowledged", message: "알림을 확인 완료했습니다.", log: "알림 확인" },
      };
      const result = actionMap[action];
      if (!result) return;

      alert.read = true;
      alert.status = result.status;
      alert.resolvedAt = new Date().toISOString();

      if (alert.type === "승인 요청" && alert.relatedDocumentId) {
        const documentItem = next.documents.find((item) => String(item.id) === String(alert.relatedDocumentId));
        if (documentItem) documentItem.status = action === "approve" ? "보호 중" : "승인 반려";
      }

      save(next);
      addLog(result.log, action === "reject" ? "반려" : "처리");
      showToast(result.message);
      renderDetail(alert.id);
    };

    document.querySelectorAll("[data-alert-filter]").forEach((button) => {
      button.addEventListener("click", () => {
        currentFilter = button.dataset.alertFilter;
        searchTerm = "";
        search.value = "";
        renderList();
      });
    });

    search.addEventListener("input", () => {
      searchTerm = search.value.trim();
      renderList();
    });

    document.querySelector("[data-read-all-alerts]")?.addEventListener("click", () => {
      const next = state();
      filteredAlerts(next).forEach((alert) => { alert.read = true; });
      save(next);
      addLog("알림 전체 읽음");
      showToast("표시된 알림을 모두 읽음 처리했습니다.");
      renderList();
    });

    document.querySelector("[data-alert-settings]")?.addEventListener("click", () => {
      document.querySelectorAll("[data-alert-filter]").forEach((button) => button.classList.remove("active"));
      const settings = state().noticeSettings || {};
      settingsForm.elements.namedItem("target").value = settings.target || "관리자";
      settingsForm.elements.namedItem("type").value = settings.type || "보안 이벤트";
      setView("settings");
    });

    settingsForm?.addEventListener("submit", (event) => {
      event.preventDefault();
      const formData = new FormData(settingsForm);
      const next = state();
      next.noticeSettings = { target: formData.get("target"), type: formData.get("type") };
      save(next);
      addLog("알림 설정 저장");
      showToast("알림 설정을 저장했습니다.");
    });

    list.addEventListener("click", (event) => {
      const item = event.target.closest("[data-alert-id]");
      if (item) renderDetail(item.dataset.alertId);
    });

    list.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      const item = event.target.closest("[data-alert-id]");
      if (!item) return;
      event.preventDefault();
      renderDetail(item.dataset.alertId);
    });

    detail.addEventListener("click", (event) => {
      if (event.target.closest("[data-alert-back]")) {
        renderList();
        return;
      }
      const actionButton = event.target.closest("[data-alert-action]");
      if (actionButton) handleAction(actionButton.dataset.alertId, actionButton.dataset.alertAction);
    });

    normalizeAlerts();
    renderList();
  }

  return { init };
})();

document.addEventListener("DOMContentLoaded", NoticePage.init);
