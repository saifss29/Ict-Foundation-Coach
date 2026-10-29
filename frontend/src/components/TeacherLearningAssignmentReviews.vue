<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useStore } from "vuex";
import { confirmAction } from "../services/confirm_dialog";

const router = useRouter();
const store = useStore();

const assignments = ref([]);
const page = ref(1);
const hasMore = ref(false);

const activeAssignment = ref(null);
const students = ref([]);
const studentPage = ref(1);
const studentsHasMore = ref(false);

const activeStudent = ref(null);
const obtainedMarks = ref("");
const feedback = ref("");
const aiLanguage = ref("banglish");

const aiDraft = computed(
  () => activeStudent.value?.submission?.ai_feedback ?? null,
);

const canGenerateAiFeedback = computed(() => {
  const assignment = activeAssignment.value;
  const submission = activeStudent.value?.submission;

  return (
    assignment?.task_type === "written" &&
    Boolean(assignment.reference_answer?.trim()) &&
    Boolean(submission?.answer_text?.trim()) &&
    submission.status !== "reviewed" &&
    !submission.ai_feedback
  );
});

const aiSections = [
  { key: "strengths", title: "Strengths" },
  { key: "missing_points", title: "Missing points" },
  { key: "improvement_suggestions", title: "How to improve" },
];

const busy = ref("");
const errorMessage = ref("");
const successMessage = ref("");

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
  return value ? new Date(value).toLocaleString() : "Unavailable";
}

function statusLabel(status) {
  return (
    {
      not_submitted: "Not submitted",
      submitted: "Review pending",
      reviewed: "Reviewed",
    }[status] || status
  );
}

async function canDiscardReview() {
  if (
    !activeStudent.value ||
    (!String(obtainedMarks.value).trim() && !feedback.value.trim())
  ) {
    return true;
  }

  const token = store.state.auth.accessToken;
  const student = activeStudent.value;

  busy.value = "confirmation";

  try {
    const accepted = await confirmAction({
      title: "Discard unsaved review?",
      message:
        "Your unsaved marks and feedback will be lost. Do you want to continue?",
      confirmText: "Discard changes",
      cancelText: "Keep editing",
      variant: "warning",
    });

    return (
      accepted &&
      store.state.auth.accessToken === token &&
      activeStudent.value === student
    );
  } finally {
    busy.value = "";
  }
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

async function loadSubmissions(assignmentId, nextPage = 1) {
  if (busy.value) return;
  if (!(await canDiscardReview())) return;

  busy.value = "submissions";
  errorMessage.value = "";
  successMessage.value = "";

  try {
    const data = await api(
      `/api/learning-assignments/${encodeURIComponent(assignmentId)}` +
        `/submissions?page=${nextPage}`,
    );

    activeAssignment.value = data.assignment;
    students.value = data.students;
    studentPage.value = data.pagination.page;
    studentsHasMore.value = data.pagination.has_more;

    activeStudent.value = null;
    obtainedMarks.value = "";
    feedback.value = "";
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "Could not load submissions.";
  } finally {
    busy.value = "";
  }
}

async function selectStudent(student) {
  if (busy.value) return;
  if (!(await canDiscardReview())) return;

  activeStudent.value = student;
  obtainedMarks.value = "";
  feedback.value = "";
  errorMessage.value = "";
  successMessage.value = "";
}
async function generateAiFeedback() {
  if (busy.value || !canGenerateAiFeedback.value) return;

  const assignmentId = activeAssignment.value.id;
  const studentId = activeStudent.value.student_id;
  const submissionId = activeStudent.value.submission.id;
  const token = store.state.auth.accessToken;

  busy.value = "ai-feedback";
  errorMessage.value = "";
  successMessage.value = "";

  try {
    const data = await api(
      `/api/learning-assignments/${encodeURIComponent(assignmentId)}` +
        `/submissions/${submissionId}/ai-feedback`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          response_language: aiLanguage.value,
        }),
      },
    );

    if (
      token !== store.state.auth.accessToken ||
      activeAssignment.value?.id !== assignmentId ||
      activeStudent.value?.submission?.id !== submissionId
    ) {
      return;
    }

    const updatedStudent = {
      ...activeStudent.value,
      submission: {
        ...activeStudent.value.submission,
        ai_feedback: data.ai_feedback,
        ai_feedback_generated_at: data.ai_feedback_generated_at,
      },
    };

    students.value = students.value.map((student) =>
      student.student_id === studentId ? updatedStudent : student,
    );

    activeStudent.value = updatedStudent;
    successMessage.value =
      "AI draft saved. Review the suggestions before saving final feedback.";
  } catch (error) {
    if (token === store.state.auth.accessToken) {
      errorMessage.value =
        error instanceof Error
          ? error.message
          : "Could not generate AI feedback.";
    }
  } finally {
    busy.value = "";
  }
}

