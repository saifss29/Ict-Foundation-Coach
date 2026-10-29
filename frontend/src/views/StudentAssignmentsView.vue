<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { onBeforeRouteLeave, RouterLink, useRouter } from "vue-router";
import { useStore } from "vuex";
import { confirmAction } from "../services/confirm_dialog";
const props = defineProps({
  historyView: {
    type: Boolean,
    default: false,
  },
  screen: {
    type: String,
    default: "list",
  },
  assignmentId: {
    type: String,
    default: "",
  },
  quizTitle: {
    type: String,
    default: "",
  },
});

const isListScreen = computed(() => props.screen === "list");

function openQuizPage(assignment) {
  router.push({
    name: "student-assignment-play",
    params: { assignmentId: assignment.id },
    query: {
      title: assignment.quiz_title,
      from: props.historyView ? "history" : "active",
    },
  });
}

function openAttemptsPage(assignment) {
  router.push({
    name: "student-assignment-attempts",
    params: { assignmentId: assignment.id },
    query: {
      title: assignment.quiz_title,
      from: props.historyView ? "history" : "active",
    },
  });
}
const router = useRouter();
const store = useStore();

const assignments = ref([]);
const page = ref(1);
const hasMore = ref(false);
const loading = ref(false);
const errorMessage = ref("");
const removeMessage = ref("");
const now = ref(Date.now());

const activeAttempt = ref(null);
const answers = ref({});
const result = ref(null);
const review = ref(null);
const reviewLoading = ref(false);
const actionBusy = ref(false);
const confirmationBusy = ref(false);
const saveMessage = ref("");
const needsSave = ref(false);
const serverOffset = ref(0);

const attemptHistory = ref([]);
const historyAssignmentId = ref("");
const historyTitle = ref("");
const historyLoading = ref(false);

const timezoneName = Intl.DateTimeFormat().resolvedOptions().timeZone;
const storageKey = `ict-assignment-attempt-${store.state.auth.currentUser?.id}`;

let clock;
let expiryRequested = false;
let disposed = false;

function timestamp(value) {
  if (typeof value !== "string") return NaN;

  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value)
    ? value
    : `${value}Z`;

  return new Date(normalized).getTime();
}

function formatDate(value) {
  const milliseconds = timestamp(value);

  if (!Number.isFinite(milliseconds)) return "Unavailable";

  return new Date(milliseconds).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

const assignmentCards = computed(() =>
  assignments.value.map((assignment) => {
    let status = "Available";

    if (now.value < timestamp(assignment.available_at)) {
      status = "Upcoming";
    } else if (now.value >= timestamp(assignment.deadline_at)) {
      status = "Closed";
    }

    return {
      ...assignment,
      status,
      statusClass: status.toLowerCase(),
    };
  }),
);

const remainingSeconds = computed(() => {
  if (!activeAttempt.value) return 0;

  return Math.max(
    0,
    Math.ceil(
      (timestamp(activeAttempt.value.expires_at) -
        (now.value + serverOffset.value)) /
        1000,
    ),
  );
});

const timerLabel = computed(() => {
  const seconds = remainingSeconds.value;

  return `${Math.floor(seconds / 60)}:` + String(seconds % 60).padStart(2, "0");
});

const answeredCount = computed(() => Object.keys(answers.value).length);

function errorText(error, fallback) {
  return error instanceof Error ? error.message : fallback;
}

async function api(path, method = "GET", body) {
  const response = await fetch(`http://127.0.0.1:5000${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${store.state.auth.accessToken}`,
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });

  if (response.status === 401) {
    store.commit("auth/CLEAR_AUTH");

    // Allow the login redirect even if a quiz request was active.
    actionBusy.value = false;
    needsSave.value = false;
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
    throw new Error(data.error || "Could not complete the request.");
  }

  return data;
}

function rememberAttempt(attempt) {
  try {
    sessionStorage.setItem(
      storageKey,
      JSON.stringify({
        assignment_id: attempt.assignment_id,
        id: attempt.id,
        expires_at: attempt.expires_at,
      }),
    );
  } catch {
    // The quiz can still run when browser storage is unavailable.
  }
}

