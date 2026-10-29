<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useStore } from "vuex";
import { confirmAction } from "../services/confirm_dialog";

const router = useRouter();
const store = useStore();

const classes = ref([]);
const students = ref([]);
const classroomId = ref("");
const selectedStudentIds = ref([]);
const audience = ref("all");
const taskType = ref("written");
const title = ref("");
const instructions = ref("");
const referenceAnswer = ref("");
const referenceLevel = ref("ssc");
const referenceLanguage = ref("banglish");
const totalMarks = ref("10");
const availableAt = ref("");
const deadlineAt = ref("");

const busy = ref("");
const studentsReady = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

function localDateTime(date) {
  const pad = (value) => String(value).padStart(2, "0");

  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-` +
    `${pad(date.getDate())}T${pad(date.getHours())}:` +
    `${pad(date.getMinutes())}`
  );
}

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

async function loadClasses() {
  if (busy.value) return;

  busy.value = "classes";
  errorMessage.value = "";

  try {
    const data = await api("/api/classes");
    classes.value = data.classes;
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "Could not load classes.";
  } finally {
    busy.value = "";
  }
}

async function loadStudents() {
  students.value = [];
  selectedStudentIds.value = [];
  studentsReady.value = false;
  errorMessage.value = "";
  successMessage.value = "";

  if (!classroomId.value || busy.value) return;

  busy.value = "students";

  try {
    const data = await api(`/api/classes/${Number(classroomId.value)}`);
    students.value = data.students;
    studentsReady.value = true;
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "Could not load students.";
  } finally {
    busy.value = "";
  }
}

async function generateReference() {
  if (busy.value || taskType.value !== "written") return;

  errorMessage.value = "";
  successMessage.value = "";

  const cleanTitle = title.value.trim();
  const cleanInstructions = instructions.value.trim();

  if (cleanTitle.length < 3 || cleanTitle.length > 150) {
    errorMessage.value = "Title must be between 3 and 150 characters.";
    return;
  }

  if (!cleanInstructions || cleanInstructions.length > 10000) {
    errorMessage.value =
      "Write the question in Instructions before generating a reference.";
    return;
  }

  const token = store.state.auth.accessToken;
  const originalReference = referenceAnswer.value;
  const level = referenceLevel.value;
  const language = referenceLanguage.value;

  busy.value = "reference";

  try {
    if (originalReference.trim()) {
      const accepted = await confirmAction({
        title: "Replace the reference answer?",
        message:
          "A new AI draft will replace your current reference answer once generation succeeds. Review and edit the draft before creating the assignment.",
        confirmText: "Generate new draft",
        cancelText: "Keep current answer",
        variant: "warning",
      });

      if (!accepted) return;
    }

    if (
      store.state.auth.accessToken !== token ||
      taskType.value !== "written" ||
      title.value.trim() !== cleanTitle ||
      instructions.value.trim() !== cleanInstructions ||
      referenceAnswer.value !== originalReference ||
      referenceLevel.value !== level ||
      referenceLanguage.value !== language
    ) {
      return;
    }

    const data = await api("/api/learning-assignments/reference-answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: cleanTitle,
        instructions: cleanInstructions,
        academic_level: level,
        response_language: language,
      }),
    });

    if (store.state.auth.accessToken !== token) return;

    if (
      taskType.value !== "written" ||
      title.value.trim() !== cleanTitle ||
      instructions.value.trim() !== cleanInstructions ||
      referenceAnswer.value !== originalReference ||
      referenceLevel.value !== level ||
      referenceLanguage.value !== language
    ) {
      errorMessage.value =
        "The question or reference changed. Generate the reference again.";
      return;
    }

    if (
      typeof data.reference_answer !== "string" ||
      !data.reference_answer.trim() ||
      data.reference_answer.length > 10000 ||
      data.is_draft !== true
    ) {
      throw new Error("The server returned an invalid reference draft.");
    }

    referenceAnswer.value = data.reference_answer.trim();
    successMessage.value =
      "Reference draft generated. Review and edit it before creating the assignment.";
  } catch (error) {
    if (store.state.auth.accessToken === token) {
      errorMessage.value =
        error instanceof Error
          ? error.message
          : "Could not generate the reference.";
    }
  } finally {
    busy.value = "";
  }
}

async function createAssignment() {
  if (busy.value) return;

  errorMessage.value = "";
  successMessage.value = "";

  const classId = Number(classroomId.value);
  const cleanTitle = title.value.trim();
  const cleanInstructions = instructions.value.trim();
  const cleanReference =
    taskType.value === "written" ? referenceAnswer.value.trim() : "";
  const start = new Date(availableAt.value);
  const deadline = new Date(deadlineAt.value);
  const marksText = String(totalMarks.value).trim();
  const marks = Number(marksText);

  if (!classes.value.some((item) => item.id === classId)) {
    errorMessage.value = "Select one of your classes.";
    return;
  }

  if (!studentsReady.value || students.value.length === 0) {
    errorMessage.value = "Select a class with enrolled students.";
    return;
  }

  if (cleanTitle.length < 3 || cleanTitle.length > 150) {
    errorMessage.value = "Title must be between 3 and 150 characters.";
    return;
  }

  if (!cleanInstructions || cleanInstructions.length > 10000) {
    errorMessage.value = "Instructions must be between 1 and 10000 characters.";
    return;
  }
  if (cleanReference.length > 10000) {
    errorMessage.value = "Reference answer must not exceed 10000 characters.";
    return;
  }

  if (
    !/^\d+(?:\.\d{1,2})?$/.test(marksText) ||
    !Number.isFinite(marks) ||
    marks <= 0 ||
    marks > 9999.99
  ) {
    errorMessage.value =
      "Enter marks above 0 and up to 9999.99, with at most two decimal places.";
    return;
  }

  if (
    !availableAt.value ||
    !deadlineAt.value ||
    Number.isNaN(start.getTime()) ||
    Number.isNaN(deadline.getTime())
  ) {
    errorMessage.value = "Enter valid availability and deadline times.";
    return;
  }

  if (deadline <= start || deadline.getTime() <= Date.now()) {
    errorMessage.value =
      "Deadline must be after availability and in the future.";
    return;
  }

  const studentIds = [...new Set(selectedStudentIds.value)];

  if (
    audience.value === "selected" &&
    (studentIds.length === 0 || studentIds.length > 500)
  ) {
    errorMessage.value = "Select between 1 and 500 students.";
    return;
  }

  if (
    audience.value === "selected" &&
    !studentIds.every((id) =>
      students.value.some((student) => student.id === id),
    )
  ) {
    errorMessage.value = "Selected students must belong to this class.";
    return;
  }

  busy.value = "create";

  try {
    await api("/api/learning-assignments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        classroom_id: classId,
        title: cleanTitle,
        instructions: cleanInstructions,
        reference_answer: cleanReference,
        task_type: taskType.value,
        audience: audience.value,
        student_ids: audience.value === "selected" ? studentIds : [],
        total_marks: marksText,
        available_at: start.toISOString(),
        deadline_at: deadline.toISOString(),
      }),
    });

    title.value = "";
    instructions.value = "";
    referenceAnswer.value = "";
    selectedStudentIds.value = [];
    successMessage.value = "Assignment created. Student notifications saved.";
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "Could not create assignment.";
  } finally {
    busy.value = "";
  }
}

onMounted(() => {
  const start = new Date();
  availableAt.value = localDateTime(start);
  deadlineAt.value = localDateTime(
    new Date(start.getTime() + 24 * 60 * 60 * 1000),
  );

  loadClasses();
});
</script>

<template>
  <section class="learning-panel">
    <h2>Create a written or practical assignment</h2>
    <p class="description">
      Instructions likhe class-e assign koro. Student text ba code submit korbe;
      teacher marks ar feedback debe.
    </p>

    <p v-if="errorMessage" class="error" role="alert">
      {{ errorMessage }}
    </p>
    <p v-if="successMessage" class="success" role="status">
      {{ successMessage }}
    </p>

    <p v-if="busy === 'classes'" role="status">Loading classes...</p>

    <button v-if="!classes.length && !busy" type="button" @click="loadClasses">
      Reload classes
    </button>

    <form @submit.prevent="createAssignment">
      <fieldset :disabled="Boolean(busy)">
        <div class="form-grid">
          <label>
            Task type
            <select v-model="taskType">
              <option value="written">Written answer</option>
              <option value="practical">Practical task</option>
            </select>
          </label>

          <label>
            Class
            <select v-model="classroomId" required @change="loadStudents">
              <option value="" disabled>Select a class</option>
              <option
                v-for="classroom in classes"
                :key="classroom.id"
                :value="classroom.id"
              >
                {{ classroom.name }}
              </option>
            </select>
          </label>

          <label class="wide">
            Title
            <input
              v-model="title"
              required
              minlength="3"
              maxlength="150"
              placeholder="Example: Create a simple HTML page"
            />
          </label>

          <label class="wide">
            Instructions
            <textarea
              v-model="instructions"
              required
              maxlength="10000"
              rows="7"
              placeholder="Explain the task and what the student should submit."
            ></textarea>
          </label>
          <div v-if="taskType === 'written'" class="wide reference-section">
            <label>
              Reference answer / assessment points (optional)
              <textarea
                v-model="referenceAnswer"
                maxlength="10000"
                rows="6"
                aria-describedby="reference-answer-help"
                placeholder="Write assessment points or generate a draft with Maira."
              ></textarea>
            </label>

            <div class="reference-controls">
              <label>
                Textbook level
                <select v-model="referenceLevel">
                  <option value="ssc">SSC ICT</option>
                  <option value="hsc">HSC ICT</option>
                </select>
              </label>

              <label>
                Reference language
                <select v-model="referenceLanguage">
                  <option value="banglish">Banglish</option>
                  <option value="english">English</option>
                </select>
              </label>
            </div>

            <button type="button" @click="generateReference">
              {{
                busy === "reference"
                  ? "Generating reference..."
                  : "Generate reference with Maira"
              }}
            </button>

            <p id="reference-answer-help" class="description">
              Maira selected textbook dataset theke draft generate korbe. Assign
              korar age answer-ta review ar edit koro. Reference student dekhbe
              na; AI draft feedback-er jonno use hobe. Blank rakhle manual
              review korte parba.
            </p>
          </div>

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

          <label>
            Audience
            <select v-model="audience">
              <option value="all">All enrolled students</option>
              <option value="selected">Selected students</option>
            </select>
          </label>

          <label>
            Available from
            <input v-model="availableAt" type="datetime-local" required />
          </label>

          <label>
            Deadline
            <input v-model="deadlineAt" type="datetime-local" required />
          </label>

          <p class="description wide">
            Times use your device's local timezone. Students can submit once
            before the deadline. Code is submitted as text.
          </p>

          <p v-if="studentsReady" class="description wide">
            {{ students.length }} enrolled students.
          </p>

          <div
            v-if="audience === 'selected' && studentsReady"
            class="student-list wide"
          >
            <label
              v-for="student in students"
              :key="student.id"
              class="student-row"
            >
              <input
                v-model="selectedStudentIds"
                type="checkbox"
                :value="student.id"
              />
              <span>{{ student.name }}</span>
            </label>
          </div>
        </div>

        <button
          type="submit"
          :disabled="!studentsReady || students.length === 0"
        >
          {{ busy === "create" ? "Creating..." : "Create and assign" }}
        </button>
      </fieldset>
    </form>
  </section>
</template>

<style scoped>
.learning-panel {
  padding: 1.5rem;
  border: 1px solid #64748b55;
  border-radius: 16px;
  background: var(--card-bg, transparent);
  color: inherit;
}

h2 {
  margin: 0 0 0.75rem;
}

.description {
  opacity: 0.8;
  line-height: 1.6;
}

fieldset {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
  margin: 1.25rem 0;
}

label {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  font-weight: 600;
}

.wide {
  grid-column: 1 / -1;
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

input:focus,
select:focus,
textarea:focus {
  outline: 2px solid #6366f1;
  outline-offset: 2px;
}

.student-list {
  max-height: 240px;
  overflow-y: auto;
  padding: 0.75rem;
  border: 1px solid #64748b55;
  border-radius: 8px;
}

.student-row {
  flex-direction: row;
  align-items: center;
  padding: 0.5rem;
}

.student-row input {
  width: auto;
}

button {
  padding: 0.75rem 1.1rem;
  border: 0;
  border-radius: 8px;
  background: #4f46e5;
  color: white;
  font: inherit;
  cursor: pointer;
  transition: background 0.2s ease;
}

button:hover:not(:disabled) {
  background: #4338ca;
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.error,
.success {
  padding: 0.85rem;
  border-radius: 8px;
  line-height: 1.5;
}

.error {
  color: #dc2626;
  background: #ef444415;
}

.success {
  color: #16a34a;
  background: #22c55e15;
}
.reference-section {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.reference-controls {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
}

.reference-section > button {
  align-self: flex-start;
}

@media (max-width: 640px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .learning-panel {
    padding: 1rem;
  }
}
</style>