async function useAiDraft() {
  if (
    busy.value ||
    !aiDraft.value ||
    activeStudent.value?.submission?.status === "reviewed"
  ) {
    return;
  }

  const lines = [aiDraft.value.summary];

  for (const section of aiSections) {
    const points = aiDraft.value[section.key];

    if (Array.isArray(points) && points.length) {
      lines.push(
        "",
        `${section.title}:`,
        ...points.map((point) => `- ${point}`),
      );
    }
  }

  const draftText = lines.join("\n");

  if (draftText.length > 5000) {
    errorMessage.value =
      "The draft exceeds 5000 characters. Copy and shorten the relevant points.";
    return;
  }

  if (feedback.value.trim()) {
    const student = activeStudent.value;
    const token = store.state.auth.accessToken;

    busy.value = "confirmation";

    try {
      const accepted = await confirmAction({
        title: "Replace your feedback?",
        message:
          "Your unsaved feedback will be replaced with the AI draft. Your marks will stay unchanged.",
        confirmText: "Replace feedback",
        cancelText: "Keep my feedback",
        variant: "warning",
      });

      if (
        !accepted ||
        activeStudent.value !== student ||
        store.state.auth.accessToken !== token
      ) {
        return;
      }
    } finally {
      busy.value = "";
    }
  }

  feedback.value = draftText;
  errorMessage.value = "";
  successMessage.value =
    "Draft copied into Feedback. Edit it and enter your own marks before saving.";
}

async function saveReview() {
  if (
    busy.value ||
    !activeAssignment.value ||
    !activeStudent.value?.submission ||
    activeStudent.value.submission.status === "reviewed"
  ) {
    return;
  }

  const marksText = String(obtainedMarks.value).trim();
  const marks = Number(marksText);
  const total = Number(activeAssignment.value.total_marks);

  errorMessage.value = "";
  successMessage.value = "";

  if (
    !/^\d+(?:\.\d{1,2})?$/.test(marksText) ||
    !Number.isFinite(marks) ||
    marks < 0 ||
    marks > total
  ) {
    errorMessage.value = `Enter marks between 0 and ${total}, with at most two decimal places.`;
    return;
  }

  const student = activeStudent.value;
  const assignment = activeAssignment.value;
  const token = store.state.auth.accessToken;

  busy.value = "review";

  try {
    const accepted = await confirmAction({
      title: "Save marks and feedback?",
      message:
        "Marks and feedback cannot be edited after saving. Please check your review before continuing.",
      confirmText: "Save review",
      cancelText: "Keep editing",
      variant: "primary",
    });

    if (
      !accepted ||
      activeStudent.value !== student ||
      activeAssignment.value !== assignment ||
      store.state.auth.accessToken !== token
    ) {
      return;
    }
    const assignmentId = activeAssignment.value.id;
    const submissionId = activeStudent.value.submission.id;

    const data = await api(
      `/api/learning-assignments/${encodeURIComponent(assignmentId)}` +
        `/submissions/${submissionId}/review`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          obtained_marks: marksText,
          feedback: feedback.value,
        }),
      },
    );

    const reviewedStudent = {
      ...activeStudent.value,
      status: "reviewed",
      submission: {
        ...activeStudent.value.submission,
        ...data.submission,
      },
    };
    students.value = students.value.map((student) =>
      student.student_id === reviewedStudent.student_id
        ? reviewedStudent
        : student,
    );

    activeStudent.value = reviewedStudent;
    obtainedMarks.value = "";
    feedback.value = "";
    successMessage.value = "Review saved. Student notification saved.";
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "Could not save review.";
  } finally {
    busy.value = "";
  }
}