function forgetAttempt() {
  try {
    sessionStorage.removeItem(storageKey);
  } catch {
    // Storage cleanup must not hide a submitted result.
  }
}

function updateHistoryResult(savedResult) {
  if (historyAssignmentId.value !== savedResult.assignment_id) return;

  const item = {
    ...savedResult,
    status: "submitted",
    can_review:
      now.value + serverOffset.value >= timestamp(savedResult.review_at),
  };

  const exists = attemptHistory.value.some(
    (attempt) => attempt.id === savedResult.id,
  );

  attemptHistory.value = exists
    ? attemptHistory.value.map((attempt) =>
        attempt.id === savedResult.id ? { ...attempt, ...item } : attempt,
      )
    : [item, ...attemptHistory.value];
}

function showResult(data) {
  review.value = null;
  result.value = data.result;
  assignments.value = assignments.value.map((assignment) =>
    assignment.id === data.result.assignment_id
      ? { ...assignment, can_remove: !props.historyView }
      : assignment,
  );
  activeAttempt.value = null;
  answers.value = {};
  needsSave.value = false;
  saveMessage.value = data.message;
  updateHistoryResult(data.result);
  forgetAttempt();
}

async function loadAssignments(nextPage = page.value) {
  if (loading.value) return;

  loading.value = true;
  errorMessage.value = "";

  try {
    const listView = props.historyView ? "history" : "active";

    const data = await api(
      `/api/quiz-assignments?view=${listView}&page=${nextPage}`,
    );
    if (disposed) return;

    assignments.value = data.assignments;
    page.value = data.pagination.page;
    hasMore.value = data.pagination.has_more;
    now.value = Date.now();
  } catch (error) {
    if (!disposed) {
      errorMessage.value = errorText(error, "Could not load assignments.");
    }
  } finally {
    loading.value = false;
  }
}
async function removeAssignment(assignment) {
  if (
    disposed ||
    props.historyView ||
    assignment.can_remove !== true ||
    loading.value ||
    actionBusy.value ||
    confirmationBusy.value ||
    activeAttempt.value ||
    historyLoading.value ||
    reviewLoading.value
  ) {
    return;
  }

  const token = store.state.auth.accessToken;

  confirmationBusy.value = true;

  try {
    const accepted = await confirmAction({
      title: "Remove this quiz?",
      message:
        `Remove "${assignment.quiz_title}" from this list?\n\n` +
        "It will remain available in Quiz History. Your attempts and results will be kept.",
      confirmText: "Remove quiz",
      cancelText: "Cancel",
      variant: "danger",
    });

    if (
      !accepted ||
      disposed ||
      store.state.auth.accessToken !== token ||
      actionBusy.value ||
      activeAttempt.value ||
      loading.value ||
      historyLoading.value ||
      reviewLoading.value
    ) {
      return;
    }

    actionBusy.value = true;
    errorMessage.value = "";
    removeMessage.value = "";

    await api(`/api/quiz-assignments/${assignment.id}/remove`, "PATCH", {});

    if (disposed || store.state.auth.accessToken !== token) return;

    assignments.value = assignments.value.filter(
      (item) => item.id !== assignment.id,
    );

    if (historyAssignmentId.value === assignment.id) {
      attemptHistory.value = [];
      historyAssignmentId.value = "";
      historyTitle.value = "";
    }

    removeMessage.value =
      "Quiz moved to History. Your attempts and results are saved.";

    const nextPage =
      assignments.value.length === 0 && page.value > 1
        ? page.value - 1
        : page.value;

    await loadAssignments(nextPage);
  } catch (error) {
    if (!disposed && store.state.auth.accessToken === token) {
      errorMessage.value = errorText(error, "Could not remove the quiz.");
    }
  } finally {
    actionBusy.value = false;
    confirmationBusy.value = false;
  }
}

