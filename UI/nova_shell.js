(function () {
  const page = document.body.dataset.page;

  if (!page) {
    return;
  }

  if (window.self !== window.top) {
    document.documentElement.classList.add("is-embedded");
    return;
  }

  if (document.querySelector(".app-header")) {
    return;
  }

  const links = [
    { page: "main", href: "main_ui.html", label: "홈" },
    { page: "documents", href: "document_ui.html", label: "문서" },
    { page: "mail", href: "mail_ui.html", label: "메일" },
    { page: "schedule", href: "schedule_ui.html", label: "캘린더" },
    { page: "logs", href: "log_ui.html", label: "로그" },
    { page: "alerts", href: "notice_ui.html", label: "알림" },
  ];

  const header = document.createElement("header");
  header.className = "app-header";
  header.setAttribute("aria-label", "DataVault 상단 메뉴");

  const brand = document.createElement("a");
  brand.className = "app-brand";
  brand.href = "main_ui.html";
  brand.innerHTML = '<span class="app-brand-mark">D</span><strong>DataVault</strong>';

  const navigation = document.createElement("nav");
  navigation.className = "app-header-nav";
  navigation.setAttribute("aria-label", "주요 서비스");

  links.forEach(function (item) {
    const link = document.createElement("a");
    link.className = "app-header-link";
    link.dataset.shellPage = item.page;
    link.href = item.href;
    link.textContent = item.label;
    navigation.appendChild(link);
  });

  const profile = document.createElement("a");
  profile.className = "app-profile";
  profile.href = "mypage_ui.html";
  profile.innerHTML = '<span class="app-profile-avatar">M</span><span>마이페이지</span>';

  header.append(brand, navigation, profile);
  document.body.prepend(header);

  function updateActiveLink() {
    const activePage = document.body.dataset.page;
    header.querySelectorAll("[data-shell-page]").forEach(function (link) {
      link.classList.toggle("active", link.dataset.shellPage === activePage);
    });
  }

  function requestShellNavigation(event) {
    const link = event.target.closest("a[href]");
    if (!link || !header.contains(link)) {
      return;
    }

    const modified = event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
    if (modified || link.target === "_blank" || event.button !== 0) {
      return;
    }

    if (!document.querySelector("#pageUnderlay")) {
      return;
    }

    event.preventDefault();
    window.postMessage(
      { type: "datavault:navigate", href: link.getAttribute("href") },
      window.location.origin
    );
  }

  updateActiveLink();
  header.addEventListener("click", requestShellNavigation);
  new MutationObserver(updateActiveLink).observe(document.body, {
    attributes: true,
    attributeFilter: ["data-page"],
  });
})();