onMounted(() => loadAssignments());
</script>

<template>
  <section class="learning-reviews" :aria-busy="Boolean(busy)">
    <div class="heading">
      <h2>Written and practical assignment reviews</h2>
      <button
        type="button"
        :disabled="Boolean(busy)"
        @click="loadAssignments(page)"
      >
        Refresh assignments
      </button>
    </div>

    <p v-if="errorMessage" class="error" role="alert">
      {{ errorMessage }}
    </p>
    <p v-if="successMessage" class="success" role="status">
      {{ successMessage }}
    </p>
    <p v-if="busy" role="status">Please wait...</p>

    <p v-if="!busy && assignments.length === 0">
      No written or practical assignments yet.
    </p>

    <article
      v-for="assignment in assignments"
      :key="assignment.id"
      class="review-card"
    >
      <h3>{{ assignment.title }}</h3>
      <p>
        {{ assignment.classroom_name }} · {{ assignment.task_type }} ·
        {{ assignment.total_marks }} marks
      </p>
      <p>Deadline: {{ formattedDate(assignment.deadline_at) }}</p>

      <button
        type="button"
        :disabled="Boolean(busy)"
        @click="loadSubmissions(assignment.id)"
      >
        View submissions
      </button>
    </article>

    <nav class="heading" aria-label="Learning assignment pages">
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

    <section v-if="activeAssignment" class="review-card">
      <div class="heading">
        <h3>{{ activeAssignment.title }} — submissions</h3>
        <button
          type="button"
          :disabled="Boolean(busy)"
          @click="loadSubmissions(activeAssignment.id, studentPage)"
        >
          Refresh submissions
        </button>
      </div>

      <p class="preserve-text">{{ activeAssignment.instructions }}</p>
      <details v-if="activeAssignment.reference_answer" class="reference-box">
        <summary>Teacher reference answer</summary>
        <p class="preserve-text">
          {{ activeAssignment.reference_answer }}
        </p>
      </details>

      <p v-if="students.length === 0">No recipients found.</p>

      <article
        v-for="student in students"
        :key="student.student_id"
        class="student-row"
      >
        <div>
          <strong>{{ student.student_name }}</strong>
          <p>{{ statusLabel(student.status) }}</p>
        </div>

        <button
          v-if="student.submission"
          type="button"
          :disabled="Boolean(busy)"
          @click="selectStudent(student)"
        >
          {{ student.status === "reviewed" ? "View review" : "Review answer" }}
        </button>
      </article>

      <nav class="heading" aria-label="Submission pages">
        <button
          type="button"
          :disabled="Boolean(busy) || studentPage <= 1"
          @click="loadSubmissions(activeAssignment.id, studentPage - 1)"
        >
          Previous
        </button>
        <span>Page {{ studentPage }}</span>
        <button
          type="button"
          :disabled="Boolean(busy) || !studentsHasMore"
          @click="loadSubmissions(activeAssignment.id, studentPage + 1)"
        >
          Next
        </button>
      </nav>

      <article v-if="activeStudent?.submission" class="review-card">
        <h3>{{ activeStudent.student_name }} — answer</h3>
        <p>
          Submitted:
          {{ formattedDate(activeStudent.submission.submitted_at) }}
        </p>

        <p v-if="activeStudent.submission.answer_text" class="preserve-text">
          {{ activeStudent.submission.answer_text }}
        </p>

        <pre
          v-if="activeStudent.submission.code_text"
        ><code>{{ activeStudent.submission.code_text }}</code></pre>
        <section
          v-if="activeAssignment.task_type === 'written'"
          class="ai-panel"
          aria-label="AI draft feedback"
        >
          <h4>AI draft feedback</h4>
          <p>
            Teacher-only suggestions. Final marks ar feedback teacher review
            kore save korbe.
          </p>

          <div v-if="canGenerateAiFeedback" class="ai-controls">
            <label>
              Feedback language
              <select v-model="aiLanguage" :disabled="Boolean(busy)">
                <option value="banglish">Banglish</option>
                <option value="english">English</option>
              </select>
            </label>

            <button
              type="button"
              :disabled="Boolean(busy)"
              @click="generateAiFeedback"
            >
              {{
                busy === "ai-feedback"
                  ? "Generating feedback..."
                  : "Generate AI Feedback"
              }}
            </button>
          </div>

          <p
            v-if="
              !aiDraft &&
              activeStudent.submission.status !== 'reviewed' &&
              !activeAssignment.reference_answer?.trim()
            "
          >
            Ei assignment-e reference answer deoa hoyni. Manual marks ar
            feedback diye review korte parba.
          </p>

          <p
            v-else-if="
              !aiDraft &&
              activeStudent.submission.status !== 'reviewed' &&
              !activeStudent.submission.answer_text?.trim()
            "
          >
            AI feedback-er jonno written answer lagbe. Code-only submission
            manually review koro.
          </p>

          <template v-if="aiDraft">
            <p class="preserve-text">{{ aiDraft.summary }}</p>

            <div v-for="section in aiSections" :key="section.key">
              <h5>{{ section.title }}</h5>
              <ul v-if="aiDraft[section.key]?.length">
                <li v-for="(point, index) in aiDraft[section.key]" :key="index">
                  {{ point }}
                </li>
              </ul>
              <p v-else>No points listed.</p>
            </div>

            <p>
              Generated:
              {{
                formattedDate(activeStudent.submission.ai_feedback_generated_at)
              }}
            </p>

            <button
              v-if="activeStudent.submission.status !== 'reviewed'"
              type="button"
              :disabled="Boolean(busy)"
              @click="useAiDraft"
            >
              Use draft in Feedback
            </button>
          </template>
        </section>

        <template v-if="activeStudent.submission.status === 'reviewed'">
          <h4>Saved review</h4>
          <p>
            Marks: {{ activeStudent.submission.obtained_marks }} /
            {{ activeAssignment.total_marks }}
          </p>
          <p class="preserve-text">
            {{
              activeStudent.submission.feedback ||
              "No written feedback provided."
            }}
          </p>
        </template>

        <form v-else @submit.prevent="saveReview">
          <fieldset :disabled="Boolean(busy)">
            <label>
              Obtained marks / {{ activeAssignment.total_marks }}
              <input
                v-model="obtainedMarks"
                type="number"
                min="0"
                :max="activeAssignment.total_marks"
                step="0.01"
                required
              />
            </label>

            <label>
              Feedback
              <textarea
                v-model="feedback"
                rows="5"
                maxlength="5000"
                placeholder="Explain what was good and what to improve."
              ></textarea>
            </label>

            <button type="submit">
              {{ busy === "review" ? "Saving..." : "Save marks and feedback" }}
            </button>
          </fieldset>
        </form>
      </article>
    </section>
  </section>