async function startQuiz(assignmentId) {
  if (
    actionBusy.value ||
    activeAttempt.value ||
    historyLoading.value ||
    reviewLoading.value
  ) {
    return;
  }

  actionBusy.value = true;
  errorMessage.value = "";

  try {
    const data = await api(
      `/api/quiz-assignments/${assignmentId}/start`,
      "POST",
      {},
    );
    if (disposed) return;

    activeAttempt.value = data.attempt;
    answers.value = { ...data.attempt.answers };
    result.value = null;
    review.value = null;
    needsSave.value = false;
    expiryRequested = false;
    now.value = Date.now();
    serverOffset.value = timestamp(data.attempt.server_time) - now.value;
    saveMessage.value = data.message;
    rememberAttempt(data.attempt);
  } catch (error) {
    if (!disposed) {
      errorMessage.value = errorText(error, "Could not start quiz.");
    }
  } finally {
    actionBusy.value = false;
  }
}

async function sendAnswers(submit = false) {
  if (actionBusy.value || !activeAttempt.value) return;

  actionBusy.value = true;
  errorMessage.value = "";
  const attempt = activeAttempt.value;

  try {
    const data = await api(
      `/api/quiz-assignments/${attempt.assignment_id}` +
        `/attempts/${attempt.id}/${submit ? "submit" : "answers"}`,
      submit ? "POST" : "PATCH",
      { answers: { ...answers.value } },
    );
    if (disposed) return;

    if (data.result) {
      showResult(data);
    } else {
      needsSave.value = false;
      saveMessage.value = "All selected answers saved.";
      now.value = Date.now();
      serverOffset.value = timestamp(data.attempt.server_time) - now.value;
    }
  } catch (error) {
    if (!disposed) {
      errorMessage.value = errorText(error, "Could not save answers.");
      saveMessage.value = "Request failed. Please retry.";
    }
  } finally {
    actionBusy.value = false;
  }
}

function answerChanged() {
  needsSave.value = true;
  saveMessage.value = "Saving answer...";
  sendAnswers();
}

async function submitQuiz() {
  if (
    disposed ||
    actionBusy.value ||
    confirmationBusy.value ||
    !activeAttempt.value
  ) {
    return;
  }

  const attempt = activeAttempt.value;
  const token = store.state.auth.accessToken;

  confirmationBusy.value = true;

  try {
    if (remainingSeconds.value > 0) {
      const accepted = await confirmAction({
        title: "Submit your quiz?",
        message:
          `You have answered ${answeredCount.value} of ` +
          `${attempt.total_questions} questions.\n\n` +
          "You cannot change your answers after submission.",
        confirmText: "Submit quiz",
        cancelText: "Keep answering",
        variant: "primary",
      });

      if (!accepted) return;
    }

    if (
      disposed ||
      store.state.auth.accessToken !== token ||
      activeAttempt.value?.id !== attempt.id ||
      actionBusy.value
    ) {
      return;
    }

    await sendAnswers(true);
  } finally {
    confirmationBusy.value = false;
  }
}
async function restoreAttempt() {
  let saved;

  try {
    saved = JSON.parse(sessionStorage.getItem(storageKey) || "null");
  } catch {
    forgetAttempt();
    return;
  }

  if (!saved?.assignment_id || !saved?.id || !saved?.expires_at) return;

  if (Date.now() < timestamp(saved.expires_at)) {
    await startQuiz(saved.assignment_id);
    return;
  }

  actionBusy.value = true;

  try {
    const data = await api(
      `/api/quiz-assignments/${saved.assignment_id}` +
        `/attempts/${saved.id}/submit`,
      "POST",
      { answers: {} },
    );

    if (!disposed) showResult(data);
  } catch (error) {
    if (!disposed) {
      errorMessage.value = errorText(error, "Could not restore attempt.");
    }
  } finally {
    actionBusy.value = false;
  }
}

async function loadReview() {
  if (
    !result.value ||
    reviewLoading.value ||
    actionBusy.value ||
    historyLoading.value
  ) {
    return;
  }

  const submittedResult = result.value;
  reviewLoading.value = true;
  errorMessage.value = "";
  review.value = null;

  try {
    const data = await api(
      `/api/quiz-assignments/${submittedResult.assignment_id}` +
        `/attempts/${submittedResult.id}/review`,
    );

    if (disposed || result.value?.id !== submittedResult.id) return;

    review.value = data.review;
  } catch (error) {
    if (!disposed) {
      errorMessage.value = errorText(error, "Could not load quiz review.");
    }
  } finally {
    reviewLoading.value = false;
  }
}

