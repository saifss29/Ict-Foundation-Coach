<script setup>
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useStore } from "vuex";

const route = useRoute();
const router = useRouter();
const store = useStore();

const API_URL = "http://127.0.0.1:5000/api";

const history = ref(null);
const isLoading = ref(false);
const loadError = ref("");

const feedbackItems = ref([]);
const feedbackPage = ref(0);
const hasMoreFeedback = ref(false);
const isFeedbackLoading = ref(false);
const feedbackLoadError = ref("");

const feedbackMessage = ref("");
const selectedAttemptId = ref("");
const isSending = ref(false);
const sendError = ref("");
const successMessage = ref("");

let pageVersion = 0;

const classroomId = computed(() => route.params.classroomId);
const studentId = computed(() => route.params.studentId);

const attempts = computed(() => history.value?.attempts || []);
const latestAttempt = computed(() => attempts.value[0] || null);

const averagePercentage = computed(() => {
  if (attempts.value.length === 0) return null;

  const total = attempts.value.reduce(
    (sum, attempt) => sum + attempt.percentage,
    0,
  );

  return Math.round(total / attempts.value.length);
});

const feedbackPath = computed(
  () => `/feedback/classes/${classroomId.value}/students/${studentId.value}`,
);

async function requestApi(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${store.state.auth.accessToken}`,
    },
  });

  if (response.status === 401) {
    store.commit("auth/CLEAR_AUTH");
    await router.replace("/login");
    throw new Error("Your session has expired. Please log in again.");
  }

  const data = await response.json();

  if (!response.ok) {
    const validationMessage = Object.values(data.messages || {})
      .flat()
      .find((message) => typeof message === "string");

    throw new Error(
      validationMessage || data.error || "Could not complete the request.",
    );
  }

  return data;
}

async function loadAttemptHistory() {
  if (isLoading.value) return;

  const version = pageVersion;

  isLoading.value = true;
  loadError.value = "";

  try {
    const data = await requestApi(
      `/classes/${classroomId.value}/students/${studentId.value}/attempts`,
    );

    if (version !== pageVersion) return;

    history.value = data;
    await loadFeedback();
  } catch (error) {
    if (version !== pageVersion) return;

    loadError.value =
      error instanceof Error
        ? error.message
        : "Could not load student history.";
  } finally {
    if (version === pageVersion) {
      isLoading.value = false;
    }
  }
}

async function loadFeedback(append = false) {
  if (isFeedbackLoading.value) return;

  const version = pageVersion;
  const nextPage = append ? feedbackPage.value + 1 : 1;

  isFeedbackLoading.value = true;
  feedbackLoadError.value = "";

  try {
    const data = await requestApi(`${feedbackPath.value}?page=${nextPage}`);

    if (version !== pageVersion) return;

    if (append) {
      const existingIds = new Set(feedbackItems.value.map((item) => item.id));

      feedbackItems.value.push(
        ...data.feedback.filter((item) => !existingIds.has(item.id)),
      );
    } else {
      feedbackItems.value = data.feedback;
    }

    feedbackPage.value = data.pagination.page;
    hasMoreFeedback.value = data.pagination.has_more;
  } catch (error) {
    if (version !== pageVersion) return;

    feedbackLoadError.value =
      error instanceof Error ? error.message : "Could not load feedback.";
  } finally {
    if (version === pageVersion) {
      isFeedbackLoading.value = false;
    }
  }
}

async function sendFeedback() {
  if (isSending.value || isFeedbackLoading.value || !history.value) {
    return;
  }

  sendError.value = "";
  successMessage.value = "";

  const message = feedbackMessage.value.trim();

  if (!message) {
    sendError.value = "Write some feedback before sending.";
    return;
  }

  if (message.length > 2000) {
    sendError.value = "Feedback must be 2000 characters or less.";
    return;
  }

  const attemptId =
    selectedAttemptId.value === "" ? null : Number(selectedAttemptId.value);

  if (
    attemptId !== null &&
    !attempts.value.some((attempt) => attempt.id === attemptId)
  ) {
    sendError.value = "Select a valid quiz attempt.";
    return;
  }

  const version = pageVersion;

  isSending.value = true;

  try {
    await requestApi(feedbackPath.value, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message,
        attempt_id: attemptId,
      }),
    });

    if (version !== pageVersion) return;

    feedbackMessage.value = "";
    selectedAttemptId.value = "";
    successMessage.value = "Feedback sent successfully.";

    await loadFeedback();
  } catch (error) {
    if (version !== pageVersion) return;

    sendError.value =
      error instanceof Error ? error.message : "Could not send feedback.";
  } finally {
    if (version === pageVersion) {
      isSending.value = false;
    }
  }
}

function goBackToAnalytics() {
  router.push({
    name: "teacher-class-analytics",
    params: {
      classroomId: classroomId.value,
    },
  });
}

function formatDate(dateValue) {
  if (!dateValue) return "No activity yet";

  const date = new Date(dateValue);

  if (Number.isNaN(date.getTime())) return "Date unavailable";

  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function scoreClass(percentage) {
  if (percentage >= 70) return "good-score";
  if (percentage < 50) return "needs-support";
  return "average-score";
}

function feedbackAttemptLabel(attemptId) {
  if (attemptId === null || attemptId === undefined) {
    return "General feedback";
  }

  const attempt = attempts.value.find((item) => item.id === attemptId);

  return attempt
    ? `${attempt.topic} · Attempt #${attempt.id}`
    : `Quiz attempt #${attemptId}`;
}