</template>

<style scoped>
.learning-reviews {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid #64748b55;
}

.heading,
.student-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 1rem;
}

.review-card {
  margin: 1rem 0;
  padding: 1.25rem;
  border: 1px solid #64748b55;
  border-radius: 12px;
}

.student-row {
  padding: 1rem 0;
  border-bottom: 1px solid #64748b33;
}

h2,
h3 {
  margin-top: 0;
}

p {
  line-height: 1.6;
}

.preserve-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

pre {
  padding: 1rem;
  overflow-x: auto;
  border: 1px solid #64748b55;
  border-radius: 8px;
  white-space: pre;
  tab-size: 4;
}

fieldset {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin: 1rem 0;
  font-weight: 600;
}

input,
select,
textarea {
  box-sizing: border-box;
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #64748b88;
  border-radius: 8px;
  background: var(--input-bg, Canvas);
  color: var(--text-color, CanvasText);
  font: inherit;
}

textarea {
  resize: vertical;
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
.ai-panel,
.reference-box {
  margin: 1rem 0;
  padding: 1rem;
  border: 1px solid #64748b55;
  border-radius: 10px;
}

.ai-panel {
  background: #6366f108;
}

.ai-panel h4 {
  margin-top: 0;
}

.ai-panel h5 {
  margin-bottom: 0.5rem;
  font-size: 1rem;
}

.ai-panel li {
  margin-bottom: 0.5rem;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.ai-controls {
  display: flex;
  align-items: end;
  flex-wrap: wrap;
  gap: 1rem;
}

.ai-controls label {
  margin: 0;
}

.reference-box summary {
  cursor: pointer;
  font-weight: 600;
}
</style>
