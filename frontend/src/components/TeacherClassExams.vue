<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useStore } from "vuex";
import { confirmAction } from "../services/confirm_dialog";
const props = defineProps({
  classroomId: {
    type: [String, Number],
    required: true,
  },
});

const router = useRouter();
const store = useStore();
const controller = new AbortController();

const exams = ref([]);
const loading = ref(false);
const saving = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

const title = ref("");
const description = ref("");
const totalMarks = ref("30");
const startsAt = ref("");
const endsAt = ref("");

const selectedExam = ref(null);
const resultRows = ref([]);
const resultPage = ref(1);
const hasMoreResults = ref(false);
const recipientCount = ref(0);
const resultsBusy = ref(false);
const resultError = ref("");
const resultSuccess = ref("");

const timezoneName =
  Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Dhaka";

const busy = computed(() => loading.value || saving.value || resultsBusy.value);

const published = computed(() =>
  Boolean(selectedExam.value?.results_published_at),
);

function rowChanged(row) {
  return row.marks !== row.savedMarks || row.is_absent !== row.savedAbsent;
}

const hasUnsavedChanges = computed(() => resultRows.value.some(rowChanged));

function firstMessage(value) {
  if (typeof value === "string") return value;

  if (value && typeof value === "object") {
    for (const child of Object.values(value)) {
      const message = firstMessage(child);
      if (message) return message;
    }
  }

  return "";
}

