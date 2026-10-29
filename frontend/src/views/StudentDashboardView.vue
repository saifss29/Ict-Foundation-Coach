<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { useStore } from "vuex";

const router = useRouter();
const store = useStore();

const loading = ref(false);
const errors = ref({});
const progress = ref(null);
const weakReport = ref(null);
const quizzes = ref(null);
const tasks = ref(null);
const feedback = ref(null);
const events = ref(null);
const now = ref(Date.now());

let controller = null;
let requestVersion = 0;
let clock = null;

const userName = computed(
  () => store.state.auth.currentUser?.name || "Student",
);

const greeting = computed(() => {
  const hour = new Date(now.value).getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
});

function timestamp(value) {
  return value ? new Date(value).getTime() : NaN;
}

function activeItems(items) {
  return (items || []).filter(
    (item) => timestamp(item.deadline_at) > now.value,
  );
}

const activeQuizzes = computed(() => activeItems(quizzes.value));
const activeTasks = computed(() => activeItems(tasks.value));

const upcomingAssignments = computed(() =>
  [
    ...activeQuizzes.value.map((item) => ({
      key: `quiz-${item.id}`,
      title: item.quiz_title,
      classroom: item.classroom_name,
      deadline: item.deadline_at,
      type: "Quiz",
      to: { name: "student-assignments" },
    })),
    ...activeTasks.value.map((item) => ({
      key: `task-${item.id}`,
      title: item.title,
      classroom: item.classroom_name,
      deadline: item.deadline_at,
      type: item.task_type === "practical" ? "Practical" : "Written",
      to: {
        name: "student-learning-assignment-task",
        params: { assignmentId: String(item.id) },
      },
    })),
  ]
    .sort((a, b) => timestamp(a.deadline) - timestamp(b.deadline))
    .slice(0, 3),
);

const weakTopics = computed(
  () => weakReport.value?.weak_topics?.slice(0, 3) || [],
);

const nextEvents = computed(() =>
  (events.value || [])
    .filter((event) => timestamp(event.ends_at) > now.value)
    .sort((a, b) => timestamp(a.starts_at) - timestamp(b.starts_at))
    .slice(0, 3),
);

const latestFeedback = computed(() => feedback.value?.[0] || null);

const stats = computed(() => [
  {
    label: "Topics practised",
    value: progress.value
      ? `${progress.value.summary.completed_topics} / ${progress.value.summary.total_topics}`
      : "—",
    note: "Topics with a completed practice attempt",
    icon: "▤",
    tone: "blue",
    to: { name: "progress" },
  },
  {
    label: "Weak topics",
    value: weakReport.value?.summary?.weak_topics ?? "—",
    note: "Topics that need more practice",
    icon: "◎",
    tone: "red",
    to: { name: "progress" },
  },
  {
    label: "Assigned quizzes",
    value: quizzes.value === null ? "—" : activeQuizzes.value.length,
    note: "Quizzes with a deadline still ahead",
    icon: "✓",
    tone: "green",
    to: { name: "student-assignments" },
  },
  {
    label: "Learning tasks",
    value: tasks.value === null ? "—" : activeTasks.value.length,
    note: "Written or practical tasks still open",
    icon: "✎",
    tone: "gold",
    to: { name: "student-learning-assignments" },
  },
]);

const quickLinks = [
  { label: "Quiz Practice", icon: "?", name: "quiz-practice" },
  { label: "My Classes", icon: "▤", name: "student-classes" },
  { label: "Exam Results", icon: "▥", name: "student-exam-results" },
];

function formatDate(value) {
  const time = timestamp(value);
  if (!Number.isFinite(time)) return "Date unavailable";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(time));
}

function canPractise(topic) {
  return (
    topic.slug === "number-systems" ||
    (store.state.auth.currentUser?.academic_level === "ssc" &&
      topic.slug.startsWith("ssc-ict-"))
  );
}

