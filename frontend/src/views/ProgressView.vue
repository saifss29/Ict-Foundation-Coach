<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useStore } from "vuex";

const router = useRouter();
const store = useStore();

const summary = ref(null);
const topicProgress = ref([]);
const isLoading = ref(true);
const errorMessage = ref("");
const masteryLabels = {
  not_started: "Not started",
  needs_support: "Needs support",
  practicing: "Practicing",
  almost_mastered: "Almost mastered",
  mastered: "Mastered",
};

function masteryLabel(status) {
  return masteryLabels[status] || "Status unavailable";
}

function clearAuthAndRedirect() {
  store.commit("auth/CLEAR_AUTH");
  router.push("/login");
}

async function loadProgress() {
  const accessToken = store.state.auth.accessToken;

  if (!accessToken) {
    router.replace("/login");
    return;
  }

  try {
    const response = await fetch("http://127.0.0.1:5000/api/progress", {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });

    const data = await response.json();

    if (response.status === 401) {
      clearAuthAndRedirect();
      return;
    }

    if (!response.ok) {
      throw new Error(data.error || "Could not load progress.");
    }

    summary.value = data.summary;
    topicProgress.value = data.topics;
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    isLoading.value = false;
  }
}

const weakReport = ref(null);
const weakReportLoading = ref(false);
const weakReportError = ref("");

let weakReportController = null;
let weakReportRequest = 0;

const trendLabels = {
  improving: "Improving",
  declining: "Lower than previous attempt",
  unchanged: "Same percentage as previous attempt",
  not_enough_attempts: "Another attempt needed to compare",
};

function trendLabel(trend) {
  return trendLabels[trend] || "Comparison unavailable";
}

async function loadWeakReport() {
  weakReportController?.abort();

  const requestId = ++weakReportRequest;
  const accessToken = store.state.auth.accessToken;

  weakReport.value = null;
  weakReportError.value = "";

  if (!accessToken) {
    weakReportLoading.value = false;
    await router.replace("/login");
    return;
  }

  const controller = new AbortController();
  weakReportController = controller;
  weakReportLoading.value = true;

  const isCurrentRequest = () =>
    requestId === weakReportRequest &&
    accessToken === store.state.auth.accessToken &&
    !controller.signal.aborted;

  try {
    const response = await fetch(
      "http://127.0.0.1:5000/api/progress/weak-topics",
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        signal: controller.signal,
      },
    );

    if (!isCurrentRequest()) return;

    if (response.status === 401) {
      clearAuthAndRedirect();
      return;
    }

    const data = await response.json();

    if (!isCurrentRequest()) return;

    if (!response.ok) {
      throw new Error(data.error || "Could not load weak-topic report.");
    }

    weakReport.value = data;
  } catch (error) {
    if (!isCurrentRequest()) return;

    weakReportError.value =
      error instanceof Error
        ? error.message
        : "Could not load weak-topic report.";
  } finally {
    if (requestId === weakReportRequest) {
      weakReportLoading.value = false;
    }
  }
}

onMounted(() => {
  loadProgress();
  loadWeakReport();
});

onBeforeUnmount(() => {
  weakReportRequest += 1;
  weakReportController?.abort();
});
</script>