async function api(path, method = "GET", body) {
  const token = store.state.auth.accessToken;

  if (!token) {
    await router.replace("/login");
    throw new Error("Please log in again.");
  }

  const response = await fetch(`http://127.0.0.1:5000${path}`, {
    method,
    signal: controller.signal,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
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
    throw new Error(
      firstMessage(data.messages) || data.error || "Exam request failed.",
    );
  }

  return data;
}

async function fetchExams() {
  const collected = [];

  for (let page = 1; page <= 10000; page += 1) {
    const data = await api(`/api/class-exams?page=${page}`);

    collected.push(
      ...data.exams.filter(
        (exam) => String(exam.classroom_id) === String(props.classroomId),
      ),
    );

    if (!data.pagination.has_more) {
      exams.value = collected;
      return;
    }
  }

  throw new Error("Could not load all exams.");
}

async function loadExams() {
  if (busy.value) return;

  loading.value = true;
  errorMessage.value = "";

  try {
    await fetchExams();
  } catch (error) {
    if (!controller.signal.aborted) {
      errorMessage.value =
        error instanceof Error ? error.message : "Could not load exams.";
    }
  } finally {
    loading.value = false;
  }
}

async function scheduleExam() {
  if (busy.value) return;

  errorMessage.value = "";
  successMessage.value = "";

  const start = new Date(startsAt.value);
  const end = new Date(endsAt.value);
  const marks = Number(totalMarks.value);

  if (
    !startsAt.value ||
    !endsAt.value ||
    !Number.isFinite(start.getTime()) ||
    !Number.isFinite(end.getTime()) ||
    end <= start
  ) {
    errorMessage.value = "Enter valid times. End must be after start.";
    return;
  }

  if (!Number.isFinite(marks) || marks <= 0) {
    errorMessage.value = "Total marks must be greater than zero.";
    return;
  }

  saving.value = true;

  try {
    const data = await api(
      `/api/class-exams/classes/${encodeURIComponent(props.classroomId)}`,
      "POST",
      {
        title: title.value.trim(),
        description: description.value.trim(),
        total_marks: totalMarks.value,
        starts_at: start.toISOString(),
        ends_at: end.toISOString(),
        timezone_name: timezoneName,
      },
    );

    successMessage.value = `Exam scheduled. ${data.recipient_count} students notified.`;

    title.value = "";
    description.value = "";
    totalMarks.value = "30";
    startsAt.value = "";
    endsAt.value = "";

    try {
      await fetchExams();
    } catch {
      if (!controller.signal.aborted) {
        errorMessage.value =
          "Exam saved, but the list refresh failed. Click Refresh.";
      }
    }
  } catch (error) {
    if (!controller.signal.aborted) {
      errorMessage.value =
        error instanceof Error ? error.message : "Could not schedule exam.";
    }
  } finally {
    saving.value = false;
  }
}

function updateExamInList(exam) {
  exams.value = exams.value.map((item) =>
    item.id === exam.id ? { ...item, ...exam } : item,
  );
}

async function fetchResultPage(examId, page) {
  const data = await api(
    `/api/class-exams/${encodeURIComponent(examId)}/results?page=${page}`,
  );

  if (
    data.exam.id !== examId ||
    String(data.exam.classroom_id) !== String(props.classroomId)
  ) {
    throw new Error("Unexpected exam response. Reload the page.");
  }

  const rows = data.results.map((row) => {
    const marks = row.obtained_marks === null ? "" : String(row.obtained_marks);

    return {
      student_id: row.student_id,
      student_name: row.student_name,
      marks,
      is_absent: row.is_absent,
      savedMarks: marks,
      savedAbsent: row.is_absent,
    };
  });

  selectedExam.value = data.exam;
  resultRows.value = rows;
  resultPage.value = data.pagination.page;
  hasMoreResults.value = data.pagination.has_more;
  recipientCount.value = data.recipient_count;

  updateExamInList(data.exam);
}

async function openResults(exam) {
  if (busy.value) return;

  if (hasUnsavedChanges.value) {
    resultError.value =
      "Save the current changes or discard them before opening another exam.";
    return;
  }

  resultsBusy.value = true;
  resultError.value = "";
  resultSuccess.value = "";

  try {
    await fetchResultPage(exam.id, 1);
  } catch (error) {
    if (!controller.signal.aborted) {
      resultError.value =
        error instanceof Error ? error.message : "Could not load results.";
    }
  } finally {
    resultsBusy.value = false;
  }
}

async function changeResultPage(page) {
  if (busy.value || !selectedExam.value) return;

  if (hasUnsavedChanges.value) {
    resultError.value = "Save or discard changes before changing the page.";
    return;
  }

  resultsBusy.value = true;
  resultError.value = "";
  resultSuccess.value = "";

  try {
    await fetchResultPage(selectedExam.value.id, page);
  } catch (error) {
    if (!controller.signal.aborted) {
      resultError.value =
        error instanceof Error ? error.message : "Could not load results.";
    }
  } finally {
    resultsBusy.value = false;
  }
}

function setAbsent(row) {
  if (row.is_absent) {
    row.marks = "";
  }
}

function discardChanges() {
  if (busy.value) return;

  for (const row of resultRows.value) {
    row.marks = row.savedMarks;
    row.is_absent = row.savedAbsent;
  }

  resultError.value = "";
  resultSuccess.value = "";
}

function closeResults() {
  if (busy.value) return;

  if (hasUnsavedChanges.value) {
    resultError.value = "Save or discard changes before closing.";
    return;
  }

  selectedExam.value = null;
  resultRows.value = [];
  resultError.value = "";
  resultSuccess.value = "";
}

async function saveDraft() {
  if (busy.value || !selectedExam.value || published.value) return;

  resultError.value = "";
  resultSuccess.value = "";

  const changedRows = resultRows.value.filter(rowChanged);

  if (!changedRows.length) {
    resultError.value = "No changes to save.";
    return;
  }

  const entries = [];

  for (const row of changedRows) {
    const marksText = String(row.marks).trim();

    if (!row.is_absent) {
      const marks = Number(marksText);

      if (
        marksText === "" ||
        !Number.isFinite(marks) ||
        marks < 0 ||
        marks > Number(selectedExam.value.total_marks)
      ) {
        resultError.value =
          `${row.student_name}: enter marks between 0 and ` +
          `${selectedExam.value.total_marks}, or mark absent.`;
        return;
      }
    }

    entries.push({
      student_id: row.student_id,
      obtained_marks: row.is_absent ? null : marksText,
      is_absent: row.is_absent,
    });
  }

  resultsBusy.value = true;

  try {
    const data = await api(
      `/api/class-exams/${encodeURIComponent(selectedExam.value.id)}/results`,
      "PATCH",
      { results: entries },
    );

    // A confirmed save remains saved even if a later refresh fails.
    for (const row of changedRows) {
      row.savedMarks = row.marks;
      row.savedAbsent = row.is_absent;
    }

    resultSuccess.value =
      `Draft saved for ${data.updated_count} students. ` +
      "Students will see their marks after publication.";
  } catch (error) {
    if (!controller.signal.aborted) {
      resultError.value =
        error instanceof Error ? error.message : "Could not save results.";
    }
  } finally {
    resultsBusy.value = false;
  }
}

async function publishResults() {
  if (busy.value || !selectedExam.value || published.value) return;

  resultError.value = "";
  resultSuccess.value = "";

  if (hasUnsavedChanges.value) {
    resultError.value = "Save the draft before publishing.";
    return;
  }

  const examId = selectedExam.value.id;
  const classroomId = props.classroomId;
  const accessToken = store.state.auth.accessToken;

  resultsBusy.value = true;

  try {
    const accepted = await confirmAction({
      title: "Publish exam results?",
      message:
        `Publish results for "${selectedExam.value.title}"?\n\n` +
        "Students will be notified. Published marks cannot be edited.",
      confirmText: "Publish results",
      cancelText: "Cancel",
      variant: "primary",
    });

    if (
      !accepted ||
      controller.signal.aborted ||
      selectedExam.value?.id !== examId ||
      props.classroomId !== classroomId ||
      store.state.auth.accessToken !== accessToken ||
      published.value
    ) {
      return;
    }

    if (hasUnsavedChanges.value) {
      resultError.value = "Save the draft before publishing.";
      return;
    }

    const data = await api(
      `/api/class-exams/${encodeURIComponent(examId)}/publish`,
      "POST",
      {},
    );

    selectedExam.value = data.exam;
    updateExamInList(data.exam);
    resultSuccess.value = "Results published. Students can view their results.";
  } catch (error) {
    if (!controller.signal.aborted) {
      resultError.value =
        error instanceof Error ? error.message : "Could not publish results.";
    }
  } finally {
    resultsBusy.value = false;
  }
}

function formatDate(value) {
  const date = new Date(value);

  if (!Number.isFinite(date.getTime())) return "Date unavailable";

  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

onMounted(loadExams);
onBeforeUnmount(() => controller.abort());
</script>

<template>
  <section class="exam-panel" :aria-busy="busy">
    <header class="panel-heading">
      <div>
        <p class="eyebrow">CLASS EXAMS</p>
        <h2>Schedule an exam</h2>
        <p class="intro">
          Exam class-e nibe. Ekhane schedule ar result publish korbe. Schedule
          korle current class students notification pabe.
        </p>
      </div>

      <button type="button" :disabled="busy" @click="loadExams">
        {{ loading ? "Loading..." : "Refresh exams" }}
      </button>
    </header>

    <form @submit.prevent="scheduleExam">
      <fieldset :disabled="busy" class="form-grid">
        <label class="wide">
          Exam title
          <input
            v-model="title"
            required
            minlength="3"
            maxlength="150"
            placeholder="1st Term ICT"
          />
        </label>

        <label class="wide">
          Instructions (optional)
          <textarea v-model="description" maxlength="2000" rows="3"></textarea>
        </label>

        <label>
          Total marks
          <input
            v-model="totalMarks"
            type="number"
            min="0.01"
            max="9999.99"
            step="0.01"
            required
          />
        </label>

        <p class="timezone-note">Times use {{ timezoneName }}.</p>

        <label>
          Starts at
          <input v-model="startsAt" type="datetime-local" required />
        </label>

        <label>
          Ends at
          <input v-model="endsAt" type="datetime-local" required />
        </label>

        <button type="submit" class="primary wide">
          {{ saving ? "Scheduling..." : "Schedule and notify students" }}
        </button>
      </fieldset>

      <p v-if="errorMessage" class="error" role="alert">
        {{ errorMessage }}
      </p>
      <p v-if="successMessage" class="success" role="status">
        {{ successMessage }}
      </p>
    </form>

    <div class="exam-list">
      <h3>Saved exams</h3>

      <p v-if="loading" class="intro" role="status">Loading exams...</p>
      <p v-else-if="!exams.length && !errorMessage" class="intro">
        No exams scheduled for this class yet.
      </p>

      <article v-for="exam in exams" :key="exam.id" class="exam-card">
        <div class="panel-heading">
          <h3>{{ exam.title }}</h3>
          <span class="exam-status">
            {{
              exam.results_published_at
                ? "Results published"
                : "Results unpublished"
            }}
          </span>
        </div>

        <p class="intro">
          {{ formatDate(exam.starts_at) }} —
          {{ formatDate(exam.ends_at) }}
        </p>
        <p class="intro">Total marks: {{ exam.total_marks }}</p>
        <p v-if="exam.description" class="exam-description">
          {{ exam.description }}
        </p>

        <button
          type="button"
          class="open-results"
          :disabled="busy"
          @click="openResults(exam)"
        >
          {{ exam.results_published_at ? "View results" : "Enter marks" }}
        </button>
      </article>

      <p v-if="resultError && !selectedExam" class="error" role="alert">
        {{ resultError }}
      </p>
    </div>

    <section
      v-if="selectedExam"
      class="results-panel"
      aria-labelledby="exam-results-heading"
    >
      <header class="panel-heading">
        <div>
          <p class="eyebrow">EXAM RESULTS</p>
          <h3 id="exam-results-heading">{{ selectedExam.title }}</h3>
          <p class="intro">
            Total marks: {{ selectedExam.total_marks }} ·
            {{ recipientCount }} students
          </p>
        </div>

        <button type="button" :disabled="busy" @click="closeResults">
          Close
        </button>
      </header>

      <p v-if="published" class="intro">
        Published {{ formatDate(selectedExam.results_published_at) }}. Results
        are read-only.
      </p>
      <p v-else class="intro">
        Enter marks or mark absent. Save each edited page. Publish korar age
        shob student-er entry complete korte hobe.
      </p>

      <form @submit.prevent="saveDraft">
        <fieldset :disabled="busy || published" class="marks-fields">
          <article
            v-for="row in resultRows"
            :key="row.student_id"
            class="marks-row"
          >
            <div class="student-name">
              <strong>{{ row.student_name }}</strong>
              <small>Student #{{ row.student_id }}</small>
            </div>

            <label>
              Obtained marks
              <input
                v-model="row.marks"
                type="number"
                min="0"
                :max="selectedExam.total_marks"
                step="0.01"
                :disabled="row.is_absent"
                placeholder="Not entered"
              />
            </label>

            <label class="checkbox-label">
              <input
                v-model="row.is_absent"
                type="checkbox"
                @change="setAbsent(row)"
              />
              Absent
            </label>
          </article>
        </fieldset>

        <p v-if="resultError" class="error" role="alert">
          {{ resultError }}
        </p>
        <p v-if="resultSuccess" class="success" role="status">
          {{ resultSuccess }}
        </p>

        <div v-if="!published" class="actions">
          <button
            type="submit"
            class="primary"
            :disabled="busy || !hasUnsavedChanges"
          >
            {{ resultsBusy ? "Please wait..." : "Save draft" }}
          </button>

          <button
            type="button"
            :disabled="busy || !hasUnsavedChanges"
            @click="discardChanges"
          >
            Discard changes
          </button>

          <button
            type="button"
            :disabled="busy || hasUnsavedChanges"
            @click="publishResults"
          >
            Publish results
          </button>
        </div>
      </form>

      <div class="pagination">
        <button
          type="button"
          :disabled="busy || hasUnsavedChanges || resultPage === 1"
          @click="changeResultPage(resultPage - 1)"
        >
          Previous
        </button>

        <span>Page {{ resultPage }}</span>

        <button
          type="button"
          :disabled="busy || hasUnsavedChanges || !hasMoreResults"
          @click="changeResultPage(resultPage + 1)"
        >
          Next
        </button>

        <button
          type="button"
          :disabled="busy || hasUnsavedChanges"
          @click="changeResultPage(resultPage)"
        >
          Reload results
        </button>
      </div>

      <p v-if="hasUnsavedChanges" class="intro">
        Unsaved changes on this page. Save or discard before switching pages.
      </p>
    </section>
  </section>
</template>

<style scoped>
.exam-panel {
  min-width: 0;
  padding: 1.5rem;
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  background: var(--surface-color);
  color: var(--text-primary);
}

.panel-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

h2,
h3 {
  margin: 0;
  overflow-wrap: anywhere;
}

h2 {
  font-size: 1.2rem;
}

h3 {
  font-size: 1rem;
}

.eyebrow {
  margin: 0 0 0.5rem;
  color: var(--accent-color);
  font-size: 0.73rem;
  font-weight: 800;
  letter-spacing: 0.1em;
}

.intro,
.timezone-note {
  color: var(--text-secondary);
  line-height: 1.6;
}

.intro {
  margin: 0.65rem 0 0;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  min-width: 0;
  margin: 1.25rem 0 0;
  padding: 0;
  border: 0;
}

.wide {
  grid-column: 1 / -1;
}

label {
  display: grid;
  gap: 0.5rem;
  min-width: 0;
  font-weight: 600;
}

input,
textarea,
button {
  box-sizing: border-box;
  font: inherit;
  border: 1px solid var(--border-color);
  border-radius: 0.65rem;
}

input,
textarea {
  width: 100%;
  min-width: 0;
  padding: 0.8rem;
  background: var(--page-background);
  color: var(--text-primary);
}

textarea {
  resize: vertical;
}

button {
  padding: 0.75rem 1rem;
  background: var(--page-background);
  color: var(--accent-color);
  cursor: pointer;
  font-weight: 700;
}

button:hover:not(:disabled) {
  background: var(--nav-hover);
}

button.primary {
  background: var(--accent-color);
  color: #fff;
}

button.primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

button:disabled,
input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

input:focus-visible,
textarea:focus-visible,
button:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

.exam-list {
  display: grid;
  gap: 1rem;
  margin-top: 1.5rem;
}

.exam-card,
.results-panel {
  min-width: 0;
  padding: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.8rem;
  background: var(--page-background);
}

.results-panel {
  margin-top: 1.5rem;
}

.exam-status {
  color: var(--accent-color);
  font-size: 0.8rem;
  font-weight: 700;
}

.exam-description {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.6;
}

.open-results {
  margin-top: 1rem;
}

.marks-fields {
  display: grid;
  gap: 0.85rem;
  min-width: 0;
  margin: 1rem 0 0;
  padding: 0;
  border: 0;
}

.marks-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(8rem, 0.7fr) auto;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.7rem;
  background: var(--surface-color);
}

.student-name {
  display: grid;
  gap: 0.35rem;
  min-width: 0;
  overflow-wrap: anywhere;
}

.student-name small {
  color: var(--text-secondary);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.checkbox-label input {
  width: 1.15rem;
  height: 1.15rem;
  margin: 0;
  accent-color: var(--accent-color);
}

.actions,
.pagination {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
  margin-top: 1rem;
}

.pagination span {
  color: var(--text-secondary);
}

.error {
  color: #dc2626;
}

.success {
  color: var(--accent-color);
}

@media (max-width: 600px) {
  .exam-panel {
    padding: 1rem;
  }

  .panel-heading {
    flex-direction: column;
  }

  .form-grid,
  .marks-row {
    grid-template-columns: 1fr;
  }
}
</style>