async function loadAttemptHistory(assignment) {
  if (historyLoading.value || actionBusy.value || reviewLoading.value) return;

  historyLoading.value = true;
  errorMessage.value = "";

  try {
    const data = await api(`/api/quiz-assignments/${assignment.id}/attempts`);

    if (disposed) return;

    attemptHistory.value = data.attempts;
    historyTitle.value = assignment.quiz_title;
    historyAssignmentId.value = assignment.id;
  } catch (error) {
    if (!disposed) {
      errorMessage.value = errorText(error, "Could not load attempts.");
    }
  } finally {
    historyLoading.value = false;
  }
}

function openSavedResult(attempt) {
  if (
    attempt.status !== "submitted" ||
    activeAttempt.value ||
    actionBusy.value ||
    reviewLoading.value
  ) {
    return;
  }

  errorMessage.value = "";
  review.value = null;
  result.value = { ...attempt };
  saveMessage.value = "Previously submitted result loaded.";
}

onBeforeRouteLeave(async () => {
  if (!store.getters["auth/isAuthenticated"]) return true;

  if (actionBusy.value || confirmationBusy.value) {
    errorMessage.value = "Wait for the current action to finish.";
    return false;
  }

  if (!needsSave.value) return true;

  const token = store.state.auth.accessToken;

  confirmationBusy.value = true;

  try {
    const accepted = await confirmAction({
      title: "Leave with unsaved answers?",
      message:
        "Some answers have not been saved. Leaving will discard those changes. The quiz timer will continue running.",
      confirmText: "Leave page",
      cancelText: "Stay in quiz",
      variant: "warning",
    });

    if (disposed || store.state.auth.accessToken !== token) return false;

    if (actionBusy.value) {
      errorMessage.value = "Wait for the current request to finish.";
      return false;
    }

    return !needsSave.value || accepted;
  } finally {
    confirmationBusy.value = false;
  }
});
function beforeUnload(event) {
  if (needsSave.value || actionBusy.value) {
    event.preventDefault();
    event.returnValue = "";
  }
}

onMounted(async () => {
  window.addEventListener("beforeunload", beforeUnload);

  clock = window.setInterval(() => {
    now.value = Date.now();

    if (
      activeAttempt.value &&
      remainingSeconds.value === 0 &&
      !actionBusy.value &&
      !expiryRequested
    ) {
      expiryRequested = true;
      sendAnswers(true);
    }
  }, 1000);

  if (isListScreen.value) {
    await loadAssignments(1);
    return;
  }

  if (props.screen === "attempts") {
    await loadAttemptHistory({
      id: props.assignmentId,
      quiz_title: props.quizTitle || "Assigned quiz",
    });
    return;
  }

  if (props.screen === "play") {
    let saved = null;

    try {
      saved = JSON.parse(sessionStorage.getItem(storageKey) || "null");
    } catch {
      // The server can still start or resume the requested quiz.
    }

    if (
      saved?.assignment_id === props.assignmentId &&
      saved?.id &&
      saved?.expires_at
    ) {
      await restoreAttempt();
    } else {
      await startQuiz(props.assignmentId);
    }
  }
});

onUnmounted(() => {
  disposed = true;
  window.clearInterval(clock);
  window.removeEventListener("beforeunload", beforeUnload);
});
</script>

