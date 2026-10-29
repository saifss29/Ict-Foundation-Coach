<script setup>
import { computed, onMounted, ref } from "vue";
import { onBeforeRouteLeave, useRoute, useRouter } from "vue-router";
import { useStore } from "vuex";
import { confirmAction } from "../services/confirm_dialog";

const props = defineProps({
  reviewQuizId: { type: String, default: "" },
});

const isReviewPage = computed(() => Boolean(props.reviewQuizId));
const route = useRoute();
const router = useRouter();
const store = useStore();

const topics = ref([]);
const quizzes = ref([]);
const selectedTopicId = ref("");
const title = ref("");
const questionCount = ref(5);
const language = ref("banglish");
const selectedLearningMode = ref("personal_growth");

function learningModeLabel(mode) {
  const labels = {
    personal_growth: "Personal growth",
    exam_preparation: "Exam preparation",
  };

  return labels[mode] || "Mode unavailable";
}

const activeQuiz = ref(null);
const editTitle = ref("");
const editQuestions = ref([]);
const originalEdit = ref("");

const page = ref(1);
const hasMore = ref(false);
const busy = ref("");
const errorMessage = ref("");
const successMessage = ref("");
const ready = ref(false);

const selectedSubject = ref("ict");
const selectedAcademicLevel = ref("hsc");

const subjectOptions = [{ value: "ict", label: "ICT" }];

const academicLevelOptions = [
  { value: "ssc", label: "SSC" },
  { value: "hsc", label: "HSC" },
];

const sscPracticeSlugs = new Set(
  [
    "ict-in-everyday-life",
    "e-learning",
    "e-governance-and-e-services",
    "e-commerce",
    "preventive-and-corrective-maintenance",
    "installing-and-uninstalling-software",
    "public-and-confidential-information",
    "cyber-risks-and-responsible-access",
    "internet-and-digital-content",
    "e-books-and-learning-resources",
    "word-processing",
    "save-and-save-as",
    "document-formatting-and-tables",
    "spreadsheets-and-cell-references",
    "multimedia-and-interactivity",
    "planning-a-presentation",
    "problem-solving-before-coding",
    "python-output-and-variables",
    "python-input-and-arithmetic",
    "python-decisions",
    "python-repetition-and-range",
    "bits-and-bytes-hsc-bridge",
    "binary-place-value-hsc-bridge",
    "first-html-page-optional-practice",
    "files-before-web-development",
  ].map((slug) => `ssc-ict-${slug}`),
);

const supportedTopics = computed(() =>
  topics.value.filter((topic) => {
    if (
      topic.subject !== selectedSubject.value ||
      topic.subject !== "ict" ||
      topic.academic_level !== selectedAcademicLevel.value
    ) {
      return false;
    }

    if (topic.academic_level === "ssc") {
      return sscPracticeSlugs.has(topic.slug);
    }

    return topic.academic_level === "hsc" && topic.slug === "number-systems";
  }),
);

function selectFirstSupportedTopic() {
  const currentTopicId = Number(selectedTopicId.value);

  if (!supportedTopics.value.some((topic) => topic.id === currentTopicId)) {
    selectedTopicId.value = supportedTopics.value[0]?.id ?? "";
  }
}

const isDraft = computed(() => activeQuiz.value?.status === "draft");

