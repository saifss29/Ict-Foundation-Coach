<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useStore } from "vuex";

const router = useRouter();
const store = useStore();
const controller = new AbortController();

const exams = ref([]);
const currentPage = ref(0);
const hasMore = ref(false);
const loading = ref(false);
const errorMessage = ref("");

const results = ref({});
const resultErrors = ref({});
const loadingResultId = ref(null);

function formatDate(value) {
  const date = new Date(value);

  if (!value || !Number.isFinite(date.getTime())) {
    return "Date unavailable";
  }

  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

async function api(path) {
  const token = store.state.auth.accessToken;

  if (!token) {
    await router.replace("/login");
    throw new Error("Please log in again.");
  }

  const response = await fetch(`http://127.0.0.1:5000${path}`, {
    signal: controller.signal,
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (token !== store.state.auth.accessToken) {
    throw new Error("Your account changed. Reload this page.");
  }

  if (response.status === 401) {
    store.commit("auth/CLEAR_AUTH");
    await router.replace("/login");
    throw new Error("Your session expired. Please log in again.");
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error("Could not read the server response.");
  }

  if (!response.ok) {
    throw new Error(data.error || "Could not load exam information.");
  }

  return data;
}

async function loadExams(append = false) {
  if (loading.value || loadingResultId.value !== null) return;

  const nextPage = append ? currentPage.value + 1 : 1;

  loading.value = true;
  errorMessage.value = "";

  try {
    const data = await api(`/api/class-exams?page=${nextPage}`);

    if (append) {
      const existingIds = new Set(exams.value.map((exam) => exam.id));

      exams.value.push(
        ...data.exams.filter((exam) => !existingIds.has(exam.id)),
      );
    } else {
      exams.value = data.exams;
      results.value = {};
      resultErrors.value = {};
    }

    currentPage.value = data.pagination.page;
    hasMore.value = data.pagination.has_more;
  } catch (error) {
    if (!controller.signal.aborted) {
      errorMessage.value =
        error instanceof Error ? error.message : "Could not load exams.";
    }
  } finally {
    loading.value = false;
  }
}

async function viewResult(exam) {
  if (
    loading.value ||
    loadingResultId.value !== null ||
    !exam.results_published_at
  ) {
    return;
  }

  loadingResultId.value = exam.id;
  resultErrors.value[exam.id] = "";
  delete results.value[exam.id];

  try {
    const data = await api(
      `/api/class-exams/${encodeURIComponent(exam.id)}/my-result`,
    );

    if (data.exam.id !== exam.id) {
      throw new Error("Unexpected exam response. Refresh the page.");
    }

    results.value[exam.id] = data.result;
  } catch (error) {
    if (!controller.signal.aborted) {
      resultErrors.value[exam.id] =
        error instanceof Error ? error.message : "Could not load your result.";
    }
  } finally {
    loadingResultId.value = null;
  }
}

onMounted(() => loadExams());
onBeforeUnmount(() => controller.abort());
</script>

<template>
  <section class="exam-results-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">YOUR CLASS EXAMS</p>
        <h1>Exam results</h1>
        <p class="intro">
          Class-e deya exam-er schedule ar teacher-published result ekhane
          dekhte parbe. Ekhane shudhu tomar nijer result dekhabe.
        </p>
      </div>

      <button
        type="button"
        :disabled="loading || loadingResultId !== null"
        @click="loadExams()"
      >
        {{ loading ? "Loading..." : "Refresh" }}
      </button>
    </header>

    <div v-if="errorMessage" class="error-state">
      <p class="error" role="alert">{{ errorMessage }}</p>
      <button
        type="button"
        :disabled="loading || loadingResultId !== null"
        @click="loadExams()"
      >
        Try again
      </button>
    </div>

    <p v-if="loading && exams.length === 0" class="intro" role="status">
      Loading your exams...
    </p>

    <p
      v-if="!loading && !errorMessage && exams.length === 0"
      class="empty-state"
    >
      No class exams yet. Teacher schedule korle ekhane dekhabe.
    </p>

    <div class="exam-list">
      <article v-for="exam in exams" :key="exam.id" class="exam-card">
        <header class="card-heading">
          <div>
            <p class="class-name">{{ exam.classroom_name }}</p>
            <h2>{{ exam.title }}</h2>
          </div>

          <span class="status">
            {{
              exam.results_published_at
                ? "Results published"
                : "Results pending"
            }}
          </span>
        </header>

        <p class="intro">
          Starts: {{ formatDate(exam.starts_at) }}
          <br />
          Ends: {{ formatDate(exam.ends_at) }}
        </p>

        <p class="intro">Total marks: {{ exam.total_marks }}</p>

        <p v-if="exam.description" class="instructions">
          {{ exam.description }}
        </p>

        <template v-if="exam.results_published_at">
          <p class="intro">
            Published {{ formatDate(exam.results_published_at) }}
          </p>

          <button
            type="button"
            class="result-button"
            :disabled="loading || loadingResultId !== null"
            @click="viewResult(exam)"
          >
            {{
              loadingResultId === exam.id
                ? "Loading result..."
                : results[exam.id]
                  ? "Reload my result"
                  : "View my result"
            }}
          </button>

          <p v-if="resultErrors[exam.id]" class="error" role="alert">
            {{ resultErrors[exam.id] }}
          </p>

          <div v-if="results[exam.id]" class="result-box" role="status">
            <p class="result-label">YOUR RESULT</p>

            <strong v-if="results[exam.id].is_absent"> Absent </strong>

            <strong v-else>
              {{ results[exam.id].obtained_marks }} /
              {{ exam.total_marks }}
            </strong>
          </div>
        </template>

        <p v-else class="pending-note">Teacher ekhono result publish koreni.</p>
      </article>
    </div>

    <button
      v-if="hasMore && !errorMessage"
      type="button"
      class="load-more"
      :disabled="loading || loadingResultId !== null"
      @click="loadExams(true)"
    >
      {{ loading ? "Loading..." : "Load more exams" }}
    </button>
  </section>
</template>

<style scoped>
.exam-results-page {
  display: grid;
  gap: 1.5rem;
  min-width: 0;
  color: var(--text-primary);
}

.page-heading,
.card-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

h1,
h2 {
  margin: 0;
  overflow-wrap: anywhere;
}

h1 {
  font-size: clamp(1.75rem, 4vw, 2.5rem);
}

h2 {
  font-size: 1.15rem;
}

.eyebrow,
.result-label {
  margin: 0 0 0.6rem;
  color: var(--accent-color);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.intro,
.pending-note {
  color: var(--text-secondary);
  line-height: 1.7;
}

.intro {
  margin: 0.75rem 0 0;
}

.class-name {
  margin: 0 0 0.5rem;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.exam-list {
  display: grid;
  gap: 1rem;
}

.exam-card,
.empty-state,
.error-state {
  min-width: 0;
  padding: 1.5rem;
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  background: var(--surface-color);
}

.empty-state {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.status {
  padding: 0.4rem 0.65rem;
  border-radius: 0.6rem;
  background: var(--nav-hover);
  color: var(--accent-color);
  font-size: 0.8rem;
  font-weight: 700;
}

.instructions {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.7;
}

button {
  width: fit-content;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.65rem;
  background: var(--page-background);
  color: var(--accent-color);
  cursor: pointer;
  font: inherit;
  font-weight: 700;
}

button:hover:not(:disabled) {
  background: var(--nav-hover);
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

button:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

.result-button {
  margin-top: 1rem;
}

.result-box {
  margin-top: 1rem;
  padding: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.8rem;
  background: var(--nav-hover);
}

.result-box strong {
  font-size: 1.5rem;
}

.error {
  color: #dc2626;
  line-height: 1.6;
}

.error-state .error {
  margin-top: 0;
}

@media (max-width: 600px) {
  .page-heading,
  .card-heading {
    flex-direction: column;
  }

  .exam-card,
  .empty-state,
  .error-state {
    padding: 1rem;
  }
}
button {
  padding: 0.7rem 1rem;
  border: 0;
  border-radius: 8px;
  background: #4f46e5;
  color: #fff;
  font: inherit;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    background-color 0.2s ease;
}

button:hover:not(:disabled) {
  background: #4338ca;
  color: #fff;
  transform: translateY(-2px);
}

button:active:not(:disabled) {
  transform: scale(0.98);
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

button:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

@media (prefers-reduced-motion: reduce) {
  button {
    transition: none;
  }
}
button {
  border: 1px solid transparent;
  border-radius: 0.65rem;
  padding: 0.75rem 1rem;
  background: #2450db;
  color: #fff;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

button:hover:not(:disabled) {
  background: #1d3fb8;
  color: #fff;
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

button:active:not(:disabled) {
  transform: scale(0.98);
}

button:focus-visible {
  outline: 2px solid #2450db;
  outline-offset: 3px;
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
