<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useStore } from "vuex";

const props = defineProps({
  assignmentId: {
    type: String,
    required: true,
  },
});

const router = useRouter();
const store = useStore();

const report = ref(null);
const loading = ref(false);
const errorMessage = ref("");
const statusFilter = ref("all");

let requestNumber = 0;
let controller = null;
let active = true;

const statusLabels = {
  submitted: "Submitted",
  not_started: "Not started",
  not_submitted: "Started but not submitted",
  in_progress: "In progress",
  expired: "Expired",
};

const mostMissedQuestions = computed(() => {
  if (!report.value) return [];

  const questionsById = new Map(
    report.value.questions.map((question) => [question.id, question]),
  );

  return report.value.most_missed_question_ids
    .map((id) => questionsById.get(id))
    .filter(Boolean);
});

function statusLabel(status) {
  return statusLabels[status] || status;
}

function percentage(value) {
  return value === null ? "No submissions" : `${value}%`;
}

async function loadReport(page = 1) {
  controller?.abort();

  const currentRequest = ++requestNumber;
  const token = store.state.auth.accessToken;
  const assignmentId = props.assignmentId;

  if (!assignmentId || !token) {
    report.value = null;
    loading.value = false;
    return;
  }

  controller = new AbortController();
  const signal = controller.signal;

  loading.value = true;
  errorMessage.value = "";

  const isCurrent = () =>
    active &&
    currentRequest === requestNumber &&
    token === store.state.auth.accessToken &&
    assignmentId === props.assignmentId;

  try {
    const query = new URLSearchParams({
      page: String(page),
      status: statusFilter.value,
    });

    const response = await fetch(
      `http://127.0.0.1:5000/api/quiz-assignments/` +
        `${encodeURIComponent(assignmentId)}/mistake-report?${query}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        signal,
      },
    );

    if (!isCurrent()) return;

    if (response.status === 401) {
      report.value = null;
      store.commit("auth/CLEAR_AUTH");
      await router.replace({ name: "login" });
      return;
    }

    let data;

    try {
      data = await response.json();
    } catch {
      throw new Error("Could not read the server response.");
    }

    if (!isCurrent()) return;

    if (!response.ok) {
      throw new Error(data.error || "Could not load the class report.");
    }

    report.value = data;
  } catch (error) {
    if (error?.name === "AbortError" || !isCurrent()) return;

    report.value = null;
    errorMessage.value =
      error instanceof Error
        ? error.message
        : "Could not load the class report.";
  } finally {
    if (active && currentRequest === requestNumber) {
      loading.value = false;
    }
  }
}

function changeFilter() {
  loadReport(1);
}

watch(
  () => props.assignmentId,
  () => {
    report.value = null;
    statusFilter.value = "all";
    loadReport(1);
  },
  { immediate: true },
);

watch(
  () => store.state.auth.accessToken,
  () => {
    report.value = null;
    loadReport(1);
  },
);

onBeforeUnmount(() => {
  active = false;
  requestNumber += 1;
  controller?.abort();
});
</script>

<template>
  <section class="mistake-report" aria-labelledby="mistake-report-title">
    <header class="report-heading">
      <div>
        <h2 id="mistake-report-title">Class Mistake Report</h2>
        <p>
          Question statistics use each student's latest submitted attempt.
          Unsubmitted answers are excluded.
        </p>
      </div>

      <button
        type="button"
        :disabled="loading"
        @click="loadReport(report?.pagination.page || 1)"
      >
        {{ loading ? "Loading..." : "Refresh report" }}
      </button>
    </header>

    <p v-if="errorMessage" class="error" role="alert">
      {{ errorMessage }}
    </p>

    <p v-if="loading" role="status">Loading class report...</p>

    <div v-if="report" :aria-busy="loading">
      <div class="summary-grid">
        <article>
          <span>Assigned students</span>
          <strong>{{ report.summary.recipient_count }}</strong>
        </article>

        <article>
          <span>Submitted at least once</span>
          <strong>{{ report.summary.submitted_students }}</strong>
        </article>

        <article>
          <span>Never started</span>
          <strong>{{ report.summary.not_started_students }}</strong>
        </article>

        <article>
          <span>Started, never submitted</span>
          <strong>{{ report.summary.not_submitted_students }}</strong>
        </article>
      </div>

      <p class="report-note">
        Without a submission:
        {{ report.summary.in_progress_students }} in progress,
        {{ report.summary.expired_without_submission_students }} expired.
      </p>

      <section class="report-section">
        <h3>Questions students got wrong most often</h3>

        <p v-if="report.summary.submitted_students === 0">
          No submitted attempts yet. Question statistics will appear after
          students submit.
        </p>

        <p v-else-if="mostMissedQuestions.length === 0">
          No wrong selected answers in the assessed submissions. Check the
          unanswered counts below too.
        </p>

        <ol v-else class="missed-list">
          <li v-for="question in mostMissedQuestions" :key="question.id">
            <strong>
              Question {{ question.question_number }}:
              {{ question.question_text }}
            </strong>
            <span>
              {{ question.wrong_count }} of
              {{ question.assessed_students }} students selected a wrong answer
              ({{ percentage(question.wrong_percentage) }}).
            </span>
          </li>
        </ol>
      </section>

      <section class="report-section">
        <h3>Question-by-question results</h3>
        <p>
          Wrong percentages use assessed students as the denominator. Unanswered
          responses are counted separately.
        </p>

        <div
          class="table-wrap"
          tabindex="0"
          role="region"
          aria-label="Question results, scroll horizontally if needed"
        >
          <table>
            <caption>
              Latest submitted attempt per student
            </caption>
            <thead>
              <tr>
                <th scope="col">Question</th>
                <th scope="col">Correct</th>
                <th scope="col">Wrong</th>
                <th scope="col">Unanswered</th>
                <th scope="col">Wrong %</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="question in report.questions" :key="question.id">
                <th scope="row" class="question-cell">
                  <strong>
                    {{ question.question_number }}.
                    {{ question.question_text }}
                  </strong>
                  <span>
                    Correct answer: {{ question.correct_option }} -
                    {{ question.correct_answer }}
                  </span>
                </th>
                <td>{{ question.correct_count }}</td>
                <td>{{ question.wrong_count }}</td>
                <td>{{ question.unanswered_count }}</td>
                <td>{{ percentage(question.wrong_percentage) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="report-section">
        <div class="report-heading">
          <h3>Student participation</h3>

          <label class="filter">
            Show students
            <select
              v-model="statusFilter"
              :disabled="loading"
              @change="changeFilter"
            >
              <option value="all">All assigned students</option>
              <option value="not_started">Never started</option>
              <option value="not_submitted">Started but never submitted</option>
              <option value="submitted">Submitted at least once</option>
            </select>
          </label>
        </div>

        <p>
          A student who submitted once remains in the Submitted group even if a
          later retry is still in progress.
        </p>

        <p v-if="report.students.length === 0">
          No students match this filter on this page.
        </p>

        <ul v-else class="student-list">
          <li v-for="student in report.students" :key="student.student_id">
            <strong>{{ student.student_name }}</strong>
            <div>
              <span>
                Participation:
                {{ statusLabel(student.participation_status) }}
              </span>
              <span>
                Latest attempt:
                {{ statusLabel(student.latest_attempt_status) }}
              </span>
            </div>
          </li>
        </ul>

        <nav class="pagination" aria-label="Participation report pages">
          <button
            type="button"
            :disabled="loading || report.pagination.page <= 1"
            @click="loadReport(report.pagination.page - 1)"
          >
            Previous
          </button>

          <span>
            Page {{ report.pagination.page }} ·
            {{ report.pagination.total }} matching students
          </span>

          <button
            type="button"
            :disabled="loading || !report.pagination.has_more"
            @click="loadReport(report.pagination.page + 1)"
          >
            Next
          </button>
        </nav>
      </section>
    </div>
  </section>
</template>

<style scoped>
.mistake-report {
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border-color, #8493a5);
  color: var(--text-primary, #243447);
  min-width: 0;
}

h2,
h3,
p {
  margin: 0;
}

h2,
h3,
strong,
span {
  overflow-wrap: anywhere;
}

p {
  margin-top: 0.65rem;
  line-height: 1.6;
}

.report-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 1rem;
}

.report-heading > div {
  flex: 1;
  min-width: 220px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.8rem;
  margin-top: 1.25rem;
}

.summary-grid article {
  display: grid;
  gap: 0.5rem;
  padding: 1rem;
  border: 1px solid var(--border-color, #8493a5);
  border-radius: 12px;
}

.summary-grid strong {
  font-size: 1.7rem;
}

.report-section {
  margin-top: 1.75rem;
}

.report-note,
.report-heading p,
.report-section > p {
  color: var(--text-secondary, #64748b);
}

button,
select {
  font: inherit;
  color: var(--text-primary, #243447);
  background: var(--bg-secondary, #f3f6fa);
  border: 1px solid var(--border-color, #8493a5);
  border-radius: 8px;
  padding: 0.65rem 0.85rem;
}

button {
  cursor: pointer;
  transition: transform 150ms ease;
}

button:hover:not(:disabled) {
  transform: translateY(-1px);
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

button:focus-visible,
select:focus-visible,
.table-wrap:focus-visible {
  outline: 3px solid var(--accent-color, #2563eb);
  outline-offset: 3px;
}

.error {
  color: var(--error-color, #dc2626);
}

.missed-list,
.student-list {
  display: grid;
  gap: 0.8rem;
  margin-top: 1rem;
}

.missed-list li span,
.question-cell span {
  display: block;
  margin-top: 0.4rem;
  font-weight: normal;
}

.table-wrap {
  overflow-x: auto;
  margin-top: 1rem;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 600px;
}

caption {
  text-align: left;
  padding-bottom: 0.75rem;
  color: var(--text-secondary, #64748b);
}

th,
td {
  border-bottom: 1px solid var(--border-color, #8493a5);
  padding: 0.8rem;
  text-align: left;
  vertical-align: top;
}

.question-cell {
  width: 55%;
}

.filter {
  display: grid;
  gap: 0.4rem;
}

.filter select {
  max-width: 100%;
}

.student-list {
  list-style: none;
  padding: 0;
}

.student-list li {
  padding: 1rem;
  border: 1px solid var(--border-color, #8493a5);
  border-radius: 10px;
}

.student-list li div {
  display: grid;
  gap: 0.3rem;
  margin-top: 0.5rem;
}

.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.8rem;
  margin-top: 1rem;
}

@media (max-width: 800px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 480px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .filter {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  button {
    transition: none;
  }

  button:hover:not(:disabled) {
    transform: none;
  }
}
</style>
