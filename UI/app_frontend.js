const App = (() => {
  const STORAGE_KEY = "assetPlatformState";
  const LEGACY_DEMO_USER_IDS = new Set(["staff01", "leader01", "admin01"]);
  const API_BASE = ["127.0.0.1", "localhost"].includes(location.hostname) && location.port && location.port !== "8000"
    ? "http://127.0.0.1:8000"
    : "";

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
      { id: 1, name: "관리자", userId: "admin", role: "관리자", status: "활성" },
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
    schedules: [
      { id: 1, date: todayKey(), time: "09:30", title: "전사 보안 공지 확인", description: "월간 보안 정책 공유", type: "보안", category: "회사" },
      { id: 2, date: todayKey(), time: "10:30", title: "문서 승인 회의", description: "최고기밀 문서 다운로드 승인 검토", type: "승인", category: "팀" },
      { id: 3, date: todayKey(), time: "17:30", title: "백업 확인", description: "암호화 문서 백업 상태 점검", type: "시스템", category: "개인" },
      { id: 4, date: todayKey(), time: "11:00", title: "개인정보 교육", description: "사내 보안 교육 참석", type: "교육", category: "회사" },
      { id: 5, date: todayKey(), time: "14:00", title: "보안 점검", description: "외부 IP 차단 로그와 접근 정책 확인", type: "보안", category: "팀" },
      { id: 6, date: todayKey(), time: "18:00", title: "메일 회신", description: "승인 요청 메일 확인", type: "업무", category: "개인" },
    ],
    mails: [
      {
        id: 1,
        from: "notice@datavault.local",
        to: "admin@datavault.local",
        subject: "최고기밀 문서 승인 요청",
        body: "서버접근_계정.pdf 문서 다운로드 승인이 필요합니다.",
        attachment: "서버접근_계정.pdf",
        grade: "최고기밀",
        box: "inbox",
        read: false,
        sentAt: "오늘 09:30",
        status: "수신",
      },
      {
        id: 2,
        from: "admin@datavault.local",
        to: "leader@datavault.local",
        subject: "정산 문서 검토 요청",
        body: "고객정보_정산.xlsx 문서 확인 후 회신 부탁드립니다.",
        attachment: "고객정보_정산.xlsx",
        grade: "기밀",
        box: "sent",
        read: true,
        sentAt: "오늘 10:15",
        status: "발송 완료",
      },
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
    lastLogArchiveDate: "",
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
    const next = JSON.parse(saved);
    if (!Array.isArray(next.mails)) {
      next.mails = clone(seed.mails);
    }
    if (!Array.isArray(next.users)) {
      next.users = clone(seed.users);
    } else {
      next.users = next.users.filter((user) => !LEGACY_DEMO_USER_IDS.has(user.userId));
      if (!next.users.some((user) => user.userId === "admin")) {
        next.users.unshift(clone(seed.users[0]));
      }
    }
    if (!Array.isArray(next.documents)) {
      next.documents = clone(seed.documents);
    }
    if (!Array.isArray(next.logs)) {
      next.logs = clone(seed.logs);
    }
    if (!Array.isArray(next.alerts) || next.alerts.length === 0) {
      next.alerts = clone(seed.alerts);
    }
    if (!Array.isArray(next.schedules)) {
      next.schedules = clone(seed.schedules);
    } else {
      next.schedules = next.schedules.map((schedule, index) => ({
        ...schedule,
        id: schedule.id || index + 1,
        date: schedule.date || todayKey(),
        category: seed.schedules.find((item) => item.time === schedule.time && item.title === schedule.title)?.category
          || schedule.category
          || (schedule.type === "보안" ? "회사" : schedule.type === "승인" ? "팀" : "개인"),
      }));
      const seenSchedules = new Set();
      next.schedules = next.schedules.filter((schedule) => {
        const key = `${schedule.date}-${schedule.time}-${schedule.title}`;
        if (seenSchedules.has(key)) return false;
        seenSchedules.add(key);
        return true;
      });
    }
    if (!next.lastLogArchiveDate) {
      next.lastLogArchiveDate = "";
    }
    if (!next.profile) {
      next.profile = clone(seed.profile);
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    return next;
  }

  function save(next) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  function todayKey() {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, "0");
    const day = String(today.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
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

  function apiPath(path) {
    return `${API_BASE}${path}`;
  }

  async function apiRequest(path, options = {}) {
    const request = async () => {
      const token = localStorage.getItem("accessToken");
      const headers = { ...(options.headers || {}) };
      if (token) headers.Authorization = `Bearer ${token}`;
      return fetch(apiPath(path), { credentials: "include", ...options, headers });
    };
    let response = await request();
    if (response.status === 401) {
      const refreshResponse = await fetch(apiPath("/api/refresh"), { method: "POST", credentials: "include" });
      const refreshResult = await refreshResponse.json().catch(() => ({}));
      if (refreshResult.ok) {
        localStorage.setItem("accessToken", refreshResult.accessToken);
        response = await request();
      }
    }
    return response;
  }

  function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
    })[character]);
  }

  function initEmbeddedNavigation() {
    if (window.parent === window) {
      return;
    }

    let parentOrigin = window.location.origin;
    try {
      parentOrigin = window.parent.location.origin;
    } catch (error) {
      parentOrigin = window.location.origin === "null" ? "*" : window.location.origin;
    }

    const navigableLinks = document.querySelectorAll(".global-nav a[href], .back-link[href]");
    navigableLinks.forEach((link) => {
      link.addEventListener("click", (event) => {
        const href = link.getAttribute("href");
        const isModifiedClick = event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
        const opensNewContext = link.target === "_blank" || event.button !== 0;

        if (!href || href.startsWith("#") || isModifiedClick || opensNewContext) {
          return;
        }

        event.preventDefault();
        window.parent.postMessage({
          type: "datavault:navigate",
          href,
        }, parentOrigin);
      });
    });
  }

  async function requireLogin() {
    try {
      let accessToken = localStorage.getItem("accessToken");
      let response = await fetch(apiPath("/api/me"), {
        credentials: "include",
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
      });
      if (response.status === 401) {
        const refreshResponse = await fetch(apiPath("/api/refresh"), {
          method: "POST",
          credentials: "include",
        });
        const refreshResult = await refreshResponse.json();
        if (refreshResult.ok) {
          localStorage.setItem("accessToken", refreshResult.accessToken);
          accessToken = refreshResult.accessToken;
          response = await fetch(apiPath("/api/me"), {
            credentials: "include",
            headers: { Authorization: `Bearer ${accessToken}` },
          });
        }
      }
      const result = await response.json();
      if (!result.ok) {
        localStorage.removeItem("accessToken");
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

  function archiveLogsIfNeeded() {
    const next = state();
    const currentDate = todayKey();

    if (!next.lastLogArchiveDate) {
      next.lastLogArchiveDate = currentDate;
      save(next);
      return;
    }

    if (next.lastLogArchiveDate === currentDate) {
      return;
    }

    if (next.logs.length === 0) {
      next.lastLogArchiveDate = currentDate;
      save(next);
      return;
    }

    const archiveDate = next.lastLogArchiveDate;
    const archiveName = `감사추적_로그_${archiveDate}.txt`;
    const alreadyArchived = next.documents.some((doc) => doc.name === archiveName);

    if (!alreadyArchived) {
      next.documents.unshift({
        id: nextId(next.documents),
        name: archiveName,
        owner: "시스템",
        grade: "기밀",
        status: "보관 완료",
        description: `${archiveDate} 접속/다운로드/관리 작업 로그 ${next.logs.length}건 자동 보관`,
        modifiedAt: currentDate,
      });
    }

    next.logs = [
      {
        id: 1,
        time: "00:00",
        user: "system",
        event: "일일 로그 초기화",
        ip: "127.0.0.1",
        result: "보관 완료",
      },
    ];
    next.lastLogArchiveDate = currentDate;
    save(next);
  }

  function renderMain(next, user) {
    const userBadge = document.querySelector("#userBadge");
    if (userBadge) {
      userBadge.textContent = `${user.name} · ${user.role}`;
    }
    const pendingDocs = next.documents.filter((doc) => doc.status === "승인 대기").length;
    const unreadAlerts = next.alerts.filter((alert) => !alert.read).length;
    const todayUploads = next.documents.filter((doc) => doc.uploadedAt === todayKey()).length;
    setText("#totalDocuments", next.documents.length);
    setText("#todayUploads", todayUploads);
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

    const scheduleList = document.querySelector("#scheduleList");
    if (scheduleList) {
      const todaySchedules = next.schedules
        .filter((schedule) => schedule.date === todayKey())
        .sort((a, b) => a.time.localeCompare(b.time));
      scheduleList.innerHTML = todaySchedules.length ? todaySchedules.slice(0, 3).map((schedule) => `
        <li>
          <strong>${escapeHTML(schedule.time)} · ${escapeHTML(schedule.title)}</strong>
          <span>${escapeHTML(schedule.description)}</span>
        </li>
      `).join("") : `
        <li>
          <strong>등록된 일정이 없습니다.</strong>
          <span>일정 관리에서 오늘 일정을 추가할 수 있습니다.</span>
        </li>
      `;
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
        uploadedAt: todayKey(),
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

  function maskIp(value) {
    if (!value) return "-";
    const parts = String(value).split(".");
    if (parts.length !== 4) return "비공개";
    return `${parts[0]}.${parts[1]}.*.*`;
  }

  function renderLogs(items) {
    const tbody = document.querySelector("[data-logs]");
    if (!tbody) return;
    tbody.innerHTML = items.map((log) => `
      <tr>
        <td>${log.time}</td>
        <td>${log.user}</td>
        <td>${log.event}</td>
        <td>${maskIp(log.ip)}</td>
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

    if (document.querySelector("[data-settings-tab]")) {
      initAdminSettings();
    }
  }

  function initAdminSettings() {
    initUsers();
    initPermissions();
    initGrades();

    document.querySelectorAll("[data-settings-tab]").forEach((button) => {
      button.addEventListener("click", () => {
        const target = button.dataset.settingsTab;
        document.querySelectorAll("[data-settings-tab]").forEach((item) => {
          item.classList.toggle("active", item === button);
        });
        document.querySelectorAll("[data-settings-section]").forEach((section) => {
          section.classList.toggle("active", section.dataset.settingsSection === target);
        });
      });
    });
  }

  async function renderMailRecipients() {
    const target = document.querySelector("[data-mail-recipients]");
    if (!target) return;
    const response = await apiRequest("/api/mail/recipients");
    const result = await response.json();
    if (!result.ok) throw new Error(result.message || "사용자 목록을 불러오지 못했습니다.");
    target.innerHTML = result.recipients.map((recipient) => (
      `<option value="${escapeHTML(recipient.address)}" label="${escapeHTML(recipient.name)}"></option>`
    )).join("");
    const note = document.querySelector("[data-mail-capability]");
    if (note) {
      const capabilities = result.capabilities || {};
      const sendText = capabilities.externalTestMode
        ? "외부 시험 발송 가능(Resend 계정 이메일만)"
        : (capabilities.externalSend ? "외부 발송 가능" : "외부 발송 설정 필요");
      const receiveText = capabilities.externalReceive
        ? `외부 수신 주소: 사용자ID@${escapeHTML(capabilities.publicDomain)}`
        : "외부 수신 도메인 설정 필요";
      note.innerHTML = `<strong>@datavault.local</strong> 사내메일 · ${sendText} · ${receiveText}`;
    }
  }

  function setMailView(view) {
    const isCompose = view === "compose";
    const isDetail = view === "detail";
    document.querySelector("[data-mail-list-view]")?.classList.toggle("active", view === "list");
    document.querySelector("[data-mail-detail-view]")?.classList.toggle("active", isDetail);
    document.querySelector("[data-mail-compose-view]")?.classList.toggle("active", isCompose);
    document.querySelector("[data-mail-compose]")?.classList.toggle("active", isCompose);
  }

  let activeMailBox = "inbox";

  function formatMailDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
  }

  async function renderMails(box = "inbox") {
    const list = document.querySelector("[data-mail-list]");
    const title = document.querySelector("[data-mail-title]");
    if (!list || !title) return;
    activeMailBox = box;
    setMailView("list");
    document.querySelectorAll("[data-mail-box]").forEach((button) => {
      button.classList.toggle("active", button.dataset.mailBox === box);
    });
    title.textContent = box === "inbox" ? "받은 메일함" : "보낸 메일함";
    list.innerHTML = '<li class="mail-item"><strong>메일을 불러오는 중입니다.</strong></li>';
    const response = await apiRequest(`/api/mail/messages?box=${box}`);
    const result = await response.json();
    if (!result.ok) throw new Error(result.message || "메일을 불러오지 못했습니다.");
    const mails = result.messages;

    if (mails.length === 0) {
      list.innerHTML = '<li class="mail-item"><strong>메일이 없습니다.</strong><div class="mail-meta">새 메일을 작성해보세요.</div></li>';
      return;
    }

    const deliveryLabel = { pending: "발송 중", sent: "발송 완료", failed: "발송 실패" };
    list.innerHTML = mails.map((mail) => `
      <li class="mail-item" data-mail-id="${mail.id}">
        <strong>${mail.read ? "" : "● "}${escapeHTML(mail.subject)}${mail.hasAttachment ? " · 첨부" : ""}</strong>
        <div class="mail-meta">${escapeHTML(mail.otherName)} &lt;${escapeHTML(mail.otherAddress)}&gt; · ${formatMailDate(mail.sentAt)} · ${escapeHTML(mail.grade)}${mail.direction === "outbound" ? ` · ${deliveryLabel[mail.deliveryStatus] || escapeHTML(mail.deliveryStatus)}` : ""}</div>
      </li>
    `).join("");
  }

  async function showMailDetail(mailId) {
    const detail = document.querySelector("[data-mail-detail]");
    if (!detail) return;
    detail.innerHTML = "<p>메일을 불러오는 중입니다.</p>";
    setMailView("detail");
    const response = await apiRequest(`/api/mail/messages/${mailId}`);
    const result = await response.json();
    if (!result.ok) throw new Error(result.message || "메일을 불러오지 못했습니다.");
    const mail = result.message;
    const deliveryLabel = { pending: "발송 중", sent: "발송 완료", failed: "발송 실패" };
    const deliveryText = mail.direction === "outbound"
      ? ` · 전달 상태: ${deliveryLabel[mail.deliveryStatus] || mail.deliveryStatus || "확인 중"}`
      : "";
    const attachments = mail.attachments || (mail.attachment ? [mail.attachment] : []);
    const attachment = attachments.length
      ? attachments.map((item) => `<button class="secondary-button small-button" type="button" data-mail-attachment-id="${item.id}" data-mail-attachment-name="${escapeHTML(item.name)}">첨부 다운로드 · ${escapeHTML(item.name)}</button>`).join(" ")
      : '<span class="mail-meta">첨부 없음</span>';
    detail.innerHTML = `
      <div class="mail-detail-header">
        <div>
          <h2>${escapeHTML(mail.subject)}</h2>
          <p class="mail-meta">보낸 사람: ${escapeHTML(mail.senderName)} &lt;${escapeHTML(mail.from)}&gt;</p>
          <p class="mail-meta">받는 사람: ${escapeHTML(mail.recipientName)} &lt;${escapeHTML(mail.to)}&gt;</p>
          <p class="mail-meta">보안 등급: ${escapeHTML(mail.grade)} · ${formatMailDate(mail.sentAt)}${escapeHTML(deliveryText)}</p>
        </div>
        <button class="secondary-button small-button" type="button" data-mail-back>목록으로</button>
      </div>
      <div class="mail-detail-body">
        <p style="white-space: pre-wrap;">${escapeHTML(mail.body)}</p>
        <div style="margin-top: 18px;">${attachment}</div>
      </div>
    `;
    setMailView("detail");
    addLog("메일 열람");
  }

  async function fileAsBase64(file) {
    const buffer = await file.arrayBuffer();
    const bytes = new Uint8Array(buffer);
    let binary = "";
    const chunkSize = 0x8000;
    for (let index = 0; index < bytes.length; index += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
    }
    return btoa(binary);
  }

  async function downloadMailAttachment(id, name) {
    const response = await apiRequest(`/api/mail/attachments/${id}`);
    if (!response.ok) {
      const result = await response.json().catch(() => ({}));
      throw new Error(result.message || "첨부 파일을 다운로드하지 못했습니다.");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = name || "attachment";
    link.click();
    URL.revokeObjectURL(url);
  }

  async function initMail() {
    try {
      await Promise.all([renderMailRecipients(), renderMails("inbox")]);
    } catch (error) {
      showToast(error.message);
    }

    const attachmentDrop = document.querySelector("[data-mail-attachment-drop]");
    const attachmentInput = document.querySelector("[data-mail-attachment-file]");
    const setMailAttachment = (file) => {
      const label = document.querySelector("[data-mail-attachment-name]");
      if (label) label.textContent = file ? file.name : "파일을 끌어다 놓거나 파일 추가를 누르세요";
    };

    attachmentInput?.addEventListener("change", (event) => {
      setMailAttachment(event.currentTarget.files?.[0]);
    });

    attachmentDrop?.addEventListener("dragover", (event) => {
      event.preventDefault();
      attachmentDrop.classList.add("drag-over");
    });

    attachmentDrop?.addEventListener("dragleave", () => {
      attachmentDrop.classList.remove("drag-over");
    });

    attachmentDrop?.addEventListener("drop", (event) => {
      event.preventDefault();
      attachmentDrop.classList.remove("drag-over");
      const file = event.dataTransfer.files?.[0];
      if (!file || !attachmentInput) return;
      const transfer = new DataTransfer();
      transfer.items.add(file);
      attachmentInput.files = transfer.files;
      setMailAttachment(file);
    });

    document.querySelectorAll("[data-mail-box]").forEach((button) => {
      button.addEventListener("click", () => {
        renderMails(button.dataset.mailBox).catch((error) => showToast(error.message));
      });
    });

    document.querySelector("[data-mail-compose]")?.addEventListener("click", () => {
      document.querySelectorAll("[data-mail-box]").forEach((button) => button.classList.remove("active"));
      setMailView("compose");
    });

    document.addEventListener("click", (event) => {
      const backButton = event.target.closest("[data-mail-back]");
      if (backButton) {
        renderMails(activeMailBox).catch((error) => showToast(error.message));
        return;
      }

      const attachmentButton = event.target.closest("[data-mail-attachment-id]");
      if (attachmentButton) {
        downloadMailAttachment(attachmentButton.dataset.mailAttachmentId, attachmentButton.dataset.mailAttachmentName)
          .catch((error) => showToast(error.message));
        return;
      }

      const item = event.target.closest("[data-mail-id]");
      if (!item) return;
      document.querySelectorAll("[data-mail-id]").forEach((node) => node.classList.toggle("active", node === item));
      showMailDetail(item.dataset.mailId).catch((error) => showToast(error.message));
    });

    document.querySelector("[data-mail-form]")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const formData = new FormData(form);
      const to = String(formData.get("to") || "").trim();
      const attachmentFile = form.querySelector("[data-mail-attachment-file]")?.files?.[0];
      const submitButton = form.querySelector('button[type="submit"]');
      if (attachmentFile && attachmentFile.size > 5 * 1024 * 1024) {
        showToast("첨부 파일은 5MB 이하만 가능합니다.");
        return;
      }
      submitButton.disabled = true;
      submitButton.textContent = "보내는 중...";
      try {
        const attachment = attachmentFile ? {
          name: attachmentFile.name,
          contentType: attachmentFile.type || "application/octet-stream",
          data: await fileAsBase64(attachmentFile),
        } : null;
        const response = await apiRequest("/api/mail/messages", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            to, subject: formData.get("subject"), body: formData.get("body"),
            grade: formData.get("grade"), attachment,
          }),
        });
        const result = await response.json();
        if (!result.ok) throw new Error(result.message || "메일을 보내지 못했습니다.");
        form.reset();
        setMailAttachment(null);
        addLog("메일 발송");
        showToast(result.message);
        await renderMails("sent");
      } catch (error) {
        showToast(error.message);
      } finally {
        submitButton.disabled = false;
        submitButton.textContent = "메일 보내기";
      }
    });
  }

  async function init() {
    initEmbeddedNavigation();

    const page = document.body.dataset.page;
    if (!page || page === "login") return;

    const user = await requireLogin();
    if (!user) return;

    const next = state();
    next.profile.name = user.name || next.profile.name;
    next.profile.userId = user.id || next.profile.userId;
    next.profile.role = user.role || next.profile.role;
    save(next);
    archiveLogsIfNeeded();

    if (page === "main") renderMain(state(), user);
    if (page === "documents") initDocuments();
    if (page === "permissions") initPermissions();
    if (page === "users") initUsers();
    if (page === "grades") initGrades();
    if (page === "logs") initLogs();
    if (page === "transfers") initTransfers();
    if (page === "mypage") initMypage();
    if (page === "admin-settings") initAdminSettings();
    if (page === "mail") await initMail();
  }

  return {
    init,
    core: { state, save, todayKey, nextId, escapeHTML, showToast, addLog },
  };
})();

document.addEventListener("DOMContentLoaded", App.init);