async function loadDashboard() {
  controller?.abort();
  const version = ++requestVersion;
  const token = store.state.auth.accessToken;

  if (!token) {
    await router.replace({ name: "login" });
    return;
  }

  controller = new AbortController();
  const signal = controller.signal;
  const isCurrent = () =>
    version === requestVersion &&
    !signal.aborted &&
    token === store.state.auth.accessToken;

  loading.value = true;
  errors.value = {};
  progress.value = null;
  weakReport.value = null;
  quizzes.value = null;
  tasks.value = null;
  feedback.value = null;
  events.value = null;
  now.value = Date.now();

  async function get(path) {
    const response = await fetch(`http://127.0.0.1:5000${path}`, {
      headers: { Authorization: `Bearer ${token}` },
      signal,
    });

    if (!isCurrent()) throw new Error("Request cancelled.");

    if (response.status === 401) {
      store.commit("auth/CLEAR_AUTH");
      controller.abort();
      await router.replace({ name: "login" });
      throw new Error("Your session expired.");
    }

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || data.msg || "Could not load this section.");
    }
    return data;
  }

  async function getPages(path, key, filters = {}) {
    const collected = [];

    for (let page = 1; page <= 10000; page += 1) {
      const query = new URLSearchParams({
        ...filters,
        page: String(page),
      });
      const data = await get(`${path}?${query}`);

      if (!Array.isArray(data[key])) {
        throw new Error("The server returned an incomplete list.");
      }

      collected.push(...data[key]);
      if (!data.pagination?.has_more) return collected;
    }

    throw new Error("Too many entries. Open the full page to continue.");
  }

  async function section(key, target, fetchData) {
    try {
      const data = await fetchData();
      if (isCurrent()) target.value = data;
    } catch (error) {
      if (isCurrent()) {
        errors.value[key] =
          error instanceof Error
            ? error.message
            : "Could not load this section.";
      }
    }
  }

  const start = new Date(now.value);
  const end = new Date(start);
  end.setDate(end.getDate() + 30);

  const calendarFilters = {
    starts_at: start.toISOString(),
    ends_at: end.toISOString(),
  };

  try {
    await Promise.allSettled([
      section("progress", progress, () => get("/api/progress")),
      section("weak", weakReport, () => get("/api/progress/weak-topics")),
      section("quizzes", quizzes, () =>
        getPages("/api/quiz-assignments", "assignments", { view: "active" }),
      ),
      section("tasks", tasks, () =>
        getPages("/api/learning-assignments", "assignments"),
      ),
      section("feedback", feedback, async () => {
        const data = await get("/api/feedback/me?page=1");
        return data.feedback;
      }),
      section("events", events, async () => {
        const [personal, assignments, exams] = await Promise.all([
          getPages("/api/calendar-events", "events", calendarFilters),
          getPages(
            "/api/calendar-events/assignments",
            "assignments",
            calendarFilters,
          ),
          getPages("/api/class-exams", "exams", calendarFilters),
        ]);

        return [
          ...personal.map((item) => ({
            ...item,
            key: `personal-${item.id}`,
            label: "Personal event",
          })),
          ...assignments.map((item) => ({
            ...item,
            key: `assignment-${item.id}`,
            label: "Assignment",
          })),
          ...exams.map((item) => ({
            ...item,
            key: `exam-${item.id}`,
            label: "Class exam",
          })),
        ];
      }),
    ]);
  } finally {
    if (version === requestVersion) loading.value = false;
  }
}

onMounted(() => {
  loadDashboard();
  clock = window.setInterval(() => {
    now.value = Date.now();
  }, 60000);
});

onBeforeUnmount(() => {
  requestVersion += 1;
  controller?.abort();
  window.clearInterval(clock);
});
</script>

