const SchedulePage = (() => {
  const weekdays = ["일", "월", "화", "수", "목", "금", "토"];
  const groups = [
    { category: "회사", title: "회사 일정", className: "company" },
    { category: "팀", title: "팀 일정", className: "team" },
    { category: "개인", title: "개인 일정", className: "personal" },
  ];

  function init() {
    if (document.body.dataset.page !== "schedule") return;

    const { state, save, todayKey, nextId, escapeHTML, showToast } = App.core;
    const data = state();
    const calendar = document.querySelector("[data-calendar]");
    const title = document.querySelector("[data-calendar-title]");
    const list = document.querySelector("[data-schedule-list]");
    const monthInput = document.querySelector("[data-calendar-month]");
    const selectedDateTitle = document.querySelector("[data-selected-date-title]");
    const dialog = document.querySelector("[data-schedule-dialog]");
    const form = document.querySelector("[data-schedule-form]");
    const formTitle = document.querySelector("[data-schedule-form-title]");

    if (!calendar || !title || !list || !monthInput || !selectedDateTitle || !dialog || !form || !formTitle) return;

    const today = new Date();
    let viewDate = new Date(today.getFullYear(), today.getMonth(), 1);
    let selectedDate = todayKey();

    const scheduleCategory = (schedule) => {
      if (schedule?.category) return schedule.category;
      if (schedule?.type === "보안") return "회사";
      if (schedule?.type === "승인") return "팀";
      return "개인";
    };

    const toDateValue = (year, month, day) => (
      `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`
    );

    const parseDate = (value) => {
      const [year, month, day] = value.split("-").map(Number);
      return new Date(year, month - 1, day);
    };

    const dateLabel = (value) => {
      const date = parseDate(value);
      const prefix = value === todayKey() ? "오늘 · " : "";
      return `${prefix}${date.getMonth() + 1}월 ${date.getDate()}일 (${weekdays[date.getDay()]})`;
    };

    const monthValue = (date) => (
      `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`
    );

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
        const date = toDateValue(year, month, day);
        const daySchedules = data.schedules
          .filter((schedule) => schedule.date === date)
          .sort((a, b) => a.time.localeCompare(b.time));
        const visibleSchedules = daySchedules.slice(0, 2);
        const chips = visibleSchedules.map((schedule) => (
          `<span class="schedule-chip">${escapeHTML(schedule.time)} ${escapeHTML(schedule.title)}</span>`
        )).join("");
        const moreChip = daySchedules.length > visibleSchedules.length
          ? `<span class="schedule-chip">+${daySchedules.length - visibleSchedules.length}개 일정</span>`
          : "";
        const classes = [
          "calendar-day",
          isCurrentMonth && day === today.getDate() ? "today" : "",
          date === selectedDate ? "selected" : "",
        ].filter(Boolean).join(" ");

        cells.push(`
          <button class="${classes}" type="button" data-schedule-date="${date}" aria-label="${dateLabel(date)} 일정 보기">
            <span class="day-number">${day}</span>
            ${chips}
            ${moreChip}
          </button>
        `);
      }

      calendar.innerHTML = cells.join("");
    };

    const renderSelectedSchedules = () => {
      selectedDateTitle.textContent = dateLabel(selectedDate);
      list.innerHTML = groups.map((group) => {
        const items = data.schedules
          .filter((schedule) => schedule.date === selectedDate && scheduleCategory(schedule) === group.category)
          .sort((a, b) => a.time.localeCompare(b.time));
        const rows = items.length > 0 ? items.map((schedule) => `
          <li class="schedule-section-item">
            <div>
              <strong>${escapeHTML(schedule.time)} · ${escapeHTML(schedule.title)}</strong>
              <span>${escapeHTML(schedule.description || "설명 없음")}</span>
            </div>
            <div class="schedule-item-actions">
              <button class="icon-button" type="button" data-schedule-edit="${schedule.id}" title="일정 수정" aria-label="${escapeHTML(schedule.title)} 수정">✎</button>
              <button class="icon-button danger" type="button" data-schedule-delete="${schedule.id}" title="일정 삭제" aria-label="${escapeHTML(schedule.title)} 삭제">×</button>
            </div>
          </li>
        `).join("") : '<li class="schedule-empty">등록된 일정이 없습니다.</li>';

        return `
          <section class="schedule-section ${group.className}">
            <div class="schedule-section-title">
              <span>${group.title}</span>
              <button
                class="icon-button schedule-add-button"
                type="button"
                data-schedule-add="${group.category}"
                title="${group.title} 추가"
                aria-label="${group.title} 추가"
              >+</button>
            </div>
            <ol class="schedule-section-list">${rows}</ol>
          </section>
        `;
      }).join("");
    };

    const render = () => {
      renderCalendar();
      renderSelectedSchedules();
    };

    const openForm = (schedule = null, defaultCategory = "회사") => {
      form.reset();
      const scheduleIdField = form.elements.namedItem("scheduleId");
      const dateField = form.elements.namedItem("date");
      const timeField = form.elements.namedItem("time");
      const categoryField = form.elements.namedItem("category");
      const titleField = form.elements.namedItem("title");
      const descriptionField = form.elements.namedItem("description");
      scheduleIdField.value = schedule?.id || "";
      dateField.value = schedule?.date || selectedDate;
      timeField.value = schedule?.time || "09:00";
      categoryField.value = schedule ? scheduleCategory(schedule) : defaultCategory;
      titleField.value = schedule?.title || "";
      descriptionField.value = schedule?.description || "";
      formTitle.textContent = schedule ? "일정 수정" : "새 일정";
      dialog.hidden = false;
      titleField.focus();
    };

    const closeForm = () => {
      dialog.hidden = true;
    };

    calendar.addEventListener("click", (event) => {
      const dayButton = event.target.closest("[data-schedule-date]");
      if (!dayButton) return;
      selectedDate = dayButton.dataset.scheduleDate;
      render();
    });

    document.querySelector("[data-schedule-close]")?.addEventListener("click", closeForm);
    document.querySelector("[data-schedule-cancel]")?.addEventListener("click", closeForm);
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) closeForm();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !dialog.hidden) closeForm();
    });

    list.addEventListener("click", (event) => {
      const addButton = event.target.closest("[data-schedule-add]");
      const editButton = event.target.closest("[data-schedule-edit]");
      const deleteButton = event.target.closest("[data-schedule-delete]");
      if (addButton) {
        openForm(null, addButton.dataset.scheduleAdd);
        return;
      }
      if (editButton) {
        const schedule = data.schedules.find((item) => item.id === Number(editButton.dataset.scheduleEdit));
        if (schedule) openForm(schedule);
        return;
      }
      if (!deleteButton) return;

      const scheduleId = Number(deleteButton.dataset.scheduleDelete);
      const schedule = data.schedules.find((item) => item.id === scheduleId);
      if (!schedule || !window.confirm(`'${schedule.title}' 일정을 삭제할까요?`)) return;
      data.schedules = data.schedules.filter((item) => item.id !== scheduleId);
      save(data);
      render();
      showToast("일정을 삭제했습니다.");
    });

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const formData = new FormData(form);
      const scheduleId = Number(formData.get("scheduleId"));
      const schedule = {
        id: scheduleId || nextId(data.schedules),
        date: String(formData.get("date")),
        time: String(formData.get("time")),
        category: String(formData.get("category")),
        type: String(formData.get("category")),
        title: String(formData.get("title")).trim(),
        description: String(formData.get("description")).trim(),
      };
      if (!schedule.title) return;

      const existingIndex = data.schedules.findIndex((item) => item.id === scheduleId);
      if (existingIndex >= 0) data.schedules[existingIndex] = schedule;
      else data.schedules.push(schedule);
      selectedDate = schedule.date;
      const savedDate = parseDate(schedule.date);
      viewDate = new Date(savedDate.getFullYear(), savedDate.getMonth(), 1);
      save(data);
      closeForm();
      render();
      showToast(existingIndex >= 0 ? "일정을 수정했습니다." : "일정을 등록했습니다.");
    });

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
      selectedDate = todayKey();
      render();
    });

    monthInput.addEventListener("change", () => {
      const [year, month] = monthInput.value.split("-").map(Number);
      if (!year || !month) return;
      viewDate = new Date(year, month - 1, 1);
      renderCalendar();
    });

    render();
  }

  return { init };
})();

document.addEventListener("DOMContentLoaded", SchedulePage.init);
