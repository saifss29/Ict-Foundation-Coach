<script setup>
import { onMounted, onBeforeUnmount, ref } from "vue";
import { onBeforeRouteLeave, useRouter } from "vue-router";
import { useStore } from "vuex";
import TeacherQuizMistakeReport from "../components/TeacherQuizMistakeReport.vue";
import { confirmAction } from "../services/confirm_dialog";
const router = useRouter();
const store = useStore();

const busy = ref("");
const errorMessage = ref("");

const expandedAssignmentId = ref("");

const assignedQuizzes = ref([]);
const assignmentPage = ref(1);
const assignmentsHasMore = ref(false);
const assignmentsLoaded = ref(false);

const selectedResults = ref(null);
const resultsPage = ref(1);
const resultsHasMore = ref(false);
const resultsError = ref("");

const submissionReview = ref(null);
const reviewAttemptId = ref("");
const submissionReviewError = ref("");

const feedbackMessage = ref("");
const feedbackError = ref("");
const feedbackSuccess = ref("");

let active = true;

const reviewOptions = [
  { key: "A", field: "option_a" },
  { key: "B", field: "option_b" },
  { key: "C", field: "option_c" },
  { key: "D", field: "option_d" },
];

function firstValidationMessage(value) {
  if (typeof value === "string") return value;

  if (value && typeof value === "object") {
    for (const child of Object.values(value)) {
      const message = firstValidationMessage(child);
      if (message) return message;
    }
  }

  return "";
}