<template>
  <section class="student-dashboard" :aria-busy="loading">
    <header class="dashboard-heading">
      <div>
        <p class="eyebrow">STUDENT DASHBOARD</p>
        <h1>Your learning, in one place</h1>
      </div>
      <button class="button" :disabled="loading" @click="loadDashboard">
        {{ loading ? "Refreshing..." : "Refresh dashboard" }}
      </button>
    </header>

    <section class="welcome-banner">
      <div class="welcome-copy">
        <h2>{{ greeting }}, {{ userName }}</h2>
        <p>
          Choto choto practice-ei boro progress hoy. Ajke ekta topic bujhe nao,
          ar nijer learning-e arekta dhap egiye jao.
        </p>
      </div>

      <div class="welcome-actions">
        <RouterLink class="button maira-button" :to="{ name: 'home' }">
          ✦ Ask Maira →
        </RouterLink>

        <div class="dashboard-art" aria-hidden="true">
          <span class="art-code">&lt;/&gt;</span>
          <span class="art-dot"></span>
          <span class="art-spark">✦</span>
        </div>
      </div>
    </section>

    <p v-if="loading" class="status" role="status">
      Loading your learning overview...
    </p>

    <div class="stats-grid">
      <RouterLink
        v-for="stat in stats"
        :key="stat.label"
        :to="stat.to"
        class="stat-card"
      >
        <span class="stat-icon" :class="stat.tone">{{ stat.icon }}</span>
        <div>
          <p>{{ stat.label }}</p>
          <strong>{{ stat.value }}</strong>
          <small>{{ stat.note }}</small>
        </div>
      </RouterLink>
    </div>

    <p v-if="errors.progress" class="error" role="alert">
      Progress: {{ errors.progress }}
    </p>

    <div class="dashboard-grid">
      <section class="panel">
        <div class="panel-heading">
          <h2>Upcoming assignments</h2>
          <RouterLink class="text-link" :to="{ name: 'student-assignments' }">
            All quizzes →
          </RouterLink>
        </div>
        <RouterLink
          class="text-link task-link"
          :to="{ name: 'student-learning-assignments' }"
        >
          All learning tasks →
        </RouterLink>

        <p v-if="errors.quizzes" class="error">{{ errors.quizzes }}</p>
        <p v-if="errors.tasks" class="error">{{ errors.tasks }}</p>

        <div class="item-list">
          <article
            v-for="item in upcomingAssignments"
            :key="item.key"
            class="list-item"
          >
            <div class="item-content">
              <span class="badge">{{ item.type }}</span>
              <h3>{{ item.title }}</h3>
              <p>{{ item.classroom }}</p>
              <small>Deadline: {{ formatDate(item.deadline) }}</small>
            </div>
            <RouterLink class="button small-button" :to="item.to">
              Open →
            </RouterLink>
          </article>
        </div>

        <p
          v-if="
            !loading &&
            !errors.quizzes &&
            !errors.tasks &&
            !upcomingAssignments.length
          "
          class="empty"
        >
          Ekhon kono upcoming assignment nei.
        </p>
      </section>

      <section class="panel">
        <div class="panel-heading">
          <h2>Practise weak topics</h2>
          <RouterLink class="text-link" :to="{ name: 'progress' }">
            View report →
          </RouterLink>
        </div>

        <p v-if="errors.weak" class="error">{{ errors.weak }}</p>

        <div class="item-list">
          <article
            v-for="topic in weakTopics"
            :key="topic.topic_id"
            class="list-item"
          >
            <div class="item-content">
              <h3>{{ topic.title }}</h3>
              <p>Latest score: {{ topic.latest_percentage }}%</p>
            </div>
            <RouterLink
              v-if="canPractise(topic)"
              class="button small-button"
              :to="{
                name: 'quiz-practice',
                query: { topic_slug: topic.slug },
              }"
            >
              Practise →
            </RouterLink>
            <RouterLink v-else class="text-link" :to="{ name: 'progress' }">
              View topic →
            </RouterLink>
          </article>
        </div>

        <p v-if="!loading && !errors.weak && !weakTopics.length" class="empty">
          {{
            progress?.summary?.completed_topics
              ? "Tomar report-e ekhon kono weak topic nei."
              : "Quiz practice korle ekhane weak topic-er report pabe."
          }}
        </p>
      </section>

      <section class="panel">
        <div class="panel-heading">
          <h2>Teacher feedback</h2>
          <RouterLink class="text-link" :to="{ name: 'student-feedback' }">
            View all →
          </RouterLink>
        </div>

        <p v-if="errors.feedback" class="error">{{ errors.feedback }}</p>

        <article v-if="latestFeedback" class="feedback-preview">
          <p class="eyebrow">LATEST ADVICE</p>
          <h3>{{ latestFeedback.teacher_name }}</h3>
          <small>{{ latestFeedback.classroom_name }}</small>
          <p class="feedback-message">{{ latestFeedback.message }}</p>
          <small>{{ formatDate(latestFeedback.created_at) }}</small>
        </article>

        <p v-else-if="!loading && !errors.feedback" class="empty">
          Teacher feedback pele ekhane latest advice dekhabe.
        </p>
      </section>

      <section class="panel">
        <div class="panel-heading">
          <h2>Upcoming events</h2>
          <RouterLink class="text-link" :to="{ name: 'calendar' }">
            Open calendar →
          </RouterLink>
        </div>
        <p class="section-note">Next 30 days</p>
        <p v-if="errors.events" class="error">{{ errors.events }}</p>

        <div class="item-list">
          <article
            v-for="event in nextEvents"
            :key="event.key"
            class="list-item"
          >
            <span class="stat-icon blue" aria-hidden="true">▦</span>
            <div class="item-content">
              <h3>{{ event.title }}</h3>
              <p>{{ event.label }}</p>
              <small>{{ formatDate(event.starts_at) }}</small>
            </div>
          </article>
        </div>

        <p
          v-if="!loading && !errors.events && !nextEvents.length"
          class="empty"
        >
          Next 30 days-e kono event nei.
        </p>
      </section>
    </div>

    <section class="panel quick-links">
      <h2>Quick links</h2>
      <RouterLink
        v-for="link in quickLinks"
        :key="link.name"
        :to="{ name: link.name }"
        class="quick-link"
      >
        <span class="stat-icon blue">{{ link.icon }}</span>
        {{ link.label }}
        <span aria-hidden="true">→</span>
      </RouterLink>
    </section>
  </section>