<template>
  <section class="progress-page">
    <header class="dashboard-heading">
      <div>
        <p class="eyebrow">YOUR LEARNING PROGRESS</p>
        <h1>See how far you have come.</h1>
        <p>Quiz practice korle ekhane tomar learning journey update hobe.</p>
      </div>

      <span class="progress-status">↗ Keep learning</span>
    </header>

    <section v-if="summary" class="progress-hero">
      <div>
        <p class="hero-label">YOUR CURRENT JOURNEY</p>
        <h2>
          {{ summary.completed_topics }} of {{ summary.total_topics }} topics
          practised
        </h2>
        <p>Small regular practice diye ICT fundamentals aro strong hobe.</p>
      </div>

      <div class="hero-visual" aria-hidden="true">
        <span class="hero-chart">↗</span>
        <span class="hero-dot dot-one"></span>
        <span class="hero-dot dot-two"></span>
      </div>
    </section>

    <section v-if="summary" class="summary-grid">
      <article class="summary-card completed-card">
        <span class="summary-icon">✓</span>

        <div>
          <p>Topics practised</p>
          <strong>{{ summary.completed_topics }}</strong>
          <small>out of {{ summary.total_topics }} topics</small>
        </div>
      </article>

      <article class="summary-card remaining-card">
        <span class="summary-icon">→</span>

        <div>
          <p>Topics remaining</p>
          <strong>
            {{ summary.total_topics - summary.completed_topics }}
          </strong>
          <small>Choose a topic and start a quiz</small>
        </div>
      </article>
    </section>
    <section
      class="progress-panel weak-topic-panel"
      :aria-busy="weakReportLoading"
    >
      <div class="section-heading">
        <div>
          <p class="eyebrow">FOCUSED PRACTICE</p>
          <h2>Topics that need more practice</h2>
        </div>

        <button
          type="button"
          class="quiz-button"
          :disabled="weakReportLoading"
          @click="loadWeakReport"
        >
          {{ weakReportLoading ? "Loading..." : "Refresh report" }}
        </button>
      </div>

      <p class="report-description">
        Latest completed quiz-er score 80%-er niche hole ekhane dekhabe. Eta
        practice guidance; full topic mastery-er assessment na. Quiz na deoa
        topic-ke weak bola hoy na.
      </p>

      <p v-if="weakReportLoading" class="loading-message" role="status">
        Loading your practice report...
      </p>

      <p v-else-if="weakReportError" class="error-message" role="alert">
        {{ weakReportError }}
      </p>

      <template v-else-if="weakReport">
        <div class="report-summary">
          <span> More practice: {{ weakReport.summary.weak_topics }} </span>
          <span>
            Latest score 80% or above:
            {{ weakReport.summary.other_practised_topics }}
          </span>
          <span>
            Not practised: {{ weakReport.summary.not_practised_topics }}
          </span>
        </div>

        <p
          v-if="weakReport.summary.total_topics === 0"
          class="report-description"
        >
          Tomar study level-er ICT topic ekhono available nai.
        </p>

        <p
          v-else-if="
            weakReport.summary.weak_topics === 0 &&
            weakReport.summary.other_practised_topics === 0
          "
          class="report-description"
        >
          Quiz submit korle ekhane practice guidance dekhabe. Ekhono kono
          topic-er result available nai.
        </p>

        <p
          v-else-if="weakReport.weak_topics.length === 0"
          class="report-description"
        >
          Practised topic-gular latest score 80% ba tar beshi. Regular revision
          chaliye jao.
        </p>

        <div v-else class="progress-list">
          <article
            v-for="topic in weakReport.weak_topics"
            :key="topic.topic_id"
            class="weak-topic-card"
          >
            <div class="topic-title-row">
              <h3>{{ topic.title }}</h3>

              <span class="status-badge" :class="topic.mastery_status">
                {{ masteryLabel(topic.mastery_status) }}
              </span>
            </div>

            <p>
              Latest score: {{ topic.latest_score }} /
              {{ topic.total_questions }} · {{ topic.latest_percentage }}%
            </p>

            <p class="trend-text">
              {{ trendLabel(topic.trend) }}
              <span v-if="topic.previous_percentage !== null">
                · Previous: {{ topic.previous_percentage }}%
              </span>
            </p>

            <small>{{ topic.attempt_count }} completed quiz attempt(s)</small>
            <RouterLink
              v-if="
                topic.slug === 'number-systems' ||
                (store.state.auth.currentUser?.academic_level === 'ssc' &&
                  topic.slug.startsWith('ssc-ict-'))
              "
              :to="{
                name: 'quiz-practice',
                query: { topic_slug: topic.slug },
              }"
              class="quiz-button weak-practice-link"
            >
              Practice this topic →
            </RouterLink>
            <p v-else class="report-description">
              Generated quiz practice is not available for this topic yet.
            </p>
          </article>
        </div>

        <details v-if="weakReport.not_practised_topics.length">
          <summary>
            Not practised topics ({{ weakReport.not_practised_topics.length }})
          </summary>

          <ul class="unpractised-list">
            <li
              v-for="topic in weakReport.not_practised_topics"
              :key="topic.topic_id"
            >
              {{ topic.title }}
            </li>
          </ul>
        </details>
      </template>
    </section>

    <p v-if="isLoading" class="loading-message">Progress loading...</p>

    <p v-else-if="errorMessage" class="error-message">
      {{ errorMessage }}
    </p>

    <section v-else class="progress-panel">
      <div class="section-heading">
        <div>
          <p class="eyebrow">TOPIC OVERVIEW</p>
          <h2>Your learning path</h2>
        </div>

        <span class="topic-count">{{ topicProgress.length }} topics</span>
      </div>

      <div class="progress-list">
        <article
          v-for="topic in topicProgress"
          :key="topic.topic_id"
          class="progress-card"
          :class="{ practised: topic.attempt_count > 0 }"
        >
          <span class="topic-number">
            {{ topic.topic_id }}
          </span>

          <div class="topic-info">
            <div class="topic-title-row">
              <h3>{{ topic.title }}</h3>

              <span class="status-badge" :class="topic.mastery_status">
                {{ masteryLabel(topic.mastery_status) }}
              </span>
            </div>

            <template v-if="topic.attempt_count > 0">
              <p>
                Latest score: {{ topic.latest_score }} /
                {{ topic.total_questions }} · {{ topic.percentage }}%
              </p>

              <div
                class="progress-track"
                :aria-label="`${topic.title} score: ${topic.percentage}%`"
              >
                <span
                  class="progress-fill"
                  :style="{ width: `${topic.percentage}%` }"
                ></span>
              </div>

              <small>{{ topic.attempt_count }} quiz attempt(s)</small>
            </template>

            <p v-else class="not-started-text">Quiz ekhono start koro nai.</p>
          </div>

          <RouterLink
            :to="{
              name: 'quiz',
              params: { slug: topic.slug },
            }"
            class="quiz-button"
          >
            {{ topic.attempt_count > 0 ? "Try again" : "Start quiz" }}
            <span>→</span>
          </RouterLink>
        </article>
      </div>
    </section>
  </section>
