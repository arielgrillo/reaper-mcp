const AUTO_REFRESH_INTERVAL_MS = 5000;
const SCROLL_STORAGE_KEY = "reaper-mcp-backlog-scroll-position";
const EXPANSION_STORAGE_KEY = "reaper-mcp-backlog-expanded-sections";

const state = {
  tasks: [],
  refreshing: false,
  nextRefreshAt: 0,
  openTaskSections: new Set(),
  openBugPanels: new Set(),
  bugSummaryOpen: false,
  filters: {
    search: "",
    status: "all",
    category: "all",
    priority: "all"
  }
};

const elements = {
  summary: document.querySelector("#summary"),
  bugSummary: document.querySelector("#bug-summary"),
  bugSummaryCounts: document.querySelector("#bug-summary-counts"),
  bugSummaryList: document.querySelector("#bug-summary-list"),
  categorySummaryList: document.querySelector("#category-summary-list"),
  progressBar: document.querySelector("#progress-bar"),
  progressLabel: document.querySelector("#progress-label"),
  refreshRing: document.querySelector("#refresh-ring"),
  refreshSeconds: document.querySelector("#refresh-seconds"),
  search: document.querySelector("#search"),
  status: document.querySelector("#status-filter"),
  category: document.querySelector("#category-filter"),
  priority: document.querySelector("#priority-filter"),
  resultCount: document.querySelector("#result-count"),
  taskList: document.querySelector("#task-list"),
  emptyState: document.querySelector("#empty-state"),
  errorState: document.querySelector("#error-state"),
  template: document.querySelector("#task-template")
};

function label(value) {
  return value.replaceAll("-", " ").replace(/\b\w/g, character => character.toUpperCase());
}

function renderSummary() {
  const completed = state.tasks.filter(task => task.status === "completed").length;
  const testing = state.tasks.filter(task => task.status === "testing").length;
  const pending = state.tasks.filter(task => task.status === "pending").length;
  const percentage = state.tasks.length ? Math.round((completed / state.tasks.length) * 100) : 0;
  const categories = new Set(state.tasks.map(task => task.category)).size;
  const metrics = [
    ["Total tasks", state.tasks.length, "total"],
    ["Completed", completed, "completed"],
    ["Testing", testing, "testing"],
    ["Pending", pending, "pending"],
    ["Categories", categories, "categories"]
  ];

  elements.summary.replaceChildren(...metrics.map(([name, value, status]) => {
    const card = document.createElement("div");
    card.className = `summary-card summary-card-${status}`;
    card.innerHTML = `<span>${name}</span><strong>${value}</strong>`;
    return card;
  }));

  elements.progressLabel.textContent = `${completed} / ${state.tasks.length} · ${percentage}%`;
  elements.progressBar.style.width = `${percentage}%`;
}

function allBugs() {
  return state.tasks.flatMap(task => (task.bugs ?? []).map(bug => ({
    ...bug,
    taskId: task.id,
    taskTitle: task.title
  })));
}

