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
      { id: 1, time: "09:30", title: "전사 보안 공지 확인", description: "월간 보안 정책 공유", type: "보안", category: "회사" },
      { id: 2, time: "10:30", title: "문서 승인 회의", description: "최고기밀 문서 다운로드 승인 검토", type: "승인", category: "팀" },
      { id: 3, time: "17:30", title: "백업 확인", description: "암호화 문서 백업 상태 점검", type: "시스템", category: "개인" },
      { id: 4, time: "11:00", title: "개인정보 교육", description: "사내 보안 교육 참석", type: "교육", category: "회사" },
      { id: 5, time: "14:00", title: "보안 점검", description: "외부 IP 차단 로그와 접근 정책 확인", type: "보안", category: "팀" },
      { id: 6, time: "18:00", title: "메일 회신", description: "승인 요청 메일 확인", type: "업무", category: "개인" },
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
    if (!Array.isArray(next.schedules)) {
      next.schedules = clone(seed.schedules);
    } else {
      next.schedules = next.schedules.map((schedule, index) => ({
        ...schedule,
        category: seed.schedules.find((item) => item.time === schedule.time && item.title === schedule.title)?.category
          || schedule.category
          || (schedule.type === "보안" ? "회사" : schedule.type === "승인" ? "팀" : "개인"),
      }));
      seed.schedules.forEach((schedule) => {
        if (!next.schedules.some((item) => item.time === schedule.time && item.title === schedule.title)) {
          next.schedules.push(clone(schedule));
        }
      });
      const seenSchedules = new Set();
      next.schedules = next.schedules.filter((schedule) => {
        const key = `${schedule.time}-${schedule.title}`;
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
      scheduleList.innerHTML = next.schedules.slice(0, 3).map((schedule) => `
        <li>
          <strong>${schedule.time} · ${schedule.title}</strong>
          <span>${schedule.description}</span>
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

  function setAlertView(view) {
    const isDetail = view === "detail";
    const isSettings = view === "settings";
    document.querySelector("[data-alert-list-view]")?.classList.toggle("active", view === "list");
    document.querySelector("[data-alert-detail-view]")?.classList.toggle("active", isDetail);
    document.querySelector("[data-alert-settings-view]")?.classList.toggle("active", isSettings);
    document.querySelector("[data-alert-settings]")?.classList.toggle("active", isSettings);
  }

  function alertItemsByFilter(next, filter) {
    if (filter === "읽지 않음") return next.alerts.filter((alert) => !alert.read);
    if (filter === "전체") return next.alerts;
    return next.alerts.filter((alert) => alert.type === filter);
  }

  function renderAlerts(next, filter = "전체") {
    const list = document.querySelector("[data-alerts]");
    const title = document.querySelector("[data-alert-title]");
    if (!list || !title) return;
    const items = alertItemsByFilter(next, filter);

    setAlertView("list");
    title.textContent = filter === "전체" ? "전체 알림" : filter;
    document.querySelectorAll("[data-alert-filter]").forEach((button) => {
      button.classList.toggle("active", button.dataset.alertFilter === filter);
    });

    if (items.length === 0) {
      list.innerHTML = '<li class="notice-item"><strong>알림이 없습니다.</strong><div class="notice-meta">조건에 맞는 알림이 없습니다.</div></li>';
      return;
    }

    list.innerHTML = items.map((alert) => `
      <li class="notice-item" data-alert-id="${alert.id}">
        <strong>${alert.read ? "" : "● "}${alert.title} ${alert.read ? '<span class="badge">읽음</span>' : '<span class="badge warn">새 알림</span>'}</strong>
        <div class="notice-meta">${alert.type} · ${alert.read ? "처리됨" : "확인 필요"}</div>
        <div class="notice-meta">${alert.message}</div>
      </li>
    `).join("");
  }

  function showAlertDetail(alertId) {
    const next = state();
    const alert = next.alerts.find((item) => String(item.id) === String(alertId));
    const detail = document.querySelector("[data-alert-detail]");
    if (!alert || !detail) return;

    detail.innerHTML = `
      <div class="notice-detail-header">
        <div>
          <h2>${alert.title}</h2>
          <p class="notice-meta">분류: ${alert.type}</p>
          <p class="notice-meta">상태: ${alert.read ? "읽음" : "새 알림"}</p>
        </div>
        <div class="notice-detail-actions">
          <button class="secondary-button small-button" type="button" data-alert-back>목록으로</button>
          <button class="primary-button small-button" type="button" data-read-alert="${alert.id}">읽음 처리</button>
        </div>
      </div>
      <div class="notice-detail-body">
        <p>${alert.message}</p>
        <p class="notice-meta" style="margin-top: 18px;">관련 작업: ${alert.type === "승인 요청" ? "문서 승인 검토" : alert.type === "보안 이벤트" ? "접근 로그 확인" : "공지 확인"}</p>
      </div>
    `;
    setAlertView("detail");
  }

  function initAlerts() {
    const requestedFilter = new URLSearchParams(window.location.search).get("filter");
    const availableFilters = ["전체", "읽지 않음", "승인 요청", "보안 이벤트", "시스템 공지"];
    let currentFilter = availableFilters.includes(requestedFilter) ? requestedFilter : "전체";
    renderAlerts(state(), currentFilter);

    document.querySelectorAll("[data-alert-filter]").forEach((button) => {
      button.addEventListener("click", () => {
        currentFilter = button.dataset.alertFilter;
        renderAlerts(state(), currentFilter);
      });
    });

    document.querySelector("[data-alert-settings]")?.addEventListener("click", () => {
      document.querySelectorAll("[data-alert-filter]").forEach((button) => button.classList.remove("active"));
      setAlertView("settings");
    });

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
      const backButton = event.target.closest("[data-alert-back]");
      if (backButton) {
        renderAlerts(state(), currentFilter);
        return;
      }

      const item = event.target.closest("[data-alert-id]");
      if (item) {
        document.querySelectorAll("[data-alert-id]").forEach((node) => node.classList.toggle("active", node === item));
        showAlertDetail(item.dataset.alertId);
        return;
      }

      const button = event.target.closest("[data-read-alert]");
      if (!button) return;
      const updated = state();
      const alert = updated.alerts.find((item) => String(item.id) === button.dataset.readAlert);
      alert.read = true;
      save(updated);
      if (document.querySelector("[data-alert-detail-view]")?.classList.contains("active")) {
        showAlertDetail(alert.id);
      } else {
        renderAlerts(updated, currentFilter);
      }
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

  function mailAddressForUser(user) {
    const id = user.userId || user.id || "user";
    return `${id}@datavault.local`;
  }

  function renderMailRecipients(next) {
    const target = document.querySelector("[data-mail-recipients]");
    if (!target) return;
    const options = next.users.map((user) => {
      const address = mailAddressForUser(user);
      return `<option value="${address}" label="${user.name}"></option>`;
    }).join("") + '<option value="external@gmail.com" label="외부메일 테스트"></option>';
    target.innerHTML = options;
  }

  function renderMailDocuments(next) {
    const select = document.querySelector("[data-mail-documents]");
    if (!select) return;
    select.innerHTML = '<option value="">첨부 없음</option>' + next.documents.map((doc) => (
      `<option value="${doc.name}">${doc.name} · ${doc.grade}</option>`
    )).join("");
  }

  function setMailView(view) {
    const isCompose = view === "compose";
    const isDetail = view === "detail";
    document.querySelector("[data-mail-list-view]")?.classList.toggle("active", view === "list");
    document.querySelector("[data-mail-detail-view]")?.classList.toggle("active", isDetail);
    document.querySelector("[data-mail-compose-view]")?.classList.toggle("active", isCompose);
    document.querySelector("[data-mail-compose]")?.classList.toggle("active", isCompose);
  }

  function renderMails(box = "inbox") {
    const next = state();
    const list = document.querySelector("[data-mail-list]");
    const title = document.querySelector("[data-mail-title]");
    if (!list || !title) return;

    setMailView("list");
    document.querySelectorAll("[data-mail-box]").forEach((button) => {
      button.classList.toggle("active", button.dataset.mailBox === box);
    });
    title.textContent = box === "inbox" ? "받은 메일함" : "보낸 메일함";
    const mails = next.mails.filter((mail) => mail.box === box);

    if (mails.length === 0) {
      list.innerHTML = '<li class="mail-item"><strong>메일이 없습니다.</strong><div class="mail-meta">새 메일을 작성해보세요.</div></li>';
      return;
    }

    list.innerHTML = mails.map((mail) => `
      <li class="mail-item" data-mail-id="${mail.id}">
        <strong>${mail.read ? "" : "● "}${mail.subject}</strong>
        <div class="mail-meta">${box === "inbox" ? mail.from : mail.to} · ${mail.sentAt} · ${mail.grade}</div>
      </li>
    `).join("");
  }

  function showMailDetail(mailId) {
    const next = state();
    const mail = next.mails.find((item) => String(item.id) === String(mailId));
    const detail = document.querySelector("[data-mail-detail]");
    if (!mail || !detail) return;

    mail.read = true;
    save(next);
    detail.innerHTML = `
      <div class="mail-detail-header">
        <div>
          <h2>${mail.subject}</h2>
          <p class="mail-meta">보낸 사람: ${mail.from}</p>
          <p class="mail-meta">받는 사람: ${mail.to}</p>
          <p class="mail-meta">보안 등급: ${mail.grade} · ${mail.sentAt}</p>
        </div>
        <button class="secondary-button small-button" type="button" data-mail-back>목록으로</button>
      </div>
      <div class="mail-detail-body">
        <p>${mail.body}</p>
        <p class="mail-meta" style="margin-top: 18px;">첨부 문서: ${mail.attachment || "없음"}</p>
      </div>
    `;
    setMailView("detail");
    addLog("사내메일 열람");
  }

  function initMail() {
    const next = state();
    renderMailRecipients(next);
    renderMailDocuments(next);
    renderMails("inbox");

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
        renderMails(button.dataset.mailBox);
      });
    });

    document.querySelector("[data-mail-compose]")?.addEventListener("click", () => {
      document.querySelectorAll("[data-mail-box]").forEach((button) => button.classList.remove("active"));
      setMailView("compose");
    });

    document.addEventListener("click", (event) => {
      const backButton = event.target.closest("[data-mail-back]");
      if (backButton) {
        const activeBox = document.querySelector("[data-mail-box].active")?.dataset.mailBox || "inbox";
        renderMails(activeBox);
        return;
      }

      const item = event.target.closest("[data-mail-id]");
      if (!item) return;
      document.querySelectorAll("[data-mail-id]").forEach((node) => node.classList.toggle("active", node === item));
      showMailDetail(item.dataset.mailId);
    });

    document.querySelector("[data-mail-form]")?.addEventListener("submit", (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const formData = new FormData(form);
      const to = String(formData.get("to") || "").trim();
      const attachmentFile = form.querySelector("[data-mail-attachment-file]")?.files?.[0];
      const attachment = attachmentFile ? attachmentFile.name : "";
      const updated = state();
      const now = new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false });

      if (!String(to).endsWith("@datavault.local")) {
        updated.mails.unshift({
          id: nextId(updated.mails),
          from: mailAddressForUser(updated.profile),
          to,
          subject: formData.get("subject"),
          body: formData.get("body"),
          attachment,
          grade: formData.get("grade"),
          box: "sent",
          read: true,
          sentAt: now,
          status: "외부 발송 차단",
        });
        save(updated);
        addLog("외부메일 발송 차단", "차단");
        showToast("외부 도메인 메일은 차단되었습니다.");
        renderMails("sent");
        return;
      }

      const baseMail = {
        id: nextId(updated.mails),
        from: mailAddressForUser(updated.profile),
        to,
        subject: formData.get("subject"),
        body: formData.get("body"),
        attachment,
        grade: formData.get("grade"),
        read: false,
        sentAt: now,
        status: "발송 완료",
      };
      updated.mails.unshift({ ...baseMail, box: "sent", read: true });
      updated.mails.unshift({ ...baseMail, id: nextId(updated.mails) + 1, box: "inbox" });
      save(updated);
      addLog("사내메일 발송");
      form.reset();
      setMailAttachment(null);
      showToast("사내 메일을 발송했습니다.");
      renderMails("sent");
    });
  }

  function initSchedule() {
    const next = state();
    const calendar = document.querySelector("[data-calendar]");
    const title = document.querySelector("[data-calendar-title]");
    const list = document.querySelector("[data-schedule-list]");
    const monthInput = document.querySelector("[data-calendar-month]");
    if (!calendar || !title || !list || !monthInput) return;

    const today = new Date();
    const weekdays = ["일", "월", "화", "수", "목", "금", "토"];
    let viewDate = new Date(today.getFullYear(), today.getMonth(), 1);

    const scheduleGroups = [
      { category: "회사", title: "회사 일정", className: "company" },
      { category: "팀", title: "팀 일정", className: "team" },
      { category: "개인", title: "개인 일정", className: "personal" },
    ];

    const scheduleCategory = (schedule, index) => {
      if (schedule.category) return schedule.category;
      if (schedule.type === "보안") return "회사";
      if (schedule.type === "승인") return "팀";
      return index % 3 === 0 ? "회사" : index % 3 === 1 ? "팀" : "개인";
    };

    const monthValue = (date) => {
      const month = String(date.getMonth() + 1).padStart(2, "0");
      return `${date.getFullYear()}-${month}`;
    };

    const renderCalendar = () => {
      const year = viewDate.getFullYear();
      const month = viewDate.getMonth();
      const firstDay = new Date(year, month, 1);
      const lastDay = new Date(year, month + 1, 0);
      const isCurrentMonth = year === today.getFullYear() && month === today.getMonth();

      monthInput.value = monthValue(viewDate);
      title.textContent = `${year}년 ${month + 1}월 일정`;
      const cells = weekdays.map((day) => `<div class="calendar-weekday">${day}</div>`);

      for (let index = 0; index < firstDay.getDay(); index += 1) {
        cells.push('<div class="calendar-day muted"></div>');
      }

      for (let day = 1; day <= lastDay.getDate(); day += 1) {
        const isToday = isCurrentMonth && day === today.getDate();
        const visibleSchedules = next.schedules.slice(0, 3);
        const chips = isToday ? visibleSchedules.map((schedule) => (
          `<span class="schedule-chip">${schedule.time} ${schedule.title}</span>`
        )).join("") : "";
        const moreChip = isToday && next.schedules.length > visibleSchedules.length
          ? `<span class="schedule-chip">+${next.schedules.length - visibleSchedules.length}개 일정</span>`
          : "";
        cells.push(`
          <div class="calendar-day${isToday ? " today" : ""}">
            <span class="day-number">${day}</span>
            ${chips}
            ${moreChip}
          </div>
        `);
      }

      calendar.innerHTML = cells.join("");
    };

    renderCalendar();
    list.innerHTML = scheduleGroups.map((group) => {
      const items = next.schedules.filter((schedule, index) => scheduleCategory(schedule, index) === group.category);
      const rows = items.length > 0 ? items.slice(0, 3).map((schedule) => `
        <li class="schedule-section-item">
          <strong>${schedule.time} · ${schedule.title}</strong>
          <span>${schedule.description}</span>
        </li>
      `).join("") : '<li class="schedule-empty">등록된 일정이 없습니다.</li>';

      return `
        <section class="schedule-section ${group.className}">
          <div class="schedule-section-title">${group.title}</div>
          <ol class="schedule-section-list">
            ${rows}
          </ol>
        </section>
      `;
    }).join("");

    document.querySelector("[data-calendar-prev]")?.addEventListener("click", () => {
      viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1);
      renderCalendar();
    });

    document.querySelector("[data-calendar-next]")?.addEventListener("click", () => {
      viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1);
      renderCalendar();
    });

    document.querySelector("[data-calendar-today]")?.addEventListener("click", () => {
      viewDate = new Date(today.getFullYear(), today.getMonth(), 1);
      renderCalendar();
    });

    const syncSelectedMonth = () => {
      const [year, month] = monthInput.value.split("-").map(Number);
      if (!year || !month) return;
      viewDate = new Date(year, month - 1, 1);
      renderCalendar();
    };

    monthInput.addEventListener("change", syncSelectedMonth);
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
    if (page === "alerts") initAlerts();
    if (page === "transfers") initTransfers();
    if (page === "mypage") initMypage();
    if (page === "admin-settings") initAdminSettings();
    if (page === "mail") initMail();
    if (page === "schedule") initSchedule();
  }

  return { init };
})();

document.addEventListener("DOMContentLoaded", App.init);