<template>
  <section class="assignments-page" :aria-busy="loading || actionBusy">
    <header v-if="isListScreen" class="heading-row">
      <div>
        <p class="eyebrow">ASSIGNED QUIZZES</p>

        <h1>
          {{
            props.historyView ? "Quiz History" : "Your teacher assigned quizzes"
          }}
        </h1>

        <p class="description">
          {{
            props.historyView
              ? "View quizzes you moved to History."
              : "Start your assigned quizzes and review your attempts."
          }}
        </p>
      </div>

      <div class="header-actions">
        <RouterLink
          class="history-link"
          :to="{
            name: props.historyView
              ? 'student-assignments'
              : 'student-assignment-history',
          }"
        >
          {{ props.historyView ? "Back to Assigned Quizzes" : "Quiz History" }}
        </RouterLink>

        <button type="button" :disabled="loading" @click="loadAssignments()">
          {{ loading ? "Loading..." : "Refresh" }}
        </button>
      </div>
    </header>
    <header v-else class="heading-row">
      <div>
        <p class="eyebrow">
          {{ props.screen === "play" ? "ASSIGNED QUIZ" : "MY ATTEMPTS" }}
        </p>

        <h1>{{ props.quizTitle || "Assigned quiz" }}</h1>
      </div>

      <div class="header-actions">
        <button
          v-if="props.screen === 'attempts' && result"
          type="button"
          :disabled="reviewLoading || actionBusy"
          @click="
            result = null;
            review = null;
          "
        >
          Back to my attempts
        </button>

        <RouterLink
          class="back-link"
          :to="{
            name: props.historyView
              ? 'student-assignment-history'
              : 'student-assignments',
          }"
        >
          {{
            props.historyView
              ? "Back to Quiz History"
              : "Back to Assigned Quizzes"
          }}
        </RouterLink>
      </div>
    </header>

    <p
      v-if="!isListScreen && (actionBusy || historyLoading)"
      class="description"
      role="status"
    >
      {{ props.screen === "play" ? "Loading quiz..." : "Loading attempts..." }}
    </p>

    <p v-if="errorMessage" class="error" role="alert">
      {{ errorMessage }}
    </p>
    <p v-if="removeMessage" class="description" role="status">
      {{ removeMessage }}
    </p>

    <p v-if="isListScreen || props.screen === 'play'" class="notice">
      Answer select korle automatically save hobe. Timer shesh hole shudhu
      server-e saved answers submit hobe. Purono result dekhte My attempts click
      koro.
    </p>

    <section v-if="!isListScreen && result" class="assignment-card">
      <h2>Quiz submitted — Attempt {{ result.attempt_number }}</h2>
      <p class="score">{{ result.score }} / {{ result.total_questions }}</p>

      <p class="description">
        Review available from: {{ formatDate(result.review_at) }}
      </p>

      <p class="description" role="status">{{ saveMessage }}</p>

      <button
        type="button"
        :disabled="reviewLoading || actionBusy || historyLoading"
        @click="loadReview"
      >
        {{ reviewLoading ? "Loading review..." : "Review answers" }}
      </button>

      <p class="description">
        Review time-er age backend answers ar explanations dekhabe na.
      </p>

      <div v-if="review" class="review-list">
        <h3>{{ review.quiz_title }} — Attempt {{ review.attempt_number }}</h3>

        <article
          v-for="question in review.questions"
          :key="question.id"
          class="review-question"
        >
          <div class="heading-row">
            <h3>{{ question.id }}. {{ question.question_text }}</h3>

            <span
              class="badge"
              :class="question.is_correct ? 'available' : 'closed'"
            >
              {{
                question.selected_option === null
                  ? "Unanswered"
                  : question.is_correct
                    ? "Correct"
                    : "Incorrect"
              }}
            </span>
          </div>

          <ul class="review-options">
            <li v-for="option in ['A', 'B', 'C', 'D']" :key="option">
              <strong>{{ option }}.</strong>
              {{ question[`option_${option.toLowerCase()}`] }}

              <span v-if="question.selected_option === option">
                — Your answer
              </span>

              <strong v-if="question.correct_option === option">
                — Correct answer
              </strong>
            </li>
          </ul>

          <p>
            <strong>Your answer:</strong>
            {{ question.selected_option || "Not answered" }}
          </p>

          <p><strong>Correct answer:</strong> {{ question.correct_option }}</p>

          <p class="explanation">
            <strong>Explanation:</strong> {{ question.explanation }}
          </p>
        </article>
      </div>
    </section>

    <section
      v-if="props.screen === 'play' && activeAttempt"
      class="assignment-card"
    >
      <div class="heading-row">
        <h2>{{ activeAttempt.quiz_title }}</h2>
        <strong class="timer">Time left: {{ timerLabel }}</strong>
      </div>

      <p class="description">
        Attempt {{ activeAttempt.attempt_number }} /
        {{ activeAttempt.max_attempts }} · Answered {{ answeredCount }} /
        {{ activeAttempt.total_questions }}
      </p>

      <p class="description" role="status">{{ saveMessage }}</p>

      <p v-if="remainingSeconds === 0" class="error">
        Time expired. Only previously saved answers will count. If submission
        failed, retry below.
      </p>

      <fieldset
        v-for="question in activeAttempt.questions"
        :key="question.id"
        class="question"
        :disabled="actionBusy || remainingSeconds === 0"
      >
        <legend>{{ question.id }}. {{ question.question_text }}</legend>

        <label
          v-for="option in ['A', 'B', 'C', 'D']"
          :key="option"
          class="answer-option"
        >
          <input
            v-model="answers[question.id]"
            type="radio"
            :name="`question-${activeAttempt.id}-${question.id}`"
            :value="option"
            @change="answerChanged"
          />

          <span>
            {{ option }}.
            {{ question[`option_${option.toLowerCase()}`] }}
          </span>
        </label>
      </fieldset>

      <div class="heading-row">
        <button
          v-if="needsSave && remainingSeconds > 0"
          type="button"
          :disabled="actionBusy"
          @click="sendAnswers()"
        >
          Retry saving answers
        </button>

        <button type="button" :disabled="actionBusy" @click="submitQuiz">
          {{ actionBusy ? "Please wait..." : "Submit quiz" }}
        </button>
      </div>
    </section>

    <p
      v-if="
        isListScreen && !loading && !errorMessage && assignments.length === 0
      "
      class="description"
    >
      {{
        props.historyView
          ? "No removed quizzes on this page."
          : "No assigned quizzes on this page."
      }}
    </p>

    <div v-if="isListScreen" class="assignment-list">
      <article
        v-for="assignment in assignmentCards"
        :key="assignment.id"
        class="assignment-card"
      >
        <div class="heading-row">
          <h2>{{ assignment.quiz_title }}</h2>

          <span class="badge" :class="assignment.statusClass">
            {{ assignment.status }}
          </span>
        </div>

        <p class="description">
          {{ assignment.classroom_name }} · {{ assignment.teacher_name }}
        </p>

        <dl>
          <div>
            <dt>Questions</dt>
            <dd>{{ assignment.question_count }}</dd>
          </div>
          <div>
            <dt>Language</dt>
            <dd>{{ assignment.response_language }}</dd>
          </div>
          <div>
            <dt>Time limit</dt>
            <dd>{{ assignment.time_limit_minutes }} minutes</dd>
          </div>
          <div>
            <dt>Allowed attempts</dt>
            <dd>{{ assignment.max_attempts }}</dd>
          </div>
          <div>
            <dt>Available from</dt>
            <dd>{{ formatDate(assignment.available_at) }}</dd>
          </div>
          <div>
            <dt>Deadline</dt>
            <dd>{{ formatDate(assignment.deadline_at) }}</dd>
          </div>
          <div>
            <dt>Review available from</dt>
            <dd>{{ formatDate(assignment.review_at) }}</dd>
          </div>
        </dl>

        <div class="assignment-actions">
          <button
            type="button"
            :disabled="
              loading ||
              actionBusy ||
              historyLoading ||
              reviewLoading ||
              Boolean(activeAttempt) ||
              assignment.status !== 'Available'
            "
            @click="openQuizPage(assignment)"
          >
            Start / resume quiz
          </button>

          <button
            type="button"
            :disabled="historyLoading || actionBusy || reviewLoading"
            @click="openAttemptsPage(assignment)"
          >
            {{
              historyLoading && historyAssignmentId === assignment.id
                ? "Loading attempts..."
                : "My attempts"
            }}
          </button>
          <button
            v-if="!props.historyView"
            type="button"
            class="remove-button remove-assignment-button"
            :disabled="
              assignment.can_remove !== true ||
              loading ||
              actionBusy ||
              historyLoading ||
              reviewLoading ||
              Boolean(activeAttempt)
            "
            :title="
              assignment.can_remove === true
                ? 'Move this quiz to History'
                : 'Submit at least one attempt before removing this quiz'
            "
            @click="removeAssignment(assignment)"
          >
            Remove
          </button>
        </div>
      </article>
    </div>

    <section
      v-if="props.screen === 'attempts' && historyAssignmentId && !result"
      class="assignment-card"
    >
      <h2>My attempts — {{ historyTitle }}</h2>

      <p v-if="historyLoading" class="description" role="status">
        Loading attempts...
      </p>

      <p v-else-if="attemptHistory.length === 0" class="description">
        You have not attempted this assignment yet.
      </p>

      <div v-else class="review-list">
        <article
          v-for="attempt in attemptHistory"
          :key="attempt.id"
          class="review-question"
        >
          <div class="heading-row">
            <h3>Attempt {{ attempt.attempt_number }}</h3>

            <span class="badge upcoming">
              {{
                attempt.status === "submitted"
                  ? "Submitted"
                  : attempt.status === "expired"
                    ? "Expired — not submitted"
                    : "In progress"
              }}
            </span>
          </div>

          <template v-if="attempt.status === 'submitted'">
            <p>
              <strong>Score:</strong>
              {{ attempt.score }} / {{ attempt.total_questions }}
            </p>

            <p class="description">
              Submitted: {{ formatDate(attempt.submitted_at) }}
            </p>

            <p class="description">
              Review available from: {{ formatDate(attempt.review_at) }}
            </p>

            <button
              type="button"
              :disabled="Boolean(activeAttempt) || actionBusy || reviewLoading"
              @click="openSavedResult(attempt)"
            >
              View result
            </button>
          </template>

          <p v-else class="description">
            {{
              attempt.status === "in_progress"
                ? "Use Start / resume quiz on the assignment card to continue."
                : "This attempt expired without a completed submission."
            }}
          </p>
        </article>
      </div>
    </section>

    <nav
      v-if="isListScreen"
      class="heading-row pagination"
      aria-label="Assignment pages"
    >
      <button
        type="button"
        :disabled="loading || page <= 1"
        @click="loadAssignments(page - 1)"
      >
        Previous
      </button>

      <span>Page {{ page }}</span>

      <button
        type="button"
        :disabled="loading || !hasMore"
        @click="loadAssignments(page + 1)"
      >
        Next
      </button>
    </nav>
  </section>