function renderBugSummary() {
  const bugs = allBugs();
  const statusCounts = new Map();

  for (const bug of bugs) {
    statusCounts.set(bug.status, (statusCounts.get(bug.status) ?? 0) + 1);
  }

  const countParts = [`${bugs.length} total`];
  for (const status of ["open", "fixed", "wont-fix"]) {
    if (status !== "wont-fix" || statusCounts.has(status)) {
      countParts.push(`${statusCounts.get(status) ?? 0} ${status}`);
    }
  }
  elements.bugSummaryCounts.textContent = countParts.join(" · ");
  elements.bugSummary.open = state.bugSummaryOpen;

  const statusOrder = ["open", "fixed", "wont-fix"];
  const statuses = [...statusCounts.keys()].sort((left, right) => {
    const leftIndex = statusOrder.indexOf(left);
    const rightIndex = statusOrder.indexOf(right);
    return (leftIndex < 0 ? statusOrder.length : leftIndex)
      - (rightIndex < 0 ? statusOrder.length : rightIndex)
      || left.localeCompare(right);
  });
  const groups = statuses.map(status => {
    const group = document.createElement("section");
    group.className = `bug-summary-group bug-summary-group-${status}`;

    const heading = document.createElement("h3");
    heading.textContent = `${label(status)} (${statusCounts.get(status)})`;
    group.append(heading);

    for (const bug of bugs.filter(entry => entry.status === status)) {
      const item = document.createElement("button");
      item.type = "button";
      item.className = `bug-summary-item bug-summary-item-${status}`;
      item.addEventListener("click", () => navigateToTask(bug.taskId));

      const identity = document.createElement("span");
      identity.className = "bug-summary-identity";
      const bugId = document.createElement("code");
      bugId.textContent = bug.id;
      const bugStatus = document.createElement("span");
      bugStatus.className = `bug-status bug-status-${status}`;
      bugStatus.textContent = label(status);
      identity.append(bugId, bugStatus);

      const title = document.createElement("strong");
      title.textContent = bug.title ?? bug.description;

      const owner = document.createElement("span");
      owner.className = "bug-summary-owner";
      owner.textContent = `${bug.taskId} — ${bug.taskTitle}`;

      item.append(identity, title, owner);
      group.append(item);
    }

    return group;
  });

  if (groups.length) {
    elements.bugSummaryList.replaceChildren(...groups);
  } else {
    const empty = document.createElement("p");
    empty.className = "bug-summary-empty";
    empty.textContent = "No bugs recorded.";
    elements.bugSummaryList.replaceChildren(empty);
  }
}

function renderCategorySummary() {
  const categoryCounts = new Map();

  for (const task of state.tasks) {
    const counts = categoryCounts.get(task.category) ?? {
      total: 0,
      pending: 0
    };
    counts.total += 1;
    counts.pending += task.status === "pending" ? 1 : 0;
    categoryCounts.set(task.category, counts);
  }

  const cards = [...categoryCounts.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([category, counts]) => {
      const card = document.createElement("article");
      card.className = "category-summary-card";

      const name = document.createElement("strong");
      name.textContent = label(category);

      const values = document.createElement("span");
      values.innerHTML = `<b>${counts.total}</b> total · <b>${counts.pending}</b> pending`;

      card.append(name, values);
      return card;
    });

  elements.categorySummaryList.replaceChildren(...cards);
}

function populateCategories() {
  const categories = [...new Set(state.tasks.map(task => task.category))].sort();
  const selectedCategory = elements.category.value;
  const allOption = elements.category.querySelector('option[value="all"]');
  elements.category.replaceChildren(allOption);

  for (const category of categories) {
    const option = document.createElement("option");
    option.value = category;
    option.textContent = label(category);
    elements.category.append(option);
  }

  elements.category.value = categories.includes(selectedCategory) ? selectedCategory : "all";
  state.filters.category = elements.category.value;
}

function matchesFilters(task) {
  const query = state.filters.search.toLowerCase();
  const bugs = (task.bugs ?? []).flatMap(bug => [bug.id, bug.status, bug.description]);
  const searchable = [task.id, task.title, task.capability, task.description, ...bugs].join(" ").toLowerCase();
  return (!query || searchable.includes(query))
    && (state.filters.status === "all" || task.status === state.filters.status)
    && (state.filters.category === "all" || task.category === state.filters.category)
    && (state.filters.priority === "all" || task.priority === state.filters.priority);
}