</template>

<style scoped>
.student-dashboard {
  display: grid;
  gap: 1.25rem;
  min-width: 0;
  color: var(--text-primary);
}

.dashboard-heading,
.panel-heading,
.welcome-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

h1,
h2,
h3,
p {
  margin: 0;
}

h1,
h2,
h3 {
  overflow-wrap: anywhere;
}

h1 {
  margin-top: 0.45rem;
  font-size: clamp(1.8rem, 3.5vw, 2.7rem);
}

h2 {
  font-size: 1.25rem;
}

h3 {
  font-size: 1rem;
  line-height: 1.5;
}

.eyebrow {
  color: var(--accent-color);
  font-size: 0.73rem;
  font-weight: 800;
  letter-spacing: 0.1em;
}

.welcome-banner {
  padding: 1.75rem;
  border: 1px solid #f3dd91;
  border-radius: 1.2rem;
  background: linear-gradient(120deg, #f8e8ad, #fff7d6, var(--surface-color));
}

.welcome-banner h2 {
  color: #172554;
  font-size: clamp(1.4rem, 2.5vw, 2rem);
}

.welcome-banner p {
  max-width: 42rem;
  margin-top: 0.7rem;
  color: #475569;
  line-height: 1.7;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
}

.stat-card,
.panel {
  min-width: 0;
  padding: 1.25rem;
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  background: var(--surface-color);
  box-shadow: 0 0.5rem 1.2rem rgb(15 23 42 / 4%);
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  color: var(--text-primary);
  text-decoration: none;
}

.stat-card p,
small,
.section-note,
.status,
.empty,
.item-content p {
  color: var(--text-secondary);
  line-height: 1.6;
}

.stat-card p {
  font-size: 0.87rem;
}

.stat-card strong {
  display: block;
  margin: 0.3rem 0;
  font-size: 1.75rem;
}

.stat-card small {
  display: block;
  font-size: 0.72rem;
}

.stat-icon {
  display: grid;
  place-items: center;
  width: 2.8rem;
  height: 2.8rem;
  flex: 0 0 auto;
  border-radius: 0.9rem;
  font-size: 1.4rem;
  font-weight: 800;
}

.blue {
  background: rgb(37 80 219 / 12%);
  color: var(--accent-color);
}

.red {
  background: rgb(220 38 38 / 12%);
  color: #dc2626;
}

.green {
  background: rgb(22 163 74 / 12%);
  color: #16a34a;
}

.gold {
  background: rgb(217 119 6 / 12%);
  color: #d97706;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 1rem;
}

.panel-heading {
  align-items: flex-start;
  flex-wrap: wrap;
}

.item-list {
  display: grid;
  margin-top: 0.8rem;
}

.list-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 0;
  border-bottom: 1px solid var(--border-color);
}

.list-item:last-child {
  border-bottom: 0;
}

.item-content {
  flex: 1;
  min-width: 0;
}

.item-content p {
  margin-top: 0.25rem;
  font-size: 0.85rem;
}

.item-content small {
  display: block;
  margin-top: 0.25rem;
}

.badge {
  display: inline-block;
  margin-bottom: 0.4rem;
  padding: 0.2rem 0.5rem;
  border-radius: 99px;
  background: var(--nav-hover);
  color: var(--accent-color);
  font-size: 0.72rem;
  font-weight: 700;
}

.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  flex-shrink: 0;
  padding: 0.75rem 1rem;
  border: 1px solid #2450db;
  border-radius: 0.65rem;
  background: #2450db;
  color: #fff;
  font: inherit;
  font-size: 0.87rem;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}

.small-button {
  padding: 0.6rem 0.8rem;
}