</template>

<style scoped>
.assignments-page {
  display: grid;
  gap: 1.25rem;
  min-width: 0;
  color: var(--text-primary);
}

.heading-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 1rem;
}

h1,
h2,
h3 {
  margin: 0;
  overflow-wrap: anywhere;
}

h1 {
  font-size: clamp(1.6rem, 4vw, 2.3rem);
}

h2 {
  font-size: 1.2rem;
}

h3 {
  font-size: 1rem;
  line-height: 1.6;
}

.eyebrow {
  color: var(--accent-color);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.1em;
}

.description,
dt {
  color: var(--text-secondary);
  line-height: 1.6;
}

.notice,
.assignment-card {
  padding: 1.25rem;
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  background: var(--surface-color);
}

.notice {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.assignment-list {
  display: grid;
  gap: 1rem;
}

.assignment-card {
  min-width: 0;
}

.assignment-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1.25rem;
}

dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin: 1rem 0 0;
}

dt {
  font-size: 0.85rem;
}

dd {
  margin: 0.3rem 0 0;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.badge {
  padding: 0.4rem 0.75rem;
  border-radius: 0.5rem;
  font-size: 0.85rem;
  font-weight: 700;
}

.upcoming {
  color: var(--accent-color);
  background: var(--nav-hover);
}

.available {
  color: #166534;
  background: #dcfce7;
}

.closed {
  color: #991b1b;
  background: #fee2e2;
}

button {
  padding: 0.75rem 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.65rem;
  color: var(--accent-color);
  background: var(--surface-color);
  font: inherit;
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

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

button:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

.error {
  color: #dc2626;
  line-height: 1.6;
}

.timer {
  color: var(--accent-color);
  font-variant-numeric: tabular-nums;
}

.score {
  color: var(--accent-color);
  font-size: 2rem;
  font-weight: 800;
}

.question {
  min-width: 0;
  margin: 1.25rem 0;
  padding: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.75rem;
}

.question legend {
  max-width: 100%;
  padding: 0 0.4rem;
  font-weight: 700;
  overflow-wrap: anywhere;
}

.answer-option {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.65rem 0;
  line-height: 1.6;
  cursor: pointer;
}

.answer-option input {
  margin-top: 0.35rem;
  flex-shrink: 0;
  accent-color: var(--accent-color);
}

.answer-option span {
  overflow-wrap: anywhere;
}

.review-list {
  display: grid;
  gap: 1rem;
  margin-top: 1.25rem;
}

.review-question {
  min-width: 0;
  padding: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.8rem;
  background: var(--page-background);
  overflow-wrap: anywhere;
}

.review-options {
  display: grid;
  gap: 0.75rem;
  padding-left: 1.25rem;
  line-height: 1.6;
}

.explanation {
  white-space: pre-wrap;
  line-height: 1.7;
}

@media (max-width: 540px) {
  dl {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  button {
    transition: none;
  }
}
.history-link {
  padding: 0.75rem 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.65rem;
  color: var(--accent-color);
  background: var(--surface-color);
  font-weight: 700;
  text-decoration: none;
}

.history-link:hover {
  background: var(--nav-hover);
}

.history-link:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}
.remove-button {
  color: #dc2626;
}

.remove-button:hover:not(:disabled) {
  background: #fee2e2;
}
.header-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-left: auto;
}
.header-actions .history-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  padding: 0.75rem 1rem;
  box-sizing: border-box;
  border: 1px solid var(--border-color);
  border-radius: 0.65rem;
  background: var(--page-background);
  color: var(--accent-color);
  font: inherit;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    background-color 0.2s ease;
}