function createTaskCard(task) {
  const fragment = elements.template.content.cloneNode(true);
  const card = fragment.querySelector(".task-card");
  card.dataset.taskId = task.id;
  card.classList.add(task.status);
  fragment.querySelector(".task-id").textContent = task.id;

  const status = fragment.querySelector(".status-pill");
  status.textContent = label(task.status);
  status.classList.add(task.status);

  fragment.querySelector(".task-title").textContent = task.title;
  fragment.querySelector(".task-description").textContent = task.description;

  const meta = fragment.querySelector(".task-meta");
  const metadata = [
    task.category,
    `${task.priority} priority`,
    task.capability
  ].filter(value => typeof value === "string" && value.length > 0);

  for (const value of metadata) {
    const pill = document.createElement("span");
    pill.className = "meta-pill";
    pill.textContent = label(value);
    meta.append(pill);
  }

  const criteriaPanel = fragment.querySelector("details");
  criteriaPanel.className = "criteria-panel";
  criteriaPanel.open = state.openTaskSections.has(task.id);
  criteriaPanel.addEventListener("toggle", () => {
    updateExpandedSet(state.openTaskSections, task.id, criteriaPanel.open);
  });

  const criteria = fragment.querySelector(".criteria");
  for (const criterion of task.acceptance_criteria) {
    const item = document.createElement("li");
    item.textContent = criterion;
    criteria.append(item);
  }

  if (task.bugs?.length) {
    const bugs = document.createElement("details");
    bugs.className = "bugs";
    bugs.open = state.openBugPanels.has(task.id);
    bugs.addEventListener("toggle", () => {
      updateExpandedSet(state.openBugPanels, task.id, bugs.open);
    });

    const heading = document.createElement("summary");
    heading.textContent = `Bugs (${task.bugs.length})`;
    bugs.append(heading);

    for (const bug of task.bugs) {
      const item = document.createElement("article");
      item.className = `bug bug-${bug.status}`;

      const topline = document.createElement("div");
      topline.className = "bug-topline";

      const id = document.createElement("code");
      id.textContent = bug.id;

      const status = document.createElement("span");
      status.className = `bug-status bug-status-${bug.status}`;
      status.textContent = label(bug.status);

      topline.append(id, status);

      const description = document.createElement("p");
      description.textContent = bug.description;

      const metadata = document.createElement("p");
      metadata.className = "bug-metadata";
      metadata.textContent = `Discovered during ${label(bug.discovered_during)}`;

      if (bug.fixed_in) {
        const separator = document.createTextNode(" · Fixed in ");
        const commit = document.createElement("code");
        commit.textContent = bug.fixed_in.slice(0, 7);
        metadata.append(separator, commit);
      }

      item.append(topline, description, metadata);
      bugs.append(item);
    }

    fragment.querySelector(".dependencies").before(bugs);
  }

  const dependencies = fragment.querySelector(".dependencies");
  if (task.depends_on.length) {
    dependencies.innerHTML = `Depends on: ${task.depends_on.map(id => `<code>${id}</code>`).join(", ")}`;
  } else {
    dependencies.textContent = "No dependencies";
  }

  return fragment;
}

function renderTasks() {
  const visibleTasks = state.tasks.filter(matchesFilters);
  elements.taskList.replaceChildren(...visibleTasks.map(createTaskCard));
  elements.resultCount.textContent = `${visibleTasks.length} of ${state.tasks.length}`;
  elements.emptyState.hidden = visibleTasks.length !== 0;
}

function navigateToTask(taskId) {
  if (!state.tasks.some(task => task.id === taskId)) return;

  state.filters = {
    search: "",
    status: "all",
    category: "all",
    priority: "all"
  };
  elements.search.value = "";
  elements.status.value = "all";
  elements.category.value = "all";
  elements.priority.value = "all";
  state.openTaskSections.add(taskId);
  state.openBugPanels.add(taskId);
  saveExpansionState();
  renderTasks();

  const card = elements.taskList.querySelector(`[data-task-id="${taskId}"]`);
  if (!card) return;

  card.scrollIntoView({ behavior: "smooth", block: "center" });
  card.classList.add("task-card-targeted");
  window.setTimeout(() => card.classList.remove("task-card-targeted"), 2200);
}

function bindFilters() {
  elements.search.addEventListener("input", event => {
    state.filters.search = event.target.value.trim();
    renderTasks();
  });

  for (const [name, element] of [
    ["status", elements.status],
    ["category", elements.category],
    ["priority", elements.priority]
  ]) {
    element.addEventListener("change", event => {
      state.filters[name] = event.target.value;
      renderTasks();
    });
  }
}

