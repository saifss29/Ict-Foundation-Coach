<script setup>
import { computed, onMounted, ref } from "vue";
import { onBeforeRouteLeave, useRouter } from "vue-router";
import { useStore } from "vuex";
import { confirmAction } from "../services/confirm_dialog";

const props = defineProps({
  assignmentId: {
    type: String,
    default: "",
  },
});
const router = useRouter();
const store = useStore();

const assignments = ref([]);
const page = ref(1);
const hasMore = ref(false);
const busy = ref("");
const errorMessage = ref("");
const successMessage = ref("");

const activeAssignment = ref(null);
const submission = ref(null);
const canSubmit = ref(false);
const answerText = ref("");
const codeText = ref("");

const hasUnsavedAnswer = computed(
  () =>
    !submission.value &&
    Boolean(answerText.value.trim() || codeText.value.trim()),
);

async function canDiscardAnswer() {
  if (busy.value) return false;
  if (!hasUnsavedAnswer.value) return true;

  const assignment = activeAssignment.value;
  const token = store.state.auth.accessToken;

  busy.value = "confirmation";

  try {
    const accepted = await confirmAction({
      title: "Discard your unsent answer?",
      message:
        "Your unsent answer and code will be lost if you leave this task.",
      confirmText: "Discard and continue",
      cancelText: "Keep editing",
      variant: "warning",
    });

    return (
      accepted &&
      activeAssignment.value === assignment &&
      store.state.auth.accessToken === token
    );
  } finally {
    busy.value = "";
  }
}

onBeforeRouteLeave(async () => {
  if (!store.getters["auth/isAuthenticated"]) return true;

  return await canDiscardAnswer();
});
function validationMessage(value) {
  if (typeof value === "string") return value;

  if (value && typeof value === "object") {
    for (const child of Object.values(value)) {
      const message = validationMessage(child);
      if (message) return message;
    }
  }

  return "";
}

