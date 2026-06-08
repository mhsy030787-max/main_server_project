const App = (() => {
  const STORAGE_KEY = "assetPlatformState";

  const seed = {
    profile: {
      name: "관리자",
      userId: "admin",
      role: "관리자",
      browser: "Chrome",
      ip: "127.0.0.1",
    },
    documents: [
      { id: 1, name: "고객정보_정산.xlsx", owner: "팀장", grade: "기밀", status: "보호 중", description: "월별 정산 자료" },
      { id: 2, name: "서버접근_계정.pdf", owner: "관리자", grade: "최고기밀", status: "승인 대기", description: "인프라 접근 정보" },
      { id: 3, name: "프로젝트_계약서.docx", owner: "사원", grade: "내부", status: "보호 중", description: "프로젝트 계약 문서" },
    ],
    users: [
      { id: 1, name: "김사원", userId: "staff01", role: "사원", status: "활성" },
      { id: 2, name: "이팀장", userId: "leader01", role: "팀장", status: "활성" },
      { id: 3, name: "박관리", userId: "admin01", role: "관리자", status: "점검" },
    ],
    grades: [
      { id: 1, name: "내부", description: "사내 공유 문서", policy: "권한 내 허용", status: "사용" },
      { id: 2, name: "기밀", description: "민감 업무 자료", policy: "로그 기록 필수", status: "사용" },
      { id: 3, name: "최고기밀", description: "핵심 보안 자료", policy: "승인 후 허용", status: "승인 필요" },
    ],
    permissions: [
      { role: "사원", view: "허용", upload: "제한", download: "허용", manage: "차단" },
      { role: "팀장", view: "허용", upload: "허용", download: "허용", manage: "팀 한정" },
      { role: "관리자", view: "허용", upload: "허용", download: "허용", manage: "전체" },
    ],
    logs: [
      { id: 1, time: "14:58", user: "admin01", event: "로그인", ip: "192.168.0.12", result: "성공" },
      { id: 2, time: "14:42", user: "leader01", event: "문서 다운로드", ip: "192.168.0.21", result: "기록" },
      { id: 3, time: "13:20", user: "unknown", event: "외부 접근", ip: "45.12.80.3", result: "차단" },
    ],
    alerts: [
      { id: 1, title: "문서 다운로드 승인 요청", message: "서버접근_계정.pdf 다운로드 승인 대기 중입니다.", type: "승인 요청", read: false },
      { id: 2, title: "외부 IP 접근 차단", message: "허용되지 않은 IP 접근 시도가 차단되었습니다.", type: "보안 이벤트", read: false },
      { id: 3, title: "세션 만료 예정", message: "장시간 미사용 계정 세션이 곧 종료됩니다.", type: "시스템 공지", read: true },
    ],
    transfers: [
      { id: 1, name: "고객정보_정산.xlsx", status: "다운로드 가능" },
      { id: 2, name: "서버접근_계정.pdf", status: "관리자 승인 필요" },
      { id: 3, name: "프로젝트_계약서.docx", status: "로그 기록 후 제공" },
    ],
    noticeSettings: {
      target: "관리자",
      type: "보안 이벤트",
    },
  };

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function state() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) {
      const next = clone(seed);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    }
    return JSON.parse(saved);
  }

  function save(next) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  function nextId(items) {
    return items.reduce((max, item) => Math.max(max, item.id || 0), 0) + 1;
  }

  function badgeClass(value) {
    if (["차단", "접근 차단", "다운로드 차단"].includes(value)) {
      return "badge danger";
    }
    if (["승인 대기", "승인 필요", "제한", "점검", "팀 한정", "관리자 승인 필요"].includes(value)) {
      return "badge warn";
    }
    return "badge";
  }

  function statusClass(value) {
    return value === "승인 대기" ? "status wait" : "status safe";
  }

  function showToast(message) {
    let toast = document.querySelector(".toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.className = "toast";
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 1800);
  }

  async function requireLogin() {
    try {
      const response = await fetch("/api/me");
      const result = await response.json();
      if (!result.ok) {
        location.href = "login_ui.html";
        return null;
      }
      return result.user;
    } catch (error) {
      return state().profile;
    }
  }

  function addLog(event, result = "기록") {
    const next = state();
    next.logs.unshift({
      id: nextId(next.logs),
      time: new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false }),
      user: next.profile.userId,
      event,
      ip: next.profile.ip,
      result,
    });
    save(next);
  }

  function renderMain(next, user) {
    const userBadge = document.querySelector("#userBadge");
    if (userBadge) {
      userBadge.textContent = `${user.name} · ${user.role}`;
    }
    const pendingDocs = next.documents.filter((doc) => doc.status === "승인 대기").length;
    const unreadAlerts = next.alerts.filter((alert) => !alert.read).length;
    setText("#totalDocuments", next.documents.length);
    setText("#todayUploads", next.transfers.length);
    setText("#pendingApprovals", pendingDocs);
    setText("#securityAlerts", unreadAlerts);

    const documentRows = document.querySelector("#documentRows");
    if (documentRows) {
      documentRows.innerHTML = next.documents.slice(0, 5).map((doc) => `
        <tr>
          <td>${doc.name}</td>
          <td>${doc.owner}</td>
          <td>${doc.grade}</td>
          <td><span class="${statusClass(doc.status)}">${doc.status}</span></td>
        </tr>
      `).join("");
    }

    const alertList = document.querySelector("#alertList");
    if (alertList) {
      alertList.innerHTML = next.alerts.slice(0, 3).map((alert) => `
        <li>
          <strong>${alert.title}</strong>
          <span>${alert.message}</span>
        </li>
      `).join("");
    }
  }

  function setText(selector, value) {
    const node = document.querySelector(selector);
    if (node) {
      node.textContent = value;
    }
  }

  function renderDocuments(next, items = next.documents) {
    const tbody = document.querySelector("[data-documents]");
    if (!tbody) return;
    tbody.innerHTML = items.map((doc) => `
      <tr data-document-row="${doc.id}">
        <td>
          <div class="file-name-cell">
            <span class="file-icon">${fileExtension(doc.name)}</span>
            <span>${doc.name}</span>
          </div>
        </td>
        <td>${doc.grade}</td>
        <td>${doc.owner}</td>
        <td>${doc.modifiedAt || "오늘"}</td>
        <td><span class="${badgeClass(doc.status)}">${doc.status}</span></td>
        <td>
          <div class="file-actions">
            <button class="secondary-button small-button" data-download-document="${doc.id}" type="button">다운로드</button>
            <button class="secondary-button small-button" data-delete-document="${doc.id}" type="button">삭제</button>
          </div>
        </td>
      </tr>
    `).join("");
    setText("[data-document-count]", `${items.length}개 항목`);
  }

  function fileExtension(name) {
    const parts = name.split(".");
    if (parts.length < 2) return "FILE";
    return parts.pop().slice(0, 4).toUpperCase();
  }

  function initDocuments() {
    const next = state();
    const sortState = {
      key: "name",
      direction: "asc",
    };
    const search = document.querySelector("[data-document-search]");
    const grade = document.querySelector("[data-document-grade]");
    const dropZone = document.querySelector("[data-upload-drop]");
    const fileInput = document.querySelector("[data-document-file]");
    const nameInput = document.querySelector("[data-document-name]");
    const selectedFile = document.querySelector("[data-selected-file]");

    const useFile = (file) => {
      if (!file) return;
      nameInput.value = file.name;
      if (selectedFile) {
        selectedFile.textContent = file.name;
      }
    };

    fileInput?.addEventListener("change", () => {
      useFile(fileInput.files[0]);
    });

    dropZone?.addEventListener("dragover", (event) => {
      event.preventDefault();
      dropZone.classList.add("drag-over");
    });

    dropZone?.addEventListener("dragleave", () => {
      dropZone.classList.remove("drag-over");
    });

    dropZone?.addEventListener("drop", (event) => {
      event.preventDefault();
      dropZone.classList.remove("drag-over");
      useFile(event.dataTransfer.files[0]);
    });

    const sortDocuments = (items) => {
      return [...items].sort((a, b) => {
        const aValue = String(a[sortState.key] || "");
        const bValue = String(b[sortState.key] || "");
        const result = aValue.localeCompare(bValue, "ko-KR", { numeric: true });
        return sortState.direction === "asc" ? result : -result;
      });
    };

    const updateSortButtons = () => {
      document.querySelectorAll("[data-sort-documents]").forEach((button) => {
        const isActive = button.dataset.sortDocuments === sortState.key;
        const label = button.textContent.replace(/\s[▲▼]$/, "");
        button.classList.toggle("active", isActive);
        button.textContent = isActive ? `${label} ${sortState.direction === "asc" ? "▲" : "▼"}` : label;
      });
    };

    const filter = () => {
      const keyword = search.value.trim();
      const selectedGrade = grade.value;
      const current = state();
      const filtered = current.documents.filter((doc) => {
        const matchesKeyword = !keyword || doc.name.includes(keyword) || doc.owner.includes(keyword);
        const matchesGrade = selectedGrade === "전체 등급" || doc.grade === selectedGrade;
        return matchesKeyword && matchesGrade;
      });
      renderDocuments(current, sortDocuments(filtered));
      updateSortButtons();
    };

    filter();

    search?.addEventListener("input", filter);
    grade?.addEventListener("change", filter);

    document.querySelectorAll("[data-sort-documents]").forEach((button) => {
      button.addEventListener("click", () => {
        const key = button.dataset.sortDocuments;
        if (sortState.key === key) {
          sortState.direction = sortState.direction === "asc" ? "desc" : "asc";
        } else {
          sortState.key = key;
          sortState.direction = "asc";
        }
        filter();
      });
    });

    document.querySelector("[data-document-form]")?.addEventListener("submit", (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const formData = new FormData(form);
      const updated = state();
      updated.documents.unshift({
        id: nextId(updated.documents),
        name: formData.get("name") || "새 문서",
        grade: formData.get("grade"),
        owner: updated.profile.role,
        status: formData.get("grade") === "최고기밀" ? "승인 대기" : "보호 중",
        description: formData.get("description") || "",
        modifiedAt: new Date().toLocaleDateString("ko-KR"),
      });
      save(updated);
      addLog("문서 업로드");
      filter();
      form.reset();
      if (selectedFile) {
        selectedFile.textContent = "파일을 끌어다 놓거나 파일 추가를 누르세요";
      }
      showToast("문서를 등록했습니다.");
    });

    document.addEventListener("click", (event) => {
      const downloadButton = event.target.closest("[data-download-document]");
      if (downloadButton) {
        const current = state();
        const doc = current.documents.find((item) => String(item.id) === downloadButton.dataset.downloadDocument);
        addLog("문서 다운로드");
        showToast(`${doc?.name || "문서"} 다운로드 로그를 기록했습니다.`);
        return;
      }

      const button = event.target.closest("[data-delete-document]");
      if (!button) return;
      const updated = state();
      updated.documents = updated.documents.filter((doc) => String(doc.id) !== button.dataset.deleteDocument);
      save(updated);
      addLog("문서 삭제");
      filter();
      showToast("문서를 삭제했습니다.");
    });

    document.querySelector("[data-document-refresh]")?.addEventListener("click", () => {
      filter();
      showToast("문서 목록을 새로고침했습니다.");
    });

    document.querySelector("[data-document-select-first]")?.addEventListener("click", () => {
      const row = document.querySelector("[data-document-row]");
      if (!row) return;
      document.querySelectorAll("[data-document-row]").forEach((item) => item.classList.remove("selected-row"));
      row.classList.add("selected-row");
      showToast("첫 문서를 선택했습니다.");
    });
  }

  function renderUsers(next, items = next.users) {
    const tbody = document.querySelector("[data-users]");
    if (!tbody) return;
    tbody.innerHTML = items.map((user) => `
      <tr>
        <td>${user.name}</td>
        <td>${user.userId}</td>
        <td>${user.role}</td>
        <td><span class="${badgeClass(user.status)}">${user.status}</span></td>
        <td><button class="secondary-button small-button" data-toggle-user="${user.id}" type="button">상태 변경</button></td>
      </tr>
    `).join("");
  }

  function initUsers() {
    const next = state();
    renderUsers(next);
    const search = document.querySelector("[data-user-search]");
    const role = document.querySelector("[data-user-role]");
    const filter = () => {
      const keyword = search.value.trim();
      const selectedRole = role.value;
      renderUsers(state(), state().users.filter((user) => {
        const matchesKeyword = !keyword || user.name.includes(keyword) || user.userId.includes(keyword);
        const matchesRole = selectedRole === "전체 역할" || user.role === selectedRole;
        return matchesKeyword && matchesRole;
      }));
    };
    search?.addEventListener("input", filter);
    role?.addEventListener("change", filter);

    document.querySelector("[data-user-form]")?.addEventListener("submit", (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const formData = new FormData(form);
      const updated = state();
      updated.users.unshift({
        id: nextId(updated.users),
        name: formData.get("name"),
        userId: formData.get("userId"),
        role: formData.get("role"),
        status: "활성",
      });
      save(updated);
      addLog("사용자 추가");
      renderUsers(updated);
      form.reset();
      showToast("사용자를 추가했습니다.");
    });

    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-toggle-user]");
      if (!button) return;
      const updated = state();
      const user = updated.users.find((item) => String(item.id) === button.dataset.toggleUser);
      user.status = user.status === "활성" ? "점검" : "활성";
      save(updated);
      addLog("사용자 상태 변경");
      renderUsers(updated);
      showToast("사용자 상태를 변경했습니다.");
    });
  }

  function renderGrades(next) {
    const tbody = document.querySelector("[data-grades]");
    if (!tbody) return;
    tbody.innerHTML = next.grades.map((grade) => `
      <tr>
        <td>${grade.name}</td>
        <td>${grade.description}</td>
        <td>${grade.policy}</td>
        <td><span class="${badgeClass(grade.status)}">${grade.status}</span></td>
      </tr>
    `).join("");
  }

  function initGrades() {
    renderGrades(state());
    document.querySelector("[data-grade-form]")?.addEventListener("submit", (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const formData = new FormData(form);
      const updated = state();
      updated.grades.unshift({
        id: nextId(updated.grades),
        name: formData.get("name"),
        policy: formData.get("policy"),
        description: formData.get("description"),
        status: formData.get("policy") === "승인 후 허용" ? "승인 필요" : "사용",
      });
      save(updated);
      addLog("등급 정책 추가");
      renderGrades(updated);
      form.reset();
      showToast("등급 정책을 저장했습니다.");
    });
  }

  function renderPermissions(next) {
    const tbody = document.querySelector("[data-permissions]");
    if (!tbody) return;
    tbody.innerHTML = next.permissions.map((permission) => `
      <tr>
        <td>${permission.role}</td>
        <td><span class="${badgeClass(permission.view)}">${permission.view}</span></td>
        <td><span class="${badgeClass(permission.upload)}">${permission.upload}</span></td>
        <td><span class="${badgeClass(permission.download)}">${permission.download}</span></td>
        <td><span class="${badgeClass(permission.manage)}">${permission.manage}</span></td>
      </tr>
    `).join("");
  }

  function initPermissions() {
    renderPermissions(state());
    document.querySelector("[data-permission-form]")?.addEventListener("submit", (event) => {
      event.preventDefault();
      const formData = new FormData(event.currentTarget);
      const updated = state();
      const role = formData.get("role");
      const policy = formData.get("policy");
      const permission = updated.permissions.find((item) => item.role === role);
      permission.download = policy;
      permission.manage = policy === "접근 차단" ? "차단" : permission.manage;
      save(updated);
      addLog("권한 정책 저장");
      renderPermissions(updated);
      showToast("권한 정책을 저장했습니다.");
    });
  }

  function renderLogs(items) {
    const tbody = document.querySelector("[data-logs]");
    if (!tbody) return;
    tbody.innerHTML = items.map((log) => `
      <tr>
        <td>${log.time}</td>
        <td>${log.user}</td>
        <td>${log.event}</td>
        <td>${log.ip}</td>
        <td><span class="${badgeClass(log.result)}">${log.result}</span></td>
      </tr>
    `).join("");
  }

  function initLogs() {
    renderLogs(state().logs);
    document.querySelector("[data-log-form]")?.addEventListener("submit", (event) => {
      event.preventDefault();
      const formData = new FormData(event.currentTarget);
      const type = formData.get("type");
      const user = formData.get("user").trim();
      renderLogs(state().logs.filter((log) => {
        const matchesType = type === "전체 이벤트" || log.event.includes(type);
        const matchesUser = !user || log.user.includes(user);
        return matchesType && matchesUser;
      }));
    });
  }

  function renderAlerts(next) {
    const list = document.querySelector("[data-alerts]");
    if (!list) return;
    list.innerHTML = next.alerts.map((alert) => `
      <li>
        <strong>${alert.title} ${alert.read ? '<span class="badge">읽음</span>' : '<span class="badge warn">새 알림</span>'}</strong>
        <span>${alert.message}</span>
        <button class="secondary-button small-button" data-read-alert="${alert.id}" type="button">읽음 처리</button>
      </li>
    `).join("");
  }

  function initAlerts() {
    renderAlerts(state());
    document.querySelector("[data-notice-form]")?.addEventListener("submit", (event) => {
      event.preventDefault();
      const formData = new FormData(event.currentTarget);
      const updated = state();
      updated.noticeSettings = {
        target: formData.get("target"),
        type: formData.get("type"),
      };
      save(updated);
      addLog("알림 설정 저장");
      showToast("알림 설정을 저장했습니다.");
    });
    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-read-alert]");
      if (!button) return;
      const updated = state();
      const alert = updated.alerts.find((item) => String(item.id) === button.dataset.readAlert);
      alert.read = true;
      save(updated);
      renderAlerts(updated);
      showToast("알림을 읽음 처리했습니다.");
    });
  }

  function renderTransfers(next) {
    const list = document.querySelector("[data-transfers]");
    if (!list) return;
    list.innerHTML = next.transfers.map((file) => `
      <li>
        <strong>${file.name}</strong>
        <span>${file.status}</span>
        <button class="secondary-button small-button" data-download-file="${file.id}" type="button">다운로드</button>
      </li>
    `).join("");
  }

  function initTransfers() {
    renderTransfers(state());
    document.querySelector("[data-transfer-form]")?.addEventListener("submit", (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const formData = new FormData(form);
      const file = formData.get("file");
      const updated = state();
      updated.transfers.unshift({
        id: nextId(updated.transfers),
        name: file && file.name ? file.name : "선택한_파일.dat",
        status: formData.get("grade") === "최고기밀" ? "관리자 승인 필요" : "다운로드 가능",
      });
      save(updated);
      addLog("파일 업로드");
      renderTransfers(updated);
      form.reset();
      showToast("파일 업로드를 등록했습니다.");
    });
    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-download-file]");
      if (!button) return;
      addLog("파일 다운로드");
      showToast("다운로드 로그를 기록했습니다.");
    });
  }

  function initMypage() {
    const next = state();
    document.querySelector("[name='name']")?.setAttribute("value", next.profile.name);
    document.querySelector("[name='userId']")?.setAttribute("value", next.profile.userId);
    document.querySelector("[name='role']")?.setAttribute("value", next.profile.role);
    setText("[data-browser]", `${next.profile.browser} · macOS · 허용 IP`);
    setText("[data-last-login]", `오늘 · ${next.profile.ip}`);
    setText("[data-my-permissions]", `${next.profile.role} 권한으로 문서 관리와 로그 조회 가능`);

    document.querySelector("[data-profile-form]")?.addEventListener("submit", (event) => {
      event.preventDefault();
      const formData = new FormData(event.currentTarget);
      const updated = state();
      updated.profile.name = formData.get("name");
      updated.profile.userId = formData.get("userId");
      updated.profile.role = formData.get("role");
      save(updated);
      addLog("내 정보 수정");
      showToast("내 정보를 수정했습니다.");
    });
  }

  async function init() {
    const page = document.body.dataset.page;
    if (!page || page === "login") return;

    const user = await requireLogin();
    if (!user) return;

    const next = state();
    next.profile.name = user.name || next.profile.name;
    next.profile.userId = user.id || next.profile.userId;
    next.profile.role = user.role || next.profile.role;
    save(next);

    if (page === "main") renderMain(state(), user);
    if (page === "documents") initDocuments();
    if (page === "permissions") initPermissions();
    if (page === "users") initUsers();
    if (page === "grades") initGrades();
    if (page === "logs") initLogs();
    if (page === "alerts") initAlerts();
    if (page === "transfers") initTransfers();
    if (page === "mypage") initMypage();
  }

  return { init };
})();

document.addEventListener("DOMContentLoaded", App.init);