const hasUnsavedChanges = computed(
  () =>
    isDraft.value &&
    JSON.stringify({
      title: editTitle.value,
      questions: editQuestions.value,
    }) !== originalEdit.value,
);

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
    throw new Error("Your session has expired. Please log in again.");
  }

  let data;

  try {
    data = await response.json();
  } catch {
    throw new Error("Could not read the server response. Please try again.");
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
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

async function runAction(name, action) {
  if (busy.value) return;

  busy.value = name;
  errorMessage.value = "";
  successMessage.value = "";

  try {
    await action();
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "Something went wrong.";
  } finally {
    busy.value = "";
  }
}

async function canLeaveEditor() {
  if (!hasUnsavedChanges.value) return true;
  if (busy.value) return false;

  const quiz = activeQuiz.value;
  const token = store.state.auth.accessToken;

  busy.value = "confirmation";

  try {
    const accepted = await confirmAction({
      title: "Discard unsaved quiz edits?",
      message:
        "Your unsaved changes to the quiz title and questions will be lost.",
      confirmText: "Discard changes",
      cancelText: "Keep editing",
      variant: "warning",
    });

    return (
      accepted &&
      activeQuiz.value === quiz &&
      store.state.auth.accessToken === token
    );
  } finally {
    busy.value = "";
  }
}

function setActiveQuiz(quiz) {
  activeQuiz.value = quiz;
  editTitle.value = quiz.title;
  editQuestions.value = JSON.parse(JSON.stringify(quiz.questions));

  originalEdit.value = JSON.stringify({
    title: editTitle.value,
    questions: editQuestions.value,
  });
}

function updateSummary(quiz) {
  const { questions, ...summary } = quiz;

  quizzes.value = quizzes.value.map((item) =>
    item.id === quiz.id ? summary : item,
  );
}

async function fetchQuizList(nextPage) {
  const data = await api(`/api/teacher-quizzes?page=${nextPage}`);

  quizzes.value = data.quizzes;
  page.value = data.pagination.page;
  hasMore.value = data.pagination.has_more;
}

async function initialize() {
  await runAction("load", async () => {
    ready.value = false;

    if (isReviewPage.value) {
      const data = await api(
        `/api/teacher-quizzes/${encodeURIComponent(props.reviewQuizId)}`,
      );

      setActiveQuiz(data.quiz);
      ready.value = true;
      return;
    }

    const topicData = await api("/api/topics");
    topics.value = topicData.topics;

    selectFirstSupportedTopic();

    await fetchQuizList(1);

    if (route.query.assigned === "1") {
      successMessage.value =
        "Quiz assigned successfully. Student notifications saved.";
    }

    ready.value = true;
  });
}

async function generateQuiz() {
  if (busy.value) return;
  if (!(await canLeaveEditor())) return;

  await runAction("generate", async () => {
    const count = Number(questionCount.value);
    const quizTitle = title.value.trim();

    if (quizTitle.length < 3 || quizTitle.length > 150) {
      throw new Error("Title must be between 3 and 150 characters.");
    }

    if (!Number.isInteger(count) || count < 1 || count > 20) {
      throw new Error("Choose between 1 and 20 questions.");
    }

    const topicId = Number(selectedTopicId.value);

    if (!supportedTopics.value.some((topic) => topic.id === topicId)) {
      throw new Error("Select a supported topic.");
    }

    const data = await api(
      "/api/teacher-quizzes",
      jsonOptions("POST", {
        topic_id: topicId,
        title: quizTitle,
        question_count: count,
        response_language: language.value,
        learning_mode: selectedLearningMode.value,
      }),
    );

    await router.push({
      name: "teacher-quiz-review",
      params: { quizId: data.quiz.id },
    });
  });
}

async function openQuiz(id) {
  if (busy.value) return;

  await router.push({
    name: "teacher-quiz-review",
    params: { quizId: id },
  });
}

async function backToGenerate() {
  if (busy.value) return;

  await router.push({ name: "teacher-quizzes" });
}

onBeforeRouteLeave(async () => {
  if (!store.getters["auth/isAuthenticated"]) return true;

  return await canLeaveEditor();
});

async function saveDraft() {
  await runAction("save", async () => {
    if (!isDraft.value) return;

    const data = await api(
      `/api/teacher-quizzes/${activeQuiz.value.id}`,
      jsonOptions("PUT", {
        title: editTitle.value,
        questions: editQuestions.value,
      }),
    );

    setActiveQuiz(data.quiz);
    updateSummary(data.quiz);
    successMessage.value = "Draft changes saved.";
  });
}

async function publishQuiz() {
  if (!isDraft.value || busy.value || hasUnsavedChanges.value) return;

  const quiz = activeQuiz.value;
  const token = store.state.auth.accessToken;

  await runAction("publish", async () => {
    const accepted = await confirmAction({
      title: "Publish this quiz?",
      message:
        "The quiz questions cannot be edited after publication. Please check the saved draft before continuing.",
      confirmText: "Publish quiz",
      cancelText: "Cancel",
      variant: "primary",
    });

    if (
      !accepted ||
      activeQuiz.value !== quiz ||
      store.state.auth.accessToken !== token ||
      !isDraft.value ||
      hasUnsavedChanges.value
    ) {
      return;
    }

    const data = await api(
      `/api/teacher-quizzes/${quiz.id}/publish`,
      jsonOptions("POST", {}),
    );

    setActiveQuiz(data.quiz);
    updateSummary(data.quiz);
    successMessage.value = "Quiz published successfully.";
  });
}

async function changePage(nextPage) {
  await runAction("list", () => fetchQuizList(nextPage));
}
async function removeQuiz(quiz) {
  if (busy.value) return;

  const quizId = quiz.id;
  const token = store.state.auth.accessToken;

  await runAction("remove", async () => {
    const accepted = await confirmAction({
      title: "Remove this quiz?",
      message:
        `Remove "${quiz.title}" from Your quizzes?\n\n` +
        "It will remain available in Quiz History.",
      confirmText: "Remove quiz",
      cancelText: "Cancel",
      variant: "danger",
    });

    if (!accepted || store.state.auth.accessToken !== token) return;

    await api(
      `/api/teacher-quizzes/${encodeURIComponent(quizId)}/remove`,
      jsonOptions("PATCH", {}),
    );

    quizzes.value = quizzes.value.filter((item) => item.id !== quizId);
    successMessage.value = "Quiz moved to history.";

    try {
      const nextPage =
        quizzes.value.length === 0 && page.value > 1
          ? page.value - 1
          : page.value;

      await fetchQuizList(nextPage);
    } catch (error) {
      errorMessage.value =
        error instanceof Error
          ? `Quiz moved to history, but the list could not refresh: ${error.message}`
          : "Quiz moved to history. Refresh the list to continue.";
    }
  });
}

const assignmentOpen = ref(false);
const assignmentClasses = ref([]);
const assignmentStudents = ref([]);
const assignmentClassId = ref("");
const assignmentAudience = ref("all");
const selectedStudentIds = ref([]);
const studentsReady = ref(false);
const assignmentSaved = ref(false);

const availableAt = ref("");
const deadlineAt = ref("");
const reviewAt = ref("");
const timeLimitMinutes = ref(30);
const maxAttempts = ref(1);

function localDateTime(date) {
  const pad = (value) => String(value).padStart(2, "0");

  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-` +
    `${pad(date.getDate())}T${pad(date.getHours())}:` +
    `${pad(date.getMinutes())}`
  );
}

async function openAssignmentForm() {
  if (activeQuiz.value?.status !== "published") return;

  await runAction("assignment-load", async () => {
    const data = await api("/api/classes");

    assignmentClasses.value = data.classes;
    assignmentClassId.value = "";
    assignmentStudents.value = [];
    selectedStudentIds.value = [];
    assignmentAudience.value = "all";
    studentsReady.value = false;
    assignmentSaved.value = false;
    timeLimitMinutes.value = 30;
    maxAttempts.value = 1;

    const start = new Date(Date.now() + 5 * 60 * 1000);
    const deadline = new Date(start.getTime() + 24 * 60 * 60 * 1000);

    availableAt.value = localDateTime(start);
    deadlineAt.value = localDateTime(deadline);
    reviewAt.value = localDateTime(deadline);
    assignmentOpen.value = true;
  });
}

async function loadAssignmentStudents() {
  assignmentStudents.value = [];
  selectedStudentIds.value = [];
  studentsReady.value = false;

  const classroomId = Number(assignmentClassId.value);
  if (!Number.isInteger(classroomId) || classroomId < 1) return;

  await runAction("assignment-students", async () => {
    const data = await api(`/api/classes/${classroomId}`);

    assignmentStudents.value = data.students;
    studentsReady.value = true;
  });
}

async function assignQuiz() {
  if (assignmentSaved.value) return;

  await runAction("assign", async () => {
    if (activeQuiz.value?.status !== "published") {
      throw new Error("Select a published quiz.");
    }

    const classroomId = Number(assignmentClassId.value);

    if (
      !assignmentClasses.value.some((classroom) => classroom.id === classroomId)
    ) {
      throw new Error("Select one of your classes.");
    }

    if (!studentsReady.value) {
      throw new Error("Load the class student list first.");
    }

    if (assignmentStudents.value.length === 0) {
      throw new Error("This class has no enrolled students.");
    }

    if (!["all", "selected"].includes(assignmentAudience.value)) {
      throw new Error("Choose all students or selected students.");
    }

    const studentIds = [...new Set(selectedStudentIds.value)];

    if (assignmentAudience.value === "selected") {
      if (studentIds.length === 0) {
        throw new Error("Select at least one student.");
      }

      if (studentIds.length > 500) {
        throw new Error("Select no more than 500 students.");
      }

      if (
        !studentIds.every((id) =>
          assignmentStudents.value.some((student) => student.id === id),
        )
      ) {
        throw new Error("Selected students must belong to this class.");
      }
    }

    const start = new Date(availableAt.value);
    const deadline = new Date(deadlineAt.value);
    const review = new Date(reviewAt.value);

    if (
      !availableAt.value ||
      !deadlineAt.value ||
      !reviewAt.value ||
      [start, deadline, review].some((date) => Number.isNaN(date.getTime()))
    ) {
      throw new Error("Enter valid availability, deadline and review times.");
    }

    if (deadline <= start) {
      throw new Error("Deadline must be after the available time.");
    }

    if (deadline.getTime() <= Date.now()) {
      throw new Error("Deadline must be in the future.");
    }

    if (review < deadline) {
      throw new Error("Review time must be at or after the deadline.");
    }

    const minutes = Number(timeLimitMinutes.value);
    const attempts = Number(maxAttempts.value);

    if (!Number.isInteger(minutes) || minutes < 1 || minutes > 180) {
      throw new Error("Time limit must be between 1 and 180 minutes.");
    }

    if (!Number.isInteger(attempts) || attempts < 1 || attempts > 5) {
      throw new Error("Allowed attempts must be between 1 and 5.");
    }

    const data = await api(
      "/api/quiz-assignments",
      jsonOptions("POST", {
        quiz_id: activeQuiz.value.id,
        classroom_id: classroomId,
        audience: assignmentAudience.value,
        student_ids: assignmentAudience.value === "selected" ? studentIds : [],
        available_at: start.toISOString(),
        deadline_at: deadline.toISOString(),
        review_at: review.toISOString(),
        time_limit_minutes: minutes,
        max_attempts: attempts,
      }),
    );

    assignmentSaved.value = true;
    successMessage.value =
      `Quiz assigned to ${data.assignment.recipient_count} students. ` +
      "Notifications saved.";

    await router.push({
      name: "teacher-quizzes",
      query: { assigned: "1" },
    });
  });
}

onMounted(async () => {
  await initialize();
});
</script>

<template>
  <section class="quiz-page" :aria-busy="Boolean(busy)">
    <header>
      <p class="eyebrow">TEACHER QUIZZES</p>
      <h1>
        {{ isReviewPage ? "Review and assign quiz" : "Generate quizzes" }}
      </h1>

      <p class="description">
        {{
          isReviewPage
            ? "Questions check koro, draft edit/save koro, tarpor publish ar assign koro."
            : "Topic select kore draft generate koro. Review alada page-e khulbe."
        }}
      </p>

      <button
        v-if="isReviewPage"
        type="button"
        :disabled="Boolean(busy)"
        @click="backToGenerate"
      >
        Back to Generate quizzes
      </button>
      <div v-if="!isReviewPage" class="quiz-header-actions">
        <RouterLink
          :to="{ name: 'teacher-assigned-quizzes' }"
          class="assigned-quizzes-link"
        >
          Assigned Quizzes
        </RouterLink>

        <RouterLink
          :to="{ name: 'teacher-quiz-history' }"
          class="assigned-quizzes-link"
        >
          Quiz History
        </RouterLink>
      </div>
    </header>

    <p v-if="errorMessage" class="error" role="alert">
      {{ errorMessage }}
    </p>

    <p v-if="successMessage" class="success" role="status">
      {{ successMessage }}
    </p>

    <p v-if="busy" class="description" role="status">
      {{
        busy === "generate"
          ? "Generating your quiz. This may take a little time..."
          : "Please wait..."
      }}
    </p>

    <button
      v-if="!ready"
      type="button"
      :disabled="Boolean(busy)"
      @click="initialize"
    >
      Retry loading
    </button>

    <template v-if="ready">
      <section v-if="!isReviewPage" class="panel">
        <h2>Generate a draft</h2>

        <p class="description">
          Select a subject and level to see available quiz topics.
        </p>

        <p
          v-if="supportedTopics.length === 0"
          class="description"
          role="status"
        >
          Quiz generation is not available for this subject and level yet.
        </p>

        <form @submit.prevent="generateQuiz">
          <fieldset :disabled="Boolean(busy)" class="form-grid">
            <label>
              Subject
              <select
                v-model="selectedSubject"
                @change="selectFirstSupportedTopic"
              >
                <option
                  v-for="subject in subjectOptions"
                  :key="subject.value"
                  :value="subject.value"
                >
                  {{ subject.label }}
                </option>
              </select>
            </label>

            <label>
              Academic level
              <select
                v-model="selectedAcademicLevel"
                @change="selectFirstSupportedTopic"
              >
                <option
                  v-for="level in academicLevelOptions"
                  :key="level.value"
                  :value="level.value"
                >
                  {{ level.label }}
                </option>
              </select>
            </label>

            <label class="wide">
              Quiz title
              <input
                v-model="title"
                required
                minlength="3"
                maxlength="150"
                placeholder="ICT Practice Quiz"
              />
            </label>

            <label>
              Topic
              <select v-model="selectedTopicId" required>
                <option disabled value="">Select a topic</option>

                <option
                  v-for="topic in supportedTopics"
                  :key="topic.id"
                  :value="topic.id"
                >
                  {{ topic.title }}
                </option>
              </select>
            </label>

            <label>
              Questions
              <input
                v-model.number="questionCount"
                type="number"
                min="1"
                max="20"
                step="1"
                required
              />
            </label>

            <label>
              Language
              <select v-model="language">
                <option value="banglish">Banglish</option>
                <option value="english">English</option>
              </select>
            </label>

            <label>
              Learning mode
              <select v-model="selectedLearningMode">
                <option value="personal_growth">Personal growth</option>
                <option value="exam_preparation">Exam preparation</option>
              </select>
            </label>

            <p class="description wide">
              Supports selected SSC ICT lessons and HSC Number Systems. Review
              every generated question before publishing. Full board-format
              practice is not available yet.
            </p>

            <button
              class="primary wide"
              type="submit"
              :disabled="supportedTopics.length === 0"
            >
              {{ busy === "generate" ? "Generating..." : "Generate quiz" }}
            </button>
          </fieldset>
        </form>
      </section>

      <section v-if="!isReviewPage" class="panel">
        <div class="heading-row">
          <h2>Your quizzes</h2>

          <button
            type="button"
            :disabled="Boolean(busy)"
            @click="changePage(page)"
          >
            Refresh
          </button>
        </div>

        <p v-if="quizzes.length === 0" class="description">
          No quizzes on this page.
        </p>

        <div class="quiz-list">
          <article v-for="quiz in quizzes" :key="quiz.id" class="quiz-list-row">
            <button
              type="button"
              class="quiz-item"
              :class="{ selected: activeQuiz?.id === quiz.id }"
              :disabled="Boolean(busy)"
              @click="openQuiz(quiz.id)"
            >
              <strong>{{ quiz.title }}</strong>
              <span>
                {{ quiz.question_count }} questions ·
                {{ quiz.response_language }} · {{ quiz.status }} ·
                {{ learningModeLabel(quiz.learning_mode) }}
              </span>
            </button>

            <button
              type="button"
              class="remove-quiz"
              :disabled="Boolean(busy)"
              :aria-label="`Remove ${quiz.title} from Your quizzes`"
              @click="removeQuiz(quiz)"
            >
              Remove
            </button>
          </article>
        </div>

        <div class="heading-row pagination">
          <button
            type="button"
            :disabled="Boolean(busy) || page <= 1"
            @click="changePage(page - 1)"
          >
            Previous
          </button>

          <span>Page {{ page }}</span>

          <button
            type="button"
            :disabled="Boolean(busy) || !hasMore"
            @click="changePage(page + 1)"
          >
            Next
          </button>
        </div>
      </section>

      <section v-if="isReviewPage && activeQuiz" class="panel">
        <div class="heading-row">
          <h2>{{ isDraft ? "Review draft" : "Published quiz" }}</h2>
          <span class="badge">{{ activeQuiz.status }}</span>
        </div>

        <p class="description">
          Saved learning mode: {{ learningModeLabel(activeQuiz.learning_mode) }}
        </p>

        <p class="description">
          {{
            isDraft
              ? "Correct answers ar explanations carefully check koro."
              : "This published quiz is read-only."
          }}
        </p>

        <form @submit.prevent="saveDraft">
          <fieldset :disabled="Boolean(busy) || !isDraft" class="editor">
            <label>
              Quiz title
              <input
                v-model="editTitle"
                required
                minlength="3"
                maxlength="150"
              />
            </label>

            <article
              v-for="question in editQuestions"
              :key="question.id"
              class="question-card"
            >
              <h3>Question {{ question.id }}</h3>

              <label>
                Question text
                <textarea
                  v-model="question.question_text"
                  required
                  maxlength="1000"
                  rows="3"
                ></textarea>
              </label>

              <div class="options-grid">
                <label v-for="option in ['a', 'b', 'c', 'd']" :key="option">
                  Option {{ option.toUpperCase() }}
                  <input
                    v-model="question[`option_${option}`]"
                    required
                    maxlength="255"
                  />
                </label>
              </div>

              <label>
                Correct answer
                <select v-model="question.correct_option">
                  <option v-for="option in ['A', 'B', 'C', 'D']" :key="option">
                    {{ option }}
                  </option>
                </select>
              </label>

              <label>
                Explanation
                <textarea
                  v-model="question.explanation"
                  required
                  maxlength="2000"
                  rows="3"
                ></textarea>
              </label>
            </article>

            <button v-if="isDraft" type="submit" class="primary">
              {{ busy === "save" ? "Saving..." : "Save draft" }}
            </button>
          </fieldset>
        </form>

        <template v-if="isDraft">
          <p v-if="hasUnsavedChanges" class="description">
            Save your edits before publishing.
          </p>

          <button
            type="button"
            class="publish"
            :disabled="Boolean(busy) || hasUnsavedChanges"
            @click="publishQuiz"
          >
            {{ busy === "publish" ? "Publishing..." : "Publish quiz" }}
          </button>
        </template>

        <div
          v-if="activeQuiz.status === 'published'"
          class="assignment-section"
        >
          <button
            type="button"
            class="primary"
            :disabled="Boolean(busy)"
            @click="openAssignmentForm"
          >
            {{ assignmentSaved ? "Create another assignment" : "Assign quiz" }}
          </button>

          <section v-if="assignmentOpen" class="question-card">
            <div class="heading-row">
              <h3>Assign: {{ activeQuiz.title }}</h3>

              <button
                type="button"
                :disabled="Boolean(busy)"
                @click="assignmentOpen = false"
              >
                Close
              </button>
            </div>

            <p class="description">
              Times use your device timezone. Correct answers and explanations
              become available at the review time once the student review
              feature is connected.
            </p>

            <p v-if="assignmentClasses.length === 0" class="description">
              Create a class from your teacher dashboard first.
            </p>

            <form v-else @submit.prevent="assignQuiz">
              <fieldset
                class="form-grid"
                :disabled="Boolean(busy) || assignmentSaved"
              >
                <label class="wide">
                  Class
                  <select
                    v-model="assignmentClassId"
                    required
                    @change="loadAssignmentStudents"
                  >
                    <option disabled value="">Select a class</option>

                    <option
                      v-for="classroom in assignmentClasses"
                      :key="classroom.id"
                      :value="classroom.id"
                    >
                      {{ classroom.name }}
                    </option>
                  </select>
                </label>

                <button
                  v-if="assignmentClassId && !studentsReady"
                  type="button"
                  class="wide"
                  @click="loadAssignmentStudents"
                >
                  Retry loading students
                </button>

                <p v-if="studentsReady" class="description wide">
                  {{ assignmentStudents.length }} enrolled students.
                </p>

                <label class="wide">
                  Assign to
                  <select v-model="assignmentAudience">
                    <option value="all">All enrolled students</option>
                    <option value="selected">Selected students</option>
                  </select>
                </label>

                <div
                  v-if="assignmentAudience === 'selected' && studentsReady"
                  class="student-picker wide"
                >
                  <p class="description">
                    Selected: {{ selectedStudentIds.length }}
                  </p>

                  <label
                    v-for="student in assignmentStudents"
                    :key="student.id"
                    class="student-choice"
                  >
                    <input
                      v-model="selectedStudentIds"
                      type="checkbox"
                      :value="student.id"
                    />
                    <span>{{ student.name }} — {{ student.email }}</span>
                  </label>
                </div>

                <label>
                  Available from
                  <input v-model="availableAt" type="datetime-local" required />
                </label>

                <label>
                  Deadline
                  <input v-model="deadlineAt" type="datetime-local" required />
                </label>

                <label>
                  Review available from
                  <input v-model="reviewAt" type="datetime-local" required />
                </label>

                <label>
                  Time limit (minutes)
                  <input
                    v-model.number="timeLimitMinutes"
                    type="number"
                    min="1"
                    max="180"
                    step="1"
                    required
                  />
                </label>

                <label>
                  Allowed attempts
                  <input
                    v-model.number="maxAttempts"
                    type="number"
                    min="1"
                    max="5"
                    step="1"
                    required
                  />
                </label>

                <button
                  type="submit"
                  class="primary wide"
                  :disabled="!studentsReady || assignmentStudents.length === 0"
                >
                  {{
                    assignmentSaved
                      ? "Assignment saved"
                      : busy === "assign"
                        ? "Assigning..."
                        : "Assign to students"
                  }}
                </button>
              </fieldset>
            </form>
          </section>
        </div>
      </section>

      <section v-if="!isReviewPage && selectedResults" class="panel">
        <TeacherQuizMistakeReport
          :key="selectedResults.assignment.id"
          :assignment-id="selectedResults.assignment.id"
        />
      </section>
    </template>
  </section>
</template>

<style scoped>
.quiz-page {
  display: grid;
  gap: 1.5rem;
  min-width: 0;
  color: var(--text-primary);
}

.eyebrow {
  color: var(--accent-color);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.1em;
}

h1,
h2,
h3 {
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
}

.panel {
  min-width: 0;
  padding: 1.5rem;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 1rem;
}

fieldset {
  min-width: 0;
  border: 0;
  padding: 0;
  margin: 1rem 0 0;
}

.form-grid,
.options-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.wide {
  grid-column: 1 / -1;
}

label,
.editor,
.question-card {
  display: grid;
  gap: 0.65rem;
}

label {
  min-width: 0;
  font-weight: 600;
  font-size: 0.9rem;
}

input,
select,
textarea,
button {
  font: inherit;
  box-sizing: border-box;
  border: 1px solid var(--border-color);
  border-radius: 0.65rem;
}

input,
select,
textarea {
  width: 100%;
  min-width: 0;
  padding: 0.8rem;
  color: var(--text-primary);
  background: var(--page-background);
}

textarea {
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

input:focus-visible,
select:focus-visible,
textarea:focus-visible,
button:focus-visible {
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

.quiz-item {
  display: grid;
  gap: 0.4rem;
  text-align: left;
  overflow-wrap: anywhere;
}

.quiz-item span {
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.selected {
  border-color: var(--accent-color);
}

.pagination {
  margin-top: 1rem;
}

.question-card {
  padding: 1rem;
  gap: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.8rem;
  background: var(--page-background);
}

.editor {
  gap: 1.25rem;
}

.badge {
  padding: 0.4rem 0.7rem;
  border-radius: 0.5rem;
  color: var(--accent-color);
  background: var(--nav-hover);
  font-size: 0.85rem;
}

.publish {
  margin-top: 1rem;
}

.error {
  color: #dc2626;
  line-height: 1.6;
}

.success {
  color: var(--accent-color);
  line-height: 1.6;
}

.assignment-section {
  display: grid;
  gap: 1rem;
  margin-top: 1.5rem;
}

.student-picker {
  display: grid;
  gap: 0.75rem;
  max-height: 300px;
  overflow-y: auto;
  padding: 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.8rem;
}

.student-choice {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.student-choice input {
  width: 1.1rem;
  height: 1.1rem;
  flex-shrink: 0;
  accent-color: var(--accent-color);
}

.student-choice span {
  overflow-wrap: anywhere;
}

.best-score {
  margin: 0;
  color: var(--accent-color);
  font-weight: 700;
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
  margin: 0;
  line-height: 1.6;
  overflow-wrap: anywhere;
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

.review-feedback h4 {
  margin: 0;
  overflow-wrap: anywhere;
}

.review-feedback p {
  margin: 0;
}

.review-feedback button {
  justify-self: start;
}

@media (max-width: 540px) {
  .panel {
    padding: 1rem;
  }

  .form-grid,
  .options-grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  button {
    transition: none;
  }
}
.assigned-quizzes-link {
  display: inline-block;
  margin-top: 0.75rem;
  color: var(--accent-color);
  font-weight: 700;
  text-decoration: underline;
  text-underline-offset: 4px;
}

.assigned-quizzes-link:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 4px;
}
.quiz-list-row {
  display: flex;
  align-items: stretch;
  gap: 0.75rem;
  min-width: 0;
}

.quiz-list-row .quiz-item {
  flex: 1;
  min-width: 0;
}

.remove-quiz {
  flex-shrink: 0;
  align-self: center;
  color: #dc2626;
}
.remove-quiz:hover:not(:disabled) {
  background: #fee2e2;
}

@media (max-width: 540px) {
  .quiz-list-row {
    flex-direction: column;
  }

  .remove-quiz {
    align-self: flex-start;
  }
}
.quiz-header-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1rem;
}

.quiz-page button,
.quiz-page .assigned-quizzes-link {
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.quiz-page button:not(.quiz-item):not(.remove-quiz),
.quiz-page .assigned-quizzes-link {
  border: 1px solid #2450db;
  background: #2450db;
  color: #fff;
}

.quiz-page .assigned-quizzes-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-top: 0;
  padding: 0.75rem 1rem;
  border-radius: 0.65rem;
  font: inherit;
  font-weight: 700;
  text-decoration: none;
}

.quiz-page button:not(.quiz-item):not(.remove-quiz):hover:not(:disabled),
.quiz-page .assigned-quizzes-link:hover {
  border-color: #1d3fb8;
  background: #1d3fb8;
  color: #fff;
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.quiz-page button.quiz-item {
  background: var(--page-background);
  color: #2450db;
}

.quiz-page button.quiz-item:hover:not(:disabled) {
  border-color: #2450db;
  background: var(--nav-hover);
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.quiz-page button.remove-quiz {
  border-color: #dc2626;
  background: transparent;
  color: #dc2626;
}

.quiz-page button.remove-quiz:hover:not(:disabled) {
  border-color: #dc2626;
  background: rgb(220 38 38 / 10%);
  color: #dc2626;
  box-shadow: 0 0.6rem 1rem rgb(220 38 38 / 20%);
  transform: translateY(-2px);
}

.quiz-page button:active:not(:disabled),
.quiz-page .assigned-quizzes-link:active {
  transform: scale(0.98);
}

.quiz-page .assigned-quizzes-link:focus-visible {
  outline: 2px solid #2450db;
  outline-offset: 3px;
}

.quiz-page button.remove-quiz:focus-visible {
  outline-color: #dc2626;
}
</style>