async function api(path, options = {}) {
  const response = await fetch(`http://127.0.0.1:5000${path}`, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${store.state.auth.accessToken}`,
    },
  });

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
    throw new Error(
      validationMessage(data.messages) ||
        data.error ||
        "Could not complete the request.",
    );
  }

  return data;
}

function formattedDate(value) {
  if (!value) return "Unavailable";

  return new Date(value).toLocaleString();
}

async function loadAssignments(nextPage = 1) {
  if (busy.value) return;

  busy.value = "list";
  errorMessage.value = "";

  try {
    const data = await api(`/api/learning-assignments?page=${nextPage}`);
    assignments.value = data.assignments;
    page.value = data.pagination.page;
    hasMore.value = data.pagination.has_more;
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "Could not load assignments.";
  } finally {
    busy.value = "";
  }
}

function goToTask(id) {
  if (busy.value) return;

  router.push({
    name: "student-learning-assignment-task",
    params: { assignmentId: String(id) },
  });
}
async function openAssignment(id) {
  if (busy.value) return;
  if (!(await canDiscardAnswer())) return;

  busy.value = "open";
  errorMessage.value = "";
  successMessage.value = "";

  try {
    const data = await api(
      `/api/learning-assignments/${encodeURIComponent(id)}`,
    );

    activeAssignment.value = data.assignment;
    submission.value = data.submission;
    canSubmit.value = data.can_submit;
    answerText.value = "";
    codeText.value = "";
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "Could not open assignment.";
  } finally {
    busy.value = "";
  }
}

async function submitAnswer() {
  if (busy.value || !activeAssignment.value || !canSubmit.value) return;

  errorMessage.value = "";
  successMessage.value = "";

  if (!answerText.value.trim() && !codeText.value.trim()) {
    errorMessage.value = "Write an answer or paste your code.";
    return;
  }

  const assignment = activeAssignment.value;
  const token = store.state.auth.accessToken;

  busy.value = "submit";

  try {
    const accepted = await confirmAction({
      title: "Submit your answer?",
      message:
        "You can submit only once. Your answer and code cannot be edited after submission.",
      confirmText: "Submit answer",
      cancelText: "Keep editing",
      variant: "primary",
    });

    if (
      !accepted ||
      activeAssignment.value !== assignment ||
      store.state.auth.accessToken !== token ||
      !canSubmit.value ||
      submission.value
    ) {
      return;
    }
    const data = await api(
      `/api/learning-assignments/${encodeURIComponent(activeAssignment.value.id)}/submit`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          answer_text: answerText.value,
          code_text: codeText.value,
        }),
      },
    );

    submission.value = data.submission;
    canSubmit.value = false;
    answerText.value = "";
    codeText.value = "";
    successMessage.value =
      "Answer submitted. Teacher review-er jonno wait koro.";
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "Could not submit answer.";
  } finally {
    busy.value = "";
  }
}

onMounted(() => {
  if (props.assignmentId) {
    openAssignment(props.assignmentId);
  } else {
    loadAssignments();
  }
});
</script>

<template>
  <section class="learning-tasks" :aria-busy="Boolean(busy)">
    <div v-if="!props.assignmentId" class="heading">
      <div>
        <h2>Written and practical assignments</h2>
        <p>Teacher-er task dekho, text ba code submit koro.</p>
      </div>

      <button
        type="button"
        :disabled="Boolean(busy)"
        @click="loadAssignments(page)"
      >
        Refresh list
      </button>
      <button
        v-if="props.assignmentId"
        type="button"
        :disabled="Boolean(busy)"
        @click="router.push({ name: 'student-learning-assignments' })"
      >
        Back to Learning Assignments
      </button>
    </div>

    <p v-if="errorMessage" class="error" role="alert">
      {{ errorMessage }}
    </p>
    <p v-if="successMessage" class="success" role="status">
      {{ successMessage }}
    </p>
    <p v-if="busy" role="status">Please wait...</p>

    <p v-if="!props.assignmentId && !busy && assignments.length === 0">
      No written or practical assignments available.
    </p>

    <article
      v-for="assignment in assignments"
      :key="assignment.id"
      class="task-card"
    >
      <h3>{{ assignment.title }}</h3>
      <p>
        {{ assignment.classroom_name }} ·
        {{ assignment.task_type === "practical" ? "Practical" : "Written" }}
        · {{ assignment.total_marks }} marks
      </p>
      <p>Deadline: {{ formattedDate(assignment.deadline_at) }}</p>

      <button
        type="button"
        :disabled="Boolean(busy)"
        @click="goToTask(assignment.id)"
      >
        Open task
      </button>
    </article>

    <nav
      v-if="!props.assignmentId"
      class="heading"
      aria-label="Written and practical assignment pages"
    >
      <button
        type="button"
        :disabled="Boolean(busy) || page <= 1"
        @click="loadAssignments(page - 1)"
      >
        Previous
      </button>
      <span>Page {{ page }}</span>
      <button
        type="button"
        :disabled="Boolean(busy) || !hasMore"
        @click="loadAssignments(page + 1)"
      >
        Next
      </button>
    </nav>
    <button
      v-if="props.assignmentId"
      type="button"
      :disabled="Boolean(busy)"
      @click="router.push({ name: 'student-learning-assignments' })"
    >
      Back to Learning Assignments
    </button>

    <article v-if="activeAssignment" class="task-card">
      <h3>{{ activeAssignment.title }}</h3>
      <p>
        {{ activeAssignment.teacher_name }} ·
        {{ activeAssignment.total_marks }} marks
      </p>

      <p class="instructions">{{ activeAssignment.instructions }}</p>

      <p>Available: {{ formattedDate(activeAssignment.available_at) }}</p>
      <p>Deadline: {{ formattedDate(activeAssignment.deadline_at) }}</p>

      <template v-if="submission">
        <h4>Your submission</h4>

        <p v-if="submission.answer_text" class="instructions">
          {{ submission.answer_text }}
        </p>

        <pre
          v-if="submission.code_text"
        ><code>{{ submission.code_text }}</code></pre>

        <p>Submitted: {{ formattedDate(submission.submitted_at) }}</p>

        <template v-if="submission.status === 'reviewed'">
          <h4>Teacher review</h4>
          <p>
            Marks: {{ submission.obtained_marks }} /
            {{ activeAssignment.total_marks }}
          </p>
          <p class="instructions">
            {{ submission.feedback || "No written feedback provided." }}
          </p>
        </template>

        <p v-else>Submitted. Teacher review pending.</p>

        <button
          type="button"
          :disabled="Boolean(busy)"
          @click="openAssignment(activeAssignment.id)"
        >
          Refresh review
        </button>
      </template>

      <form v-else-if="canSubmit" @submit.prevent="submitAnswer">
        <fieldset :disabled="Boolean(busy)">
          <label>
            Your answer
            <textarea
              v-model="answerText"
              rows="7"
              maxlength="20000"
              placeholder="Write your explanation here."
            ></textarea>
          </label>

          <label>
            Your code (optional)
            <textarea
              v-model="codeText"
              class="code-input"
              rows="10"
              maxlength="50000"
              spellcheck="false"
              placeholder="Paste your code here."
            ></textarea>
          </label>

          <p>
            Text, code, ba duitai dite paro. Code text hisebe submit hobe. Ekbar
            submit korar por edit kora jabe na.
          </p>

          <button type="submit">
            {{ busy === "submit" ? "Submitting..." : "Submit answer" }}
          </button>
        </fieldset>
      </form>

      <template v-else>
        <p>Submission ekhono open hoyni, ba deadline sesh hoyeche.</p>
        <button
          type="button"
          class="refresh-list"
          :disabled="Boolean(busy)"
          @click="openAssignment(activeAssignment.id)"
        >
          Refresh task
        </button>
      </template>
    </article>
  </section>
</template>

<style scoped>
.learning-tasks {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid #64748b55;
}

.heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 1rem;
}

.task-card {
  margin: 1rem 0;
  padding: 1.25rem;
  border: 1px solid #64748b55;
  border-radius: 12px;
}

h2,
h3 {
  margin-top: 0;
}

p {
  line-height: 1.6;
}

.instructions {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

fieldset {
  min-width: 0;
  padding: 0;
  margin: 0;
  border: 0;
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin: 1rem 0;
  font-weight: 600;
}

textarea {
  box-sizing: border-box;
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #64748b88;
  border-radius: 8px;
  background: var(--input-bg, Canvas);
  color: var(--text-color, CanvasText);
  font: inherit;
  resize: vertical;
}

.code-input,
pre {
  font-family: monospace;
  tab-size: 4;
}

pre {
  padding: 1rem;
  overflow-x: auto;
  border: 1px solid #64748b55;
  border-radius: 8px;
  white-space: pre;
}

button {
  padding: 0.7rem 1rem;
  border: 0;
  border-radius: 8px;
  background: #4f46e5;
  color: white;
  font: inherit;
  cursor: pointer;
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.error {
  color: #dc2626;
}

.success {
  color: #16a34a;
}
button {
  transition:
    transform 0.2s ease,
    background-color 0.2s ease;
}

button:hover:not(:disabled) {
  background: var(--accent-hover, #4338ca);
  transform: translateY(-2px);
}

button:active:not(:disabled) {
  transform: scale(0.98);
}

button.refresh-list {
  border: 1px solid var(--border-color);
  border-radius: 0.65rem;
  background: var(--page-background);
  color: var(--accent-color);
  font-weight: 700;
}

button.refresh-list:hover:not(:disabled) {
  background: var(--nav-hover);
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
button.refresh-list {
  padding: 0.7rem 1rem;
  border: 0;
  border-radius: 8px;
  background: #4f46e5;
  color: #fff;
  font: inherit;
}

button.refresh-list:hover:not(:disabled) {
  background: #4338ca;
  transform: translateY(-2px);
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
