const AUTO_REFRESH_INTERVAL_MS = 5000;
const SCROLL_STORAGE_KEY = "reaper-mcp-backlog-scroll-position";

const state = {
  tasks: [],
  refreshing: false,
  openBugPanels: new Set(),
  filters: {
    search: "",
    status: "all",
    category: "all",
    priority: "all"
  }
};

const elements = {
  summary: document.querySelector("#summary"),
  progressBar: document.querySelector("#progress-bar"),
  progressLabel: document.querySelector("#progress-label"),
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
  const pending = state.tasks.length - completed;
  const percentage = state.tasks.length ? Math.round((completed / state.tasks.length) * 100) : 0;
  const categories = new Set(state.tasks.map(task => task.category)).size;
  const metrics = [
    ["Total tasks", state.tasks.length],
    ["Completed", completed],
    ["Pending", pending],
    ["Categories", categories]
  ];

  elements.summary.replaceChildren(...metrics.map(([name, value]) => {
    const card = document.createElement("div");
    card.className = "summary-card";
    card.innerHTML = `<span>${name}</span><strong>${value}</strong>`;
    return card;
  }));

  elements.progressLabel.textContent = `${completed} / ${state.tasks.length} · ${percentage}%`;
  elements.progressBar.style.width = `${percentage}%`;
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
  card.classList.add(task.status);
  fragment.querySelector(".task-id").textContent = task.id;

  const status = fragment.querySelector(".status-pill");
  status.textContent = label(task.status);
  status.classList.add(task.status);

  fragment.querySelector(".task-title").textContent = task.title;
  fragment.querySelector(".task-description").textContent = task.description;

  const meta = fragment.querySelector(".task-meta");
  for (const value of [task.category, `${task.priority} priority`, task.capability]) {
    const pill = document.createElement("span");
    pill.className = "meta-pill";
    pill.textContent = label(value);
    meta.append(pill);
  }

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
      if (bugs.open) {
        state.openBugPanels.add(task.id);
      } else {
        state.openBugPanels.delete(task.id);
      }
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

function restoreScrollPosition(position) {
  requestAnimationFrame(() => window.scrollTo(0, position));
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
    renderSummary();
    populateCategories();
    renderTasks();
    elements.errorState.hidden = true;

    if (preserveScroll) restoreScrollPosition(scrollPosition);
  } catch (error) {
    elements.errorState.hidden = false;
    elements.errorState.textContent = `Could not load backlog.json: ${error.message}. Serve this directory through a local web server.`;
  } finally {
    state.refreshing = false;
  }
}

async function initialize() {
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";

  const savedScrollPosition = Number(sessionStorage.getItem(SCROLL_STORAGE_KEY)) || 0;
  bindFilters();
  await refreshBacklog();
  restoreScrollPosition(savedScrollPosition);

  window.addEventListener("pagehide", saveScrollPosition);
  window.setInterval(
    () => refreshBacklog({ preserveScroll: true }),
    AUTO_REFRESH_INTERVAL_MS
  );
}

initialize();