.header-actions .history-link:hover {
  background: var(--nav-hover);
  color: var(--accent-color);
  text-decoration: none;
  transform: translateY(-2px);
}

.header-actions .history-link:active {
  transform: scale(0.98);
}

.header-actions .history-link:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

@media (prefers-reduced-motion: reduce) {
  .header-actions .history-link {
    transition: none;
  }
}
button,
.header-actions .history-link {
  padding: 0.7rem 1rem;
  border: 0;
  border-radius: 8px;
  background: #4f46e5;
  color: #fff;
  font: inherit;
  text-decoration: none;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    background-color 0.2s ease;
}

button:hover:not(:disabled),
.header-actions .history-link:hover {
  background: #4338ca;
  color: #fff;
  text-decoration: none;
  transform: translateY(-2px);
}

button:active:not(:disabled),
.header-actions .history-link:active {
  transform: scale(0.98);
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

button.remove-button {
  background: #dc2626;
  color: #fff;
}

button.remove-button:hover:not(:disabled) {
  background: #b91c1c;
}

@media (prefers-reduced-motion: reduce) {
  button,
  .header-actions .history-link {
    transition: none;
  }
}
.header-actions .back-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  padding: 0.7rem 1rem;
  border: 0;
  border-radius: 8px;
  background: #4f46e5;
  color: #fff;
  font: inherit;
  text-decoration: none;
  transition:
    transform 0.2s ease,
    background-color 0.2s ease;
}