async function api(path, options = {}) {
  const token = store.state.auth.accessToken;

  const response = await fetch(`http://127.0.0.1:5000${path}`, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${token}`,
    },
  });

  if (!active || token !== store.state.auth.accessToken) {
    throw new Error("Request cancelled because the session changed.");
  }

  if (response.status === 401) {
    store.commit("auth/CLEAR_AUTH");
    await router.replace("/login");

    throw new Error("Your session has expired. Please log in again.");
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error("Could not read the server response. Please try again.");
  }

  if (!active || token !== store.state.auth.accessToken) {
    throw new Error("Request cancelled because the session changed.");
  }

  if (!response.ok) {
    throw new Error(
      firstValidationMessage(data.messages) ||
        data.error ||
        "Could not complete the request.",
    );
  }

  return data;
}

function jsonOptions(method, body) {
  return {
    method,
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  };
}

async function runAction(name, action) {
  if (busy.value) return;

  busy.value = name;
  errorMessage.value = "";

  try {
    await action();
  } catch (error) {
    if (!active) return;

    errorMessage.value =
      error instanceof Error ? error.message : "Something went wrong.";
  } finally {
    if (active) {
      busy.value = "";
    }
  }
}

async function canDiscardFeedback() {
  if (!active || busy.value) return false;
  if (!feedbackMessage.value.trim()) return true;

  const review = submissionReview.value;
  const token = store.state.auth.accessToken;

  busy.value = "confirmation";

  try {
    const accepted = await confirmAction({
      title: "Discard unsent feedback?",
      message: "Your unsent feedback will be lost. Do you want to continue?",
      confirmText: "Discard feedback",
      cancelText: "Keep editing",
      variant: "warning",
    });

    return (
      accepted &&
      active &&
      submissionReview.value === review &&
      store.state.auth.accessToken === token
    );
  } finally {
    if (active) busy.value = "";
  }
}
function clearSubmissionReview() {
  submissionReview.value = null;
  reviewAttemptId.value = "";
  submissionReviewError.value = "";
  feedbackMessage.value = "";
  feedbackError.value = "";
  feedbackSuccess.value = "";
}

async function closeSubmissionReview() {
  if (busy.value) return;
  if (!(await canDiscardFeedback())) return;

  clearSubmissionReview();
}

function formatAssignmentDate(value) {
  if (typeof value !== "string") return "Unavailable";

  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value)
    ? value
    : `${value}Z`;

  const date = new Date(normalized);

  if (Number.isNaN(date.getTime())) return "Unavailable";

  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function attemptStatusLabel(status) {
  return (
    {
      not_started: "Not started",
      in_progress: "In progress",
      expired: "Expired",
      submitted: "Submitted",
    }[status] || status
  );
}

async function loadAssignedQuizzes(nextPage = assignmentPage.value) {
  if (busy.value) return;
  if (!(await canDiscardFeedback())) return;

  await runAction("assignment-list", async () => {
    const data = await api(`/api/quiz-assignments?page=${nextPage}`);

    clearSubmissionReview();
    selectedResults.value = null;
    expandedAssignmentId.value = "";
    resultsError.value = "";

    assignedQuizzes.value = data.assignments;
    assignmentPage.value = data.pagination.page;
    assignmentsHasMore.value = data.pagination.has_more;
    assignmentsLoaded.value = true;
  });
}

async function loadTeacherResults(assignmentId, nextPage = 1) {
  if (busy.value) return;
  if (!(await canDiscardFeedback())) return;

  expandedAssignmentId.value = assignmentId;

  await runAction("assignment-results", async () => {
    resultsError.value = "";
    clearSubmissionReview();

    if (selectedResults.value?.assignment.id !== assignmentId) {
      selectedResults.value = null;
    }

    try {
      const data = await api(
        `/api/quiz-assignments/${assignmentId}/results?page=${nextPage}`,
      );

      selectedResults.value = data;
      resultsPage.value = data.pagination.page;
      resultsHasMore.value = data.pagination.has_more;
    } catch (error) {
      if (!active) return;

      resultsError.value =
        error instanceof Error
          ? error.message
          : "Could not load assignment results.";
    }
  });
}

async function toggleResults(assignmentId) {
  if (busy.value) return;

  if (expandedAssignmentId.value === assignmentId) {
    if (!(await canDiscardFeedback())) return;

    expandedAssignmentId.value = "";
    selectedResults.value = null;
    resultsError.value = "";
    clearSubmissionReview();
    return;
  }

  loadTeacherResults(assignmentId);
}

async function loadSubmissionReview(assignmentId, attemptId) {
  if (busy.value) return;
  if (!(await canDiscardFeedback())) return;

  await runAction("submission-review", async () => {
    clearSubmissionReview();
    reviewAttemptId.value = attemptId;

    try {
      const data = await api(
        `/api/quiz-assignments/${assignmentId}` +
          `/attempts/${attemptId}/teacher-review`,
      );

      submissionReview.value = data.review;
    } catch (error) {
      if (!active) return;

      submissionReviewError.value =
        error instanceof Error
          ? error.message
          : "Could not load student submission.";
    }
  });
}

async function sendReviewFeedback() {
  if (busy.value || !submissionReview.value) return;

  const review = submissionReview.value;
  const message = feedbackMessage.value.trim();

  feedbackError.value = "";
  feedbackSuccess.value = "";

  if (!message) {
    feedbackError.value = "Write feedback before sending.";
    return;
  }

  if (!Number.isInteger(review.quiz_attempt_id) || review.quiz_attempt_id < 1) {
    feedbackError.value =
      "Reload the submission review before sending feedback.";
    return;
  }

  await runAction("review-feedback", async () => {
    try {
      await api(
        `/api/feedback/classes/${review.classroom_id}` +
          `/students/${review.student_id}`,
        jsonOptions("POST", {
          message,
          attempt_id: review.quiz_attempt_id,
        }),
      );

      feedbackMessage.value = "";
      feedbackSuccess.value = "Feedback sent. Student notification saved.";
    } catch (error) {
      if (!active) return;

      feedbackError.value =
        error instanceof Error ? error.message : "Could not send feedback.";
    }
  });
}

onBeforeRouteLeave(async () => {
  if (!store.getters["auth/isAuthenticated"]) return true;

  return await canDiscardFeedback();
});
onBeforeUnmount(() => {
  active = false;
});

onMounted(() => {
  loadAssignedQuizzes(1);
});
</script>

<template>
  <section class="quiz-page" :aria-busy="Boolean(busy)">
    <header class="page-header">
      <p class="eyebrow">TEACHER</p>

      <h1>Assigned Quizzes</h1>

      <p class="description">
        Open an assignment to see its class report, results and submission
        reviews below that card.
      </p>

      <RouterLink class="navigation-link" :to="{ name: 'teacher-quizzes' }">
        Generate a quiz
      </RouterLink>
    </header>

    <p v-if="errorMessage" class="error" role="alert">
      {{ errorMessage }}
    </p>

    <section class="panel">
      <div class="heading-row">
        <h2>Your assigned quizzes</h2>

        <button
          type="button"
          :disabled="Boolean(busy)"
          @click="loadAssignedQuizzes(assignmentPage)"
        >
          {{
            busy === "assignment-list" ? "Loading..." : "Refresh assignments"
          }}
        </button>
      </div>

      <p
        v-if="assignmentsLoaded && assignedQuizzes.length === 0"
        class="description"
      >
        No assignments on this page.
      </p>

      <div class="quiz-list">
        <article
          v-for="assignment in assignedQuizzes"
          :key="assignment.id"
          class="question-card"
        >
          <h3>{{ assignment.quiz_title }}</h3>

          <p class="description">
            {{ assignment.classroom_name }} ·
            {{ assignment.recipient_count }} students ·
            {{ assignment.question_count }} questions
          </p>

          <p class="description">
            Available: {{ formatAssignmentDate(assignment.available_at) }}
            <br />
            Deadline: {{ formatAssignmentDate(assignment.deadline_at) }}
          </p>

          <button
            type="button"
            :disabled="Boolean(busy)"
            :aria-expanded="expandedAssignmentId === assignment.id"
            :aria-controls="`assignment-results-${assignment.id}`"
            @click="toggleResults(assignment.id)"
          >
            {{
              expandedAssignmentId === assignment.id
                ? "Close results"
                : "View results"
            }}
          </button>

          <div
            v-if="expandedAssignmentId === assignment.id"
            :id="`assignment-results-${assignment.id}`"
            class="expanded-content"
          >
            <p
              v-if="busy === 'assignment-results'"
              class="description"
              role="status"
            >
              Loading results...
            </p>

            <p v-if="resultsError" class="error" role="alert">
              {{ resultsError }}
            </p>

            <TeacherQuizMistakeReport
              :key="assignment.id"
              :assignment-id="assignment.id"
            />

            <section
              v-if="selectedResults?.assignment.id === assignment.id"
              class="inline-results"
            >
              <div class="heading-row">
                <h2>Results: {{ selectedResults.assignment.quiz_title }}</h2>

                <button
                  type="button"
                  :disabled="Boolean(busy)"
                  @click="
                    loadTeacherResults(
                      selectedResults.assignment.id,
                      resultsPage,
                    )
                  "
                >
                  Refresh results
                </button>
              </div>

              <p class="description">
                {{ selectedResults.assignment.classroom_name }} ·
                {{ selectedResults.assignment.recipient_count }}
                assigned students ·
                {{ selectedResults.assignment.max_attempts }}
                allowed attempts
              </p>

              <p
                v-if="selectedResults.students.length === 0"
                class="description"
              >
                No students on this page.
              </p>

              <div class="quiz-list">
                <article
                  v-for="student in selectedResults.students"
                  :key="student.student_id"
                  class="question-card"
                >
                  <div class="heading-row">
                    <h3>{{ student.student_name }}</h3>

                    <span class="badge">
                      {{ attemptStatusLabel(student.latest_status) }}
                    </span>
                  </div>

                  <p class="description">
                    Attempts used: {{ student.attempts_used }} /
                    {{ selectedResults.assignment.max_attempts }} · Submitted:
                    {{ student.submitted_attempts }}
                  </p>

                  <p v-if="student.best_score !== null" class="best-score">
                    Best submitted score:
                    {{ student.best_score }} /
                    {{ student.best_total_questions }}
                  </p>

                  <p v-else class="description">No submitted score yet.</p>

                  <details v-if="student.attempts.length">
                    <summary>Show attempts</summary>

                    <div class="attempt-results">
                      <article
                        v-for="attempt in student.attempts"
                        :key="attempt.id"
                        class="attempt-result"
                      >
                        <div class="heading-row">
                          <strong>
                            Attempt {{ attempt.attempt_number }}
                          </strong>

                          <span>
                            {{ attemptStatusLabel(attempt.status) }}
                          </span>
                        </div>

                        <p v-if="attempt.status === 'submitted'">
                          Score: {{ attempt.score }} /
                          {{ attempt.total_questions }}
                          <br />
                          Submitted:
                          {{ formatAssignmentDate(attempt.submitted_at) }}
                        </p>

                        <p v-else class="description">
                          {{
                            attempt.status === "expired"
                              ? "Time expired; this attempt has not been submitted."
                              : "Student is taking this quiz."
                          }}
                        </p>

                        <p class="description">
                          Started:
                          {{ formatAssignmentDate(attempt.started_at) }}
                          <br />
                          Expires:
                          {{ formatAssignmentDate(attempt.expires_at) }}
                        </p>

                        <button
                          v-if="attempt.status === 'submitted'"
                          type="button"
                          :disabled="Boolean(busy)"
                          @click="
                            loadSubmissionReview(
                              selectedResults.assignment.id,
                              attempt.id,
                            )
                          "
                        >
                          {{
                            busy === "submission-review" &&
                            reviewAttemptId === attempt.id
                              ? "Loading review..."
                              : "Review submission"
                          }}
                        </button>

                        <section
                          v-if="reviewAttemptId === attempt.id"
                          class="submission-review"
                          :aria-busy="busy === 'submission-review'"
                          aria-label="Student submission review"
                        >
                          <div class="heading-row">
                            <h3>Submission review</h3>

                            <button
                              type="button"
                              :disabled="Boolean(busy)"
                              @click="closeSubmissionReview"
                            >
                              Close review
                            </button>
                          </div>

                          <p
                            v-if="busy === 'submission-review'"
                            class="description"
                            role="status"
                          >
                            Loading answers...
                          </p>

                          <p
                            v-if="submissionReviewError"
                            class="error"
                            role="alert"
                          >
                            {{ submissionReviewError }}
                          </p>

                          <template v-if="submissionReview">
                            <p class="description">
                              {{ submissionReview.student_name }} ·
                              {{ submissionReview.classroom_name }} · Attempt
                              {{ submissionReview.attempt_number }}
                              <br />
                              Score: {{ submissionReview.score }} /
                              {{ submissionReview.total_questions }}
                            </p>

                            <article
                              v-for="(
                                question, index
                              ) in submissionReview.questions"
                              :key="question.id"
                              class="review-question"
                            >
                              <div class="heading-row">
                                <h4>
                                  {{ index + 1 }}.
                                  {{ question.question_text }}
                                </h4>

                                <span class="badge">
                                  {{
                                    !question.selected_option
                                      ? "Unanswered"
                                      : question.is_correct
                                        ? "Correct"
                                        : "Incorrect"
                                  }}
                                </span>
                              </div>

                              <ul class="review-options">
                                <li
                                  v-for="option in reviewOptions"
                                  :key="option.key"
                                  :class="{
                                    'answer-correct':
                                      question.correct_option === option.key,
                                    'answer-wrong':
                                      question.selected_option === option.key &&
                                      !question.is_correct,
                                  }"
                                >
                                  <span>
                                    <strong>{{ option.key }}.</strong>
                                    {{ question[option.field] }}
                                  </span>

                                  <span
                                    v-if="
                                      question.selected_option === option.key
                                    "
                                    class="answer-label"
                                  >
                                    Student selected
                                  </span>

                                  <span
                                    v-if="
                                      question.correct_option === option.key
                                    "
                                    class="answer-label"
                                  >
                                    Correct answer
                                  </span>
                                </li>
                              </ul>

                              <p class="review-explanation">
                                <strong>Explanation:</strong>
                                {{ question.explanation }}
                              </p>
                            </article>

                            <form
                              class="review-feedback"
                              @submit.prevent="sendReviewFeedback"
                            >
                              <h4>
                                Send feedback to
                                {{ submissionReview.student_name }}
                              </h4>

                              <label :for="`review-feedback-${attempt.id}`">
                                Learning feedback

                                <textarea
                                  :id="`review-feedback-${attempt.id}`"
                                  v-model="feedbackMessage"
                                  rows="4"
                                  required
                                  :disabled="Boolean(busy)"
                                ></textarea>
                              </label>

                              <p
                                v-if="feedbackError"
                                class="error"
                                role="alert"
                              >
                                {{ feedbackError }}
                              </p>

                              <p
                                v-if="feedbackSuccess"
                                class="success"
                                role="status"
                              >
                                {{ feedbackSuccess }}
                              </p>

                              <button
                                type="submit"
                                class="primary"
                                :disabled="
                                  Boolean(busy) || !feedbackMessage.trim()
                                "
                              >
                                {{
                                  busy === "review-feedback"
                                    ? "Sending feedback..."
                                    : "Send feedback"
                                }}
                              </button>
                            </form>
                          </template>
                        </section>
                      </article>
                    </div>
                  </details>
                </article>
              </div>

              <nav
                class="heading-row pagination"
                aria-label="Results student pages"
              >
                <button
                  type="button"
                  :disabled="Boolean(busy) || resultsPage <= 1"
                  @click="
                    loadTeacherResults(
                      selectedResults.assignment.id,
                      resultsPage - 1,
                    )
                  "
                >
                  Previous
                </button>

                <span>Student page {{ resultsPage }}</span>

                <button
                  type="button"
                  :disabled="Boolean(busy) || !resultsHasMore"
                  @click="
                    loadTeacherResults(
                      selectedResults.assignment.id,
                      resultsPage + 1,
                    )
                  "
                >
                  Next
                </button>
              </nav>
            </section>
          </div>
        </article>
      </div>

      <nav class="heading-row pagination" aria-label="Assignment pages">
        <button
          type="button"
          :disabled="Boolean(busy) || assignmentPage <= 1"
          @click="loadAssignedQuizzes(assignmentPage - 1)"
        >
          Previous
        </button>

        <span>Page {{ assignmentPage }}</span>

        <button
          type="button"
          :disabled="Boolean(busy) || !assignmentsHasMore"
          @click="loadAssignedQuizzes(assignmentPage + 1)"
        >
          Next
        </button>
      </nav>
    </section>
  </section>
</template>

<style scoped>
.quiz-page {
  display: grid;
  gap: 1.5rem;
  min-width: 0;
  color: var(--text-primary);
}

.page-header {
  display: grid;
  gap: 0.75rem;
}

.eyebrow {
  margin: 0;
  color: var(--accent-color);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.1em;
}

h1,
h2,
h3,
h4 {
  margin: 0;
  overflow-wrap: anywhere;
}

h1 {
  font-size: clamp(1.6rem, 4vw, 2.4rem);
}

h2 {
  font-size: 1.2rem;
}

h3 {
  font-size: 1rem;
}

.description {
  color: var(--text-secondary);
  line-height: 1.7;
  overflow-wrap: anywhere;
}

.page-header .description {
  margin: 0;
}

.navigation-link {
  justify-self: start;
  color: var(--accent-color);
  font-weight: 700;
}

.panel {
  min-width: 0;
  padding: 1.5rem;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 1rem;
}

label,
.question-card {
  display: grid;
  gap: 0.65rem;
}

label {
  min-width: 0;
  font-weight: 600;
  font-size: 0.9rem;
}

textarea,
button {
  font: inherit;
  box-sizing: border-box;
  border: 1px solid var(--border-color);
  border-radius: 0.65rem;
}

textarea {
  width: 100%;
  min-width: 0;
  padding: 0.8rem;
  color: var(--text-primary);
  background: var(--page-background);
  resize: vertical;
}

button {
  padding: 0.75rem 1rem;
  background: var(--page-background);
  color: var(--accent-color);
  font-weight: 700;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    background-color 0.2s ease;
}

button:hover:not(:disabled) {
  background: var(--nav-hover);
  transform: translateY(-2px);
}

button:active:not(:disabled) {
  transform: scale(0.98);
}

.primary {
  background: var(--accent-color);
  color: #fff;
}

.primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

textarea:focus-visible,
button:focus-visible,
.navigation-link:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

.heading-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.quiz-list {
  display: grid;
  gap: 0.75rem;
  margin-top: 1rem;
}

.pagination {
  margin-top: 1rem;
}

.question-card {
  min-width: 0;
  padding: 1rem;
  gap: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.8rem;
  background: var(--page-background);
}

.badge {
  padding: 0.4rem 0.7rem;
  border-radius: 0.5rem;
  color: var(--accent-color);
  background: var(--nav-hover);
  font-size: 0.85rem;
}

.error {
  color: #dc2626;
  line-height: 1.6;
}

.success {
  color: var(--accent-color);
  line-height: 1.6;
}

.best-score {
  margin: 0;
  color: var(--accent-color);
  font-weight: 700;
}

details {
  min-width: 0;
}

summary {
  cursor: pointer;
  color: var(--accent-color);
  font-weight: 600;
  padding: 0.5rem 0;
}

summary:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

.attempt-results {
  display: grid;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

.attempt-result {
  min-width: 0;
  padding: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.65rem;
  overflow-wrap: anywhere;
}

.submission-review {
  display: grid;
  gap: 1rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-color);
  min-width: 0;
}

.review-question {
  display: grid;
  gap: 0.9rem;
  padding: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.8rem;
  background: var(--surface-color);
  min-width: 0;
}

.review-question h4 {
  line-height: 1.6;
  white-space: pre-wrap;
}

.review-options {
  display: grid;
  gap: 0.6rem;
  list-style: none;
  margin: 0;
  padding: 0;
}

.review-options li {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.8rem;
  border: 1px solid var(--border-color);
  border-radius: 0.6rem;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.review-options .answer-correct {
  border-color: #16a34a;
  background: rgb(22 163 74 / 10%);
}

.review-options .answer-wrong {
  border-color: #dc2626;
  background: rgb(220 38 38 / 10%);
}

.answer-label {
  padding: 0.2rem 0.5rem;
  border-radius: 0.4rem;
  background: var(--nav-hover);
  color: var(--text-primary);
  font-size: 0.75rem;
  font-weight: 700;
}

.review-explanation {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.review-feedback {
  display: grid;
  gap: 1rem;
  padding: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.8rem;
  background: var(--surface-color);
  min-width: 0;
}

.review-feedback p {
  margin: 0;
}

.review-feedback button {
  justify-self: start;
}

.expanded-content {
  min-width: 0;
  margin-top: 1rem;
  border-top: 1px solid var(--border-color);
  padding-top: 1rem;
}

.inline-results {
  min-width: 0;
  margin-top: 1.5rem;
}

@media (max-width: 540px) {
  .panel {
    padding: 1rem;
  }

  .question-card,
  .attempt-result,
  .review-question,
  .review-feedback {
    padding: 0.8rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  button {
    transition: none;
  }

  button:hover:not(:disabled),
  button:active:not(:disabled) {
    transform: none;
  }
}
</style>