</template>

<style scoped>
.progress-page {
  display: grid;
  gap: 1.5rem;
  min-width: 0;
}

.dashboard-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 1rem;
}

.eyebrow,
.hero-label {
  margin: 0;
  color: var(--accent-color);
  font-size: 0.7rem;
  font-weight: 850;
  letter-spacing: 0.11em;
}

.dashboard-heading h1 {
  margin: 0.4rem 0 0;
  color: var(--text-primary);
  font-size: clamp(1.65rem, 3vw, 2.35rem);
  line-height: 1.15;
}

.dashboard-heading p:last-child {
  max-width: 620px;
  margin: 0.55rem 0 0;
  color: var(--text-secondary);
  line-height: 1.55;
}

.progress-status,
.topic-count {
  flex: 0 0 auto;
  border-radius: 99rem;
  padding: 0.45rem 0.7rem;
  background: color-mix(in srgb, #22c55e 14%, var(--surface-color));
  color: #15803d;
  font-size: 0.76rem;
  font-weight: 800;
  white-space: nowrap;
}

.progress-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 2rem;
  overflow: hidden;
  min-height: 190px;
  padding: 2rem;
  border: 1px solid #f3dd91;
  border-radius: 1.35rem;
  background:
    radial-gradient(
      circle at 88% 20%,
      rgb(255 255 255 / 54%),
      transparent 11rem
    ),
    linear-gradient(120deg, #f4d774, #f8e8ad 52%, #f4f7ff);
}

.progress-hero > div:first-child {
  max-width: 640px;
}

.hero-label {
  color: #7c5c00;
}

.progress-hero h2 {
  margin: 0.55rem 0;
  color: #172554;
  font-size: clamp(1.55rem, 3vw, 2.35rem);
  line-height: 1.15;
}

.progress-hero p:not(.hero-label) {
  margin: 0;
  color: #475569;
  line-height: 1.65;
}

.hero-visual {
  position: relative;
  display: grid;
  width: 10rem;
  height: 8rem;
  flex: 0 0 auto;
  place-items: center;
}

.hero-chart {
  display: grid;
  width: 6.6rem;
  height: 6.6rem;
  place-items: center;
  border-radius: 2rem;
  background: #1d4ed8;
  box-shadow: 0 1rem 2rem rgb(30 64 175 / 25%);
  color: #facc15;
  font-size: 2.6rem;
  font-weight: 900;
  transform: rotate(-8deg);
}

.hero-dot {
  position: absolute;
  width: 1rem;
  height: 1rem;
  border-radius: 50%;
}

.dot-one {
  top: 0.6rem;
  left: 0.2rem;
  background: #f97316;
}

.dot-two {
  right: 0.3rem;
  bottom: 0.7rem;
  background: #22c55e;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.summary-card {
  display: flex;
  align-items: center;
  gap: 0.95rem;
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  padding: 1.2rem;
  background: var(--surface-color);
  box-shadow: 0 0.65rem 1.5rem rgb(15 23 42 / 6%);
  transition:
    border-color 0.2s ease,
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.summary-card:hover {
  box-shadow: 0 0.9rem 1.8rem rgb(15 23 42 / 11%);
  transform: translateY(-3px);
}

.completed-card {
  border-color: color-mix(in srgb, #22c55e 45%, var(--border-color));
}

.remaining-card {
  border-color: color-mix(in srgb, #f59e0b 48%, var(--border-color));
}

.summary-icon {
  display: grid;
  width: 2.7rem;
  height: 2.7rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.85rem;
  background: var(--nav-hover);
  color: var(--accent-color);
  font-size: 1.2rem;
  font-weight: 900;
}

.completed-card .summary-icon {
  background: rgb(34 197 94 / 15%);
  color: #15803d;
}

.remaining-card .summary-icon {
  background: rgb(245 158 11 / 15%);
  color: #a16207;
}

.summary-card p,
.summary-card small {
  display: block;
  margin: 0;
  color: var(--text-secondary);
}

.summary-card p {
  font-size: 0.88rem;
}

.summary-card strong {
  display: block;
  margin: 0.15rem 0;
  color: var(--text-primary);
  font-size: 1.8rem;
}

.summary-card small {
  font-size: 0.76rem;
}

.progress-panel {
  border: 1px solid var(--border-color);
  border-radius: 1.15rem;
  padding: 1.35rem;
  background: var(--surface-color);
  box-shadow: 0 0.7rem 1.7rem rgb(15 23 42 / 6%);
}

.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.section-heading h2 {
  margin: 0.4rem 0 0;
  color: var(--text-primary);
  font-size: 1.35rem;
}

.topic-count {
  background: var(--nav-hover);
  color: var(--accent-color);
}

.progress-list {
  display: grid;
  gap: 0.8rem;
  margin-top: 1.2rem;
}

.progress-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.95rem;
  padding: 1rem;
  background: var(--page-background);
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.progress-card:hover {
  border-color: var(--accent-color);
  box-shadow: 0 0.7rem 1.3rem rgb(30 64 175 / 10%);
  transform: translateY(-2px);
}

.progress-card.practised {
  background: color-mix(
    in srgb,
    var(--accent-color) 5%,
    var(--page-background)
  );
}

.topic-number {
  display: grid;
  width: 2.4rem;
  height: 2.4rem;
  place-items: center;
  border-radius: 0.75rem;
  background: var(--nav-hover);
  color: var(--accent-color);
  font-size: 0.86rem;
  font-weight: 900;
}

.topic-info {
  min-width: 0;
}

.topic-title-row {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.topic-title-row h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 1rem;
}

.status-badge {
  flex: 0 0 auto;
  border-radius: 99rem;
  padding: 0.28rem 0.55rem;
  font-size: 0.7rem;
  font-weight: 800;
  white-space: nowrap;
}

.status-badge.completed {
  background: rgb(34 197 94 / 15%);
  color: #15803d;
}

.status-badge.pending {
  background: rgb(245 158 11 / 15%);
  color: #a16207;
}

.topic-info p {
  margin: 0.42rem 0;
  color: var(--text-secondary);
  font-size: 0.88rem;
  line-height: 1.5;
}

.topic-info small {
  color: var(--text-secondary);
  font-size: 0.76rem;
}

.progress-track {
  width: 100%;
  max-width: 410px;
  height: 0.52rem;
  overflow: hidden;
  border-radius: 99rem;
  background: var(--nav-hover);
}

.progress-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--accent-color), #60a5fa);
  transform: scaleX(0);
  transform-origin: left;
  animation: fill-progress 0.8s ease-out forwards;
}

.not-started-text {
  margin-bottom: 0;
}

.quiz-button {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  flex: 0 0 auto;
  border-radius: 0.65rem;
  padding: 0.7rem 0.85rem;
  background: var(--accent-color);
  color: #ffffff;
  font-size: 0.82rem;
  font-weight: 800;
  text-decoration: none;
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.quiz-button:hover {
  background: var(--accent-hover);
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.loading-message,
.error-message {
  margin: 0;
  font-size: 0.9rem;
}

.loading-message {
  color: var(--text-secondary);
}

.error-message {
  border-radius: 0.7rem;
  padding: 0.8rem;
  background: rgb(220 38 38 / 10%);
  color: #dc2626;
}

@keyframes fill-progress {
  from {
    transform: scaleX(0);
  }

  to {
    transform: scaleX(1);
  }
}

:global(.dark-theme) .progress-hero {
  border-color: #715d1f;
  background:
    radial-gradient(
      circle at 88% 20%,
      rgb(255 255 255 / 8%),
      transparent 11rem
    ),
    linear-gradient(120deg, #5d4d18, #352f22 55%, #132442);
}

:global(.dark-theme) .progress-hero h2 {
  color: #ffffff;
}

:global(.dark-theme) .progress-hero p:not(.hero-label) {
  color: #e2e8f0;
}

:global(.dark-theme) .progress-status,
:global(.dark-theme) .status-badge.completed,
:global(.dark-theme) .completed-card .summary-icon {
  color: #86efac;
}

:global(.dark-theme) .status-badge.pending,
:global(.dark-theme) .remaining-card .summary-icon {
  color: #fcd34d;
}

@media (max-width: 720px) {
  .dashboard-heading,
  .progress-hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .hero-visual {
    align-self: flex-end;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }

  .progress-card {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .quiz-button {
    grid-column: 1 / -1;
    justify-content: center;
  }
}

@media (max-width: 480px) {
  .topic-title-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .progress-panel,
  .progress-hero {
    padding: 1.15rem;
  }
}
.topic-title-row {
  flex-wrap: wrap;
}

.topic-title-row h3 {
  overflow-wrap: anywhere;
}

.status-badge {
  background: var(--nav-hover);
  color: var(--text-secondary);
}

.status-badge.not_started {
  background: var(--nav-hover);
  color: var(--text-secondary);
}

.status-badge.needs_support {
  background: rgb(220 38 38 / 12%);
  color: #b91c1c;
}

.status-badge.practicing {
  background: rgb(217 119 6 / 12%);
  color: #92400e;
}

.status-badge.almost_mastered {
  background: rgb(37 99 235 / 12%);
  color: #1d4ed8;
}

.status-badge.mastered {
  background: rgb(22 163 74 / 12%);
  color: #166534;
}

:global(.dark-theme) .status-badge.needs_support {
  color: #fca5a5;
}

:global(.dark-theme) .status-badge.practicing {
  color: #fcd34d;
}

:global(.dark-theme) .status-badge.almost_mastered {
  color: #93c5fd;
}

:global(.dark-theme) .status-badge.mastered {
  color: #86efac;
}
.weak-topic-panel .section-heading {
  flex-wrap: wrap;
}

.report-description {
  color: var(--text-secondary);
  line-height: 1.7;
}

.report-refresh {
  padding: 0.65rem 0.9rem;
  border: 1px solid var(--border-color);
  border-radius: 0.65rem;
  background: var(--page-background);
  color: var(--accent-color);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.report-refresh:hover:not(:disabled) {
  background: var(--nav-hover);
}

.report-refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.report-refresh:focus-visible,
.weak-topic-panel summary:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 4px;
}

.report-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  margin-top: 1rem;
}

.report-summary span {
  padding: 0.5rem 0.75rem;
  border-radius: 0.65rem;
  background: var(--nav-hover);
  color: var(--text-primary);
  font-size: 0.85rem;
}

.weak-topic-card {
  min-width: 0;
  padding: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.85rem;
  background: var(--page-background);
}

.weak-topic-card h3 {
  margin: 0;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.weak-topic-card p {
  margin: 0.65rem 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.weak-topic-card small {
  color: var(--text-secondary);
}

.weak-topic-panel details {
  margin-top: 1.2rem;
}

.weak-topic-panel summary {
  color: var(--accent-color);
  font-weight: 700;
  cursor: pointer;
}

.unpractised-list {
  display: grid;
  gap: 0.5rem;
  padding-left: 1.25rem;
  color: var(--text-secondary);
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.weak-practice-link {
  margin-top: 0.8rem;
}
button.refresh-report {
  padding: 0.7rem 1rem;
  border: 0;
  border-radius: 8px;
  background: var(--accent-color);
  color: #fff;
  font: inherit;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

button.refresh-report:hover:not(:disabled) {
  background: var(--accent-hover);
  color: #fff;
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

button.refresh-report:active:not(:disabled) {
  transform: scale(0.98);
}

button.refresh-report:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

button.refresh-report:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

@media (prefers-reduced-motion: reduce) {
  button.refresh-report {
    transition: none;
  }
}
</style>