.button,
.stat-card,
.quick-link,
.text-link {
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.button:hover:not(:disabled) {
  background: #1d3fb8;
  border-color: #1d3fb8;
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.button:active:not(:disabled) {
  transform: scale(0.98);
}

.button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.text-link {
  color: var(--accent-color);
  font-size: 0.85rem;
  font-weight: 700;
  text-decoration: none;
}

.text-link:hover {
  text-decoration: underline;
  text-underline-offset: 4px;
  transform: translateX(2px);
}

.task-link {
  display: inline-block;
  margin-top: 0.65rem;
}

.feedback-preview {
  margin-top: 1rem;
  padding: 1rem;
  border-radius: 0.85rem;
  background: var(--nav-hover);
}

.feedback-preview h3 {
  margin-top: 0.65rem;
}

.feedback-message {
  margin: 0.7rem 0;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.section-note,
.empty {
  margin-top: 0.8rem;
  font-size: 0.9rem;
}

.error {
  margin-top: 0.8rem;
  color: #dc2626;
  line-height: 1.6;
}

.quick-links {
  display: grid;
  grid-template-columns: auto repeat(3, minmax(0, 1fr));
  align-items: center;
  gap: 1rem;
}

.quick-link {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  min-width: 0;
  padding: 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.85rem;
  color: var(--accent-color);
  font-weight: 700;
  text-decoration: none;
}

.quick-link > span:last-child {
  margin-left: auto;
}

.stat-card:hover,
.quick-link:hover {
  background: var(--nav-hover);
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 12%);
  transform: translateY(-2px);
}

a:focus-visible,
button:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 4px;
}

:global(.dark-theme) .welcome-banner {
  border-color: #715d1f;
  background: linear-gradient(120deg, #5d4d18, #352f22, var(--surface-color));
}

:global(.dark-theme) .welcome-banner h2 {
  color: #fff;
}

:global(.dark-theme) .welcome-banner p {
  color: #e2e8f0;
}

@media (max-width: 1100px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .quick-links {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .quick-links h2 {
    grid-column: 1 / -1;
  }
}

@media (max-width: 760px) {
  .dashboard-grid,
  .quick-links {
    grid-template-columns: 1fr;
  }

  .dashboard-heading,
  .welcome-banner {
    align-items: flex-start;
    flex-direction: column;
  }

  .welcome-banner {
    padding: 1.25rem;
  }
}

@media (max-width: 480px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .list-item {
    flex-wrap: wrap;
  }

  .panel {
    padding: 1rem;
  }
}
.button.maira-button {
  border-color: #800000;
  background: #800000;
  color: #fff;
}

.button.maira-button:hover {
  border-color: #650000;
  background: #650000;
  box-shadow: 0 0.6rem 1rem rgb(128 0 0 / 20%);
}

.button.maira-button:focus-visible {
  outline-color: #800000;
}
.student-dashboard .welcome-banner {
  gap: 1.25rem;
  padding: 1.25rem 1.5rem;
  background:
    radial-gradient(
      circle at 95% 15%,
      rgb(255 255 255 / 55%),
      transparent 12rem
    ),
    linear-gradient(120deg, #f4d774, #f8e8ad 55%, #f4f7ff);
}

.welcome-copy {
  flex: 1;
  min-width: 0;
}

.student-dashboard .welcome-banner h2 {
  font-size: clamp(1.35rem, 2.5vw, 1.8rem);
}

.student-dashboard .welcome-banner p {
  max-width: 42rem;
  margin-top: 0.5rem;
  font-size: 0.95rem;
  line-height: 1.6;
}

.welcome-actions {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  flex-shrink: 0;
}

.dashboard-art {
  position: relative;
  display: grid;
  place-items: center;
  width: 6rem;
  height: 6rem;
  flex-shrink: 0;
}

.art-code {
  display: grid;
  place-items: center;
  width: 4.3rem;
  height: 4.3rem;
  border-radius: 1.2rem;
  background: #2450db;
  color: #facc15;
  font-size: 1.6rem;
  font-weight: 900;
  box-shadow: 0 0.7rem 1.3rem rgb(30 64 175 / 20%);
  transform: rotate(8deg);
}

.art-dot {
  position: absolute;
  top: 0;
  right: 0;
  width: 1rem;
  height: 1rem;
  border-radius: 50%;
  background: #fb923c;
}

.art-spark {
  position: absolute;
  bottom: 0;
  left: 0;
  color: #2450db;
  font-size: 1.2rem;
}

:global(.dark-theme) .student-dashboard .welcome-banner {
  background: linear-gradient(120deg, #5d4d18, #352f22, #132442);
}

@media (max-width: 760px) {
  .welcome-actions {
    flex-wrap: wrap;
  }

  .dashboard-art {
    display: none;
  }
}
</style>