// Vue Router can reuse this page when the student ID changes.
watch(
  () => [route.params.classroomId, route.params.studentId],
  () => {
    pageVersion += 1;

    history.value = null;
    isLoading.value = false;
    loadError.value = "";

    feedbackItems.value = [];
    feedbackPage.value = 0;
    hasMoreFeedback.value = false;
    isFeedbackLoading.value = false;
    feedbackLoadError.value = "";

    feedbackMessage.value = "";
    selectedAttemptId.value = "";
    isSending.value = false;
    sendError.value = "";
    successMessage.value = "";

    loadAttemptHistory();
  },
  { immediate: true },
);
</script>

<template>
  <section class="history-page">
    <button type="button" class="back-button" @click="goBackToAnalytics">
      ← Back to class analytics
    </button>

    <p v-if="isLoading" class="status-note" role="status">
      Loading student attempt history...
    </p>

    <section v-else-if="loadError" class="error-state">
      <h1>Could not load attempt history</h1>
      <p>{{ loadError }}</p>

      <div class="error-actions">
        <button
          type="button"
          class="secondary-button"
          @click="loadAttemptHistory"
        >
          Try again
        </button>

        <button type="button" class="primary-button" @click="goBackToAnalytics">
          Back to analytics
        </button>
      </div>
    </section>

    <template v-else-if="history">
      <header class="history-header">
        <p class="eyebrow">STUDENT ATTEMPT HISTORY</p>
        <h1>{{ history.student.name }}</h1>
        <p class="student-email">{{ history.student.email }}</p>
        <p class="intro">
          {{ history.classroom.name }} class-er quiz performance timeline.
        </p>
      </header>

      <section class="summary-grid" aria-label="Student history summary">
        <article class="summary-card">
          <span>Total attempts</span>
          <strong>{{ attempts.length }}</strong>
          <small>All completed quizzes</small>
        </article>

        <article class="summary-card">
          <span>Latest result</span>
          <strong
            v-if="latestAttempt"
            :class="scoreClass(latestAttempt.percentage)"
          >
            {{ latestAttempt.percentage }}%
          </strong>
          <strong v-else>—</strong>
          <small>
            {{ latestAttempt ? latestAttempt.topic : "No quiz completed yet" }}
          </small>
        </article>

        <article class="summary-card">
          <span>Average score</span>
          <strong
            v-if="averagePercentage !== null"
            :class="scoreClass(averagePercentage)"
          >
            {{ averagePercentage }}%
          </strong>
          <strong v-else>—</strong>
          <small>Across all quiz attempts</small>
        </article>
      </section>

      <section class="feedback-panel" aria-labelledby="feedback-heading">
        <p class="eyebrow">TEACHER SUPPORT</p>
        <h2 id="feedback-heading">Send feedback</h2>
        <p class="intro">
          Student-ke learning advice dao, ba specific quiz result niye feedback
          pathao.
        </p>

        <form class="feedback-form" @submit.prevent="sendFeedback">
          <div class="form-field">
            <label for="feedback-attempt">Feedback about</label>
            <select
              id="feedback-attempt"
              v-model="selectedAttemptId"
              :disabled="isSending"
            >
              <option value="">General learning feedback</option>
              <option
                v-for="attempt in attempts"
                :key="attempt.id"
                :value="attempt.id"
              >
                {{ attempt.topic }} — {{ attempt.percentage }}% —
                {{ formatDate(attempt.completed_at) }} — #{{ attempt.id }}
              </option>
            </select>
          </div>

          <div class="form-field">
            <label for="feedback-message">Your feedback</label>
            <textarea
              id="feedback-message"
              v-model="feedbackMessage"
              rows="5"
              maxlength="2000"
              placeholder="Example: Binary conversion-er place values abar practice koro. Tarpor quiz-ta retry koro."
              :disabled="isSending"
              required
            ></textarea>
            <small class="character-count">
              {{ feedbackMessage.length }}/2000 characters
            </small>
          </div>

          <p v-if="sendError" class="error-message" role="alert">
            {{ sendError }}
          </p>

          <p v-if="successMessage" class="success-message" role="status">
            {{ successMessage }}
          </p>

          <button
            type="submit"
            class="primary-button"
            :disabled="
              isSending || isFeedbackLoading || !feedbackMessage.trim()
            "
          >
            {{ isSending ? "Sending..." : "Send feedback" }}
          </button>
        </form>

        <div class="feedback-history">
          <h3>Previously sent feedback</h3>

          <p
            v-if="isFeedbackLoading && feedbackItems.length === 0"
            class="status-note"
            role="status"
          >
            Loading feedback...
          </p>

          <p
            v-else-if="feedbackItems.length === 0 && !feedbackLoadError"
            class="status-note"
          >
            No feedback sent yet.
          </p>

          <div v-if="feedbackItems.length > 0" class="feedback-list">
            <article
              v-for="item in feedbackItems"
              :key="item.id"
              class="feedback-card"
            >
              <div class="feedback-meta">
                <strong>
                  {{ feedbackAttemptLabel(item.attempt_id) }}
                </strong>
                <span>{{ formatDate(item.created_at) }}</span>
              </div>
              <p class="feedback-content">{{ item.message }}</p>
            </article>
          </div>

          <div v-if="feedbackLoadError" class="feedback-error">
            <p class="error-message" role="alert">
              {{ feedbackLoadError }}
            </p>
            <button
              type="button"
              class="secondary-button"
              :disabled="isFeedbackLoading || isSending"
              @click="loadFeedback()"
            >
              Retry feedback list
            </button>
          </div>

          <button
            v-if="hasMoreFeedback && !feedbackLoadError"
            type="button"
            class="secondary-button load-more"
            :disabled="isFeedbackLoading || isSending"
            @click="loadFeedback(true)"
          >
            {{ isFeedbackLoading ? "Loading..." : "Load older feedback" }}
          </button>
        </div>
      </section>

      <section class="attempts-panel" aria-labelledby="attempts-heading">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">QUIZ TIMELINE</p>
            <h2 id="attempts-heading">All attempts</h2>
          </div>
          <span class="attempt-count"> {{ attempts.length }} attempts </span>
        </div>

        <div v-if="attempts.length === 0" class="empty-state">
          <h3>No quiz attempts yet</h3>
          <p>Ei student ekhono kono quiz complete kore nai.</p>
        </div>

        <div v-else class="attempt-list">
          <article
            v-for="(attempt, index) in attempts"
            :key="attempt.id"
            class="attempt-card"
          >
            <div class="attempt-number" aria-hidden="true">
              {{ attempts.length - index }}
            </div>

            <div class="attempt-main">
              <h3>{{ attempt.topic }}</h3>
              <p>{{ formatDate(attempt.completed_at) }}</p>
            </div>

            <div class="attempt-score">
              <span>Score</span>
              <strong :class="scoreClass(attempt.percentage)">
                {{ attempt.score }}/{{ attempt.total_questions }}
              </strong>
            </div>

            <div class="attempt-score">
              <span>Percentage</span>
              <strong :class="scoreClass(attempt.percentage)">
                {{ attempt.percentage }}%
              </strong>
            </div>
          </article>
        </div>
      </section>
    </template>
  </section>