function saveScrollPosition() {
  sessionStorage.setItem(SCROLL_STORAGE_KEY, String(window.scrollY));
}

function updateExpandedSet(expandedSet, taskId, isOpen) {
  if (isOpen) {
    expandedSet.add(taskId);
  } else {
    expandedSet.delete(taskId);
  }

  saveExpansionState();
}

function saveExpansionState() {
  sessionStorage.setItem(EXPANSION_STORAGE_KEY, JSON.stringify({
    taskSections: [...state.openTaskSections],
    bugPanels: [...state.openBugPanels],
    bugSummaryOpen: state.bugSummaryOpen
  }));
}

function restoreExpansionState() {
  try {
    const savedState = JSON.parse(
      sessionStorage.getItem(EXPANSION_STORAGE_KEY) ?? "{}"
    );
    state.openTaskSections = new Set(savedState.taskSections ?? []);
    state.openBugPanels = new Set(savedState.bugPanels ?? []);
    state.bugSummaryOpen = savedState.bugSummaryOpen ?? false;
  } catch {
    state.openTaskSections.clear();
    state.openBugPanels.clear();
    state.bugSummaryOpen = false;
  }
}

function pruneExpansionState() {
  const taskIds = new Set(state.tasks.map(task => task.id));
  state.openTaskSections = new Set(
    [...state.openTaskSections].filter(taskId => taskIds.has(taskId))
  );
  state.openBugPanels = new Set(
    [...state.openBugPanels].filter(taskId => taskIds.has(taskId))
  );
  saveExpansionState();
}

function restoreScrollPosition(position) {
  requestAnimationFrame(() => window.scrollTo(0, position));
}

function resetRefreshCountdown() {
  state.nextRefreshAt = Date.now() + AUTO_REFRESH_INTERVAL_MS;
}

function runRefreshLoop() {
  const remainingMilliseconds = Math.max(0, state.nextRefreshAt - Date.now());
  const progress = remainingMilliseconds / AUTO_REFRESH_INTERVAL_MS;
  elements.refreshRing.style.setProperty(
    "--refresh-progress",
    `${progress}turn`
  );
  elements.refreshSeconds.textContent = String(
    Math.max(0, Math.ceil(remainingMilliseconds / 1000))
  );

  if (remainingMilliseconds === 0 && !state.refreshing) {
    refreshBacklog({ preserveScroll: true });
  }

  requestAnimationFrame(runRefreshLoop);
}

async function refreshBacklog({ preserveScroll = false } = {}) {
  if (state.refreshing) return;

  state.refreshing = true;
  const scrollPosition = preserveScroll ? window.scrollY : 0;

  try {
    const response = await fetch(`backlog.json?refresh=${Date.now()}`, {
      cache: "no-store"
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const backlog = await response.json();
    state.tasks = backlog.tasks;
    pruneExpansionState();
    renderSummary();
    renderBugSummary();
    renderCategorySummary();
    populateCategories();
    renderTasks();
    elements.errorState.hidden = true;

    if (preserveScroll) restoreScrollPosition(scrollPosition);
  } catch (error) {
    elements.errorState.hidden = false;
    elements.errorState.textContent = `Could not load backlog.json: ${error.message}. Serve this directory through a local web server.`;
  } finally {
    state.refreshing = false;
    resetRefreshCountdown();
  }
}

async function initialize() {
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";

  const savedScrollPosition = Number(sessionStorage.getItem(SCROLL_STORAGE_KEY)) || 0;
  restoreExpansionState();
  bindFilters();
  elements.bugSummary.addEventListener("toggle", () => {
    state.bugSummaryOpen = elements.bugSummary.open;
    saveExpansionState();
  });
  await refreshBacklog();
  restoreScrollPosition(savedScrollPosition);

  window.addEventListener("pagehide", () => {
    saveScrollPosition();
    saveExpansionState();
  });
  requestAnimationFrame(runRefreshLoop);
}

initialize();