.header-actions .back-link:hover {
  background: #4338ca;
  color: #fff;
  transform: translateY(-2px);
}

.header-actions .back-link:active {
  transform: scale(0.98);
}

.header-actions .back-link:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

@media (prefers-reduced-motion: reduce) {
  .header-actions .back-link {
    transition: none;
  }
}
.assignments-page button,
.assignments-page .history-link {
  border: 1px solid transparent;
  border-radius: 0.65rem;
  padding: 0.75rem 1rem;
  background: #2450db;
  color: #fff;
  font: inherit;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.assignments-page button:hover:not(:disabled),
.assignments-page .history-link:hover {
  background: #1d3fb8;
  color: #fff;
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.assignments-page button:active:not(:disabled),
.assignments-page .history-link:active {
  transform: scale(0.98);
}

.assignments-page button:focus-visible,
.assignments-page .history-link:focus-visible {
  outline: 2px solid #2450db;
  outline-offset: 3px;
}

.assignments-page button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.assignments-page button.remove-assignment-button {
  border-color: #dc2626;
  background: transparent;
  color: #dc2626;
}

.assignments-page button.remove-assignment-button:hover:not(:disabled) {
  background: rgb(220 38 38 / 10%);
  color: #dc2626;
  box-shadow: 0 0.6rem 1rem rgb(220 38 38 / 20%);
  transform: translateY(-2px);
}

.assignments-page button.remove-assignment-button:focus-visible {
  outline-color: #dc2626;
}
</style>