</template>

<style scoped>
.history-page {
  display: grid;
  gap: 1.5rem;
  min-width: 0;
}

.back-button,
.primary-button,
.secondary-button {
  width: fit-content;
  border: 1px solid transparent;
  border-radius: 0.7rem;
  padding: 0.75rem 0.95rem;
  cursor: pointer;
  font: inherit;
  font-weight: 700;
  transition:
    background-color 0.2s ease,
    color 0.2s ease,
    transform 0.2s ease;
}

.back-button,
.secondary-button {
  border-color: var(--border-color);
  background: var(--surface-color);
  color: var(--accent-color);
}

.back-button:hover:not(:disabled),
.secondary-button:hover:not(:disabled) {
  background: var(--nav-hover);
}

.primary-button {
  background: var(--accent-color);
  color: var(--surface-color);
}

.primary-button:hover:not(:disabled) {
  background: var(--accent-hover);
}

button:active:not(:disabled) {
  transform: scale(0.97);
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

button:focus-visible,
select:focus-visible,
textarea:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

.eyebrow {
  margin: 0 0 0.55rem;
  color: var(--accent-color);
  font-size: 0.73rem;
  font-weight: 800;
  letter-spacing: 0.1em;
}

h1,
h2,
h3 {
  margin: 0;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

h1 {
  font-size: clamp(1.8rem, 4vw, 2.5rem);
  line-height: 1.2;
}

h2 {
  font-size: 1.2rem;
}

h3 {
  font-size: 1rem;
  line-height: 1.4;
}

.student-email,
.intro {
  color: var(--text-secondary);
  line-height: 1.65;
}

.student-email {
  margin: 0.35rem 0 0;
}

.intro {
  margin: 0.65rem 0 0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.summary-card,
.attempts-panel,
.feedback-panel,
.error-state {
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  background: var(--surface-color);
}

.summary-card {
  display: grid;
  gap: 0.35rem;
  padding: 1.2rem;
}

.summary-card span,
.summary-card small {
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.45;
}

.summary-card strong {
  color: var(--text-primary);
  font-size: 1.7rem;
  line-height: 1.2;
}

.attempts-panel,
.feedback-panel {
  padding: 1.5rem;
}

.panel-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 1rem;
}

.panel-heading .eyebrow {
  margin-bottom: 0.4rem;
}

.attempt-count {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 0.4rem 0.65rem;
  background: var(--nav-hover);
  color: var(--accent-color);
  font-size: 0.82rem;
  font-weight: 700;
}

.attempt-list {
  display: grid;
  gap: 0.75rem;
  margin-top: 1.35rem;
}

.attempt-card {
  display: grid;
  grid-template-columns: auto minmax(10rem, 1fr) 0.75fr 0.75fr;
  align-items: center;
  gap: 1rem;
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 0.85rem;
  padding: 1rem;
  background: var(--page-background);
}

.attempt-number {
  display: grid;
  width: 2rem;
  height: 2rem;
  place-items: center;
  border-radius: 50%;
  background: var(--nav-hover);
  color: var(--accent-color);
  font-size: 0.85rem;
  font-weight: 800;
}

.attempt-main p {
  margin: 0.25rem 0 0;
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.45;
}

.attempt-score {
  display: grid;
  gap: 0.35rem;
}

.attempt-score span {
  color: var(--text-secondary);
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.attempt-score strong {
  color: var(--text-primary);
  font-size: 1rem;
}

.good-score {
  color: #15803d !important;
}

.average-score {
  color: #b45309 !important;
}

.needs-support {
  color: #dc2626 !important;
}

.feedback-form {
  display: grid;
  gap: 1rem;
  margin-top: 1.25rem;
}

.form-field {
  display: grid;
  gap: 0.55rem;
  min-width: 0;
}

label {
  color: var(--text-primary);
  font-size: 0.9rem;
  font-weight: 700;
}

select,
textarea {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid var(--border-color);
  border-radius: 0.7rem;
  padding: 0.85rem;
  background: var(--page-background);
  color: var(--text-primary);
  font: inherit;
  line-height: 1.6;
}

textarea {
  resize: vertical;
  min-height: 8rem;
}

.character-count {
  color: var(--text-secondary);
  text-align: right;
}

.feedback-history {
  display: grid;
  gap: 1rem;
  margin-top: 1.75rem;
  border-top: 1px solid var(--border-color);
  padding-top: 1.25rem;
}

.feedback-list {
  display: grid;
  gap: 0.75rem;
}

.feedback-card {
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 0.85rem;
  padding: 1rem;
  background: var(--page-background);
}

.feedback-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 0.5rem;
}

.feedback-meta strong {
  color: var(--accent-color);
  font-size: 0.85rem;
  overflow-wrap: anywhere;
}

.feedback-meta span {
  color: var(--text-secondary);
  font-size: 0.8rem;
}

.feedback-content {
  margin: 0.75rem 0 0;
  color: var(--text-primary);
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.feedback-error {
  display: grid;
  gap: 0.75rem;
}

.error-message,
.success-message {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.6;
}

.error-message {
  color: #dc2626;
}

.success-message {
  color: var(--accent-color);
}

.empty-state,
.error-state {
  margin-top: 1.35rem;
  padding: 1.5rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.empty-state p,
.error-state p {
  margin: 0.55rem 0 0;
}

.error-state {
  margin-top: 0;
}

.error-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1rem;
}

.status-note {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

@media (max-width: 760px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .attempts-panel,
  .feedback-panel {
    padding: 1rem;
  }

  .panel-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .attempt-card {
    grid-template-columns: auto 1fr;
    gap: 0.9rem;
  }

  .attempt-main {
    min-width: 0;
  }

  .attempt-score {
    grid-column: span 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  button {
    transition: none;
  }
}
.history-page .back-button,
.history-page .primary-button,
.history-page .secondary-button {
  border-color: #2450db;
  background: #2450db;
  color: #fff;
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.history-page button:hover:not(:disabled) {
  border-color: #1d3fb8;
  background: #1d3fb8;
  color: #fff;
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.history-page button:active:not(:disabled) {
  transform: scale(0.98);
}

.history-page button:focus-visible {
  outline: 2px solid #2450db;
  outline-offset: 3px;
}
</style>
