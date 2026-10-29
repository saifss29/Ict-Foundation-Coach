<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useStore } from "vuex";
import TeacherClassExams from "../components/TeacherClassExams.vue";
import TeacherParentEmailCorrection from "../components/TeacherParentEmailCorrection.vue";

const route = useRoute();
const router = useRouter();
const store = useStore();

const analytics = ref(null);
const isLoading = ref(false);
const loadError = ref("");

const classroomId = computed(() => route.params.classroomId);
const studentsNeedingAttention = computed(() => {
  if (!analytics.value) {
    return [];
  }

  return analytics.value.students.filter((student) => {
    return (
      student.total_attempts === 0 ||
      (student.latest_percentage !== null && student.latest_percentage < 50)
    );
  });
});

async function loadAnalytics() {
  if (isLoading.value) return;

  isLoading.value = true;
  loadError.value = "";

  try {
    const response = await fetch(
      `http://127.0.0.1:5000/api/classes/${classroomId.value}`,
      {
        headers: {
          Authorization: `Bearer ${store.state.auth.accessToken}`,
        },
      },
    );

    if (response.status === 401) {
      store.commit("auth/CLEAR_AUTH");
      await router.replace("/login");
      throw new Error("Your session has expired. Please log in again.");
    }

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Could not load class analytics.");
    }

    analytics.value = data;
  } catch (error) {
    loadError.value =
      error instanceof Error
        ? error.message
        : "Could not load class analytics.";
  } finally {
    isLoading.value = false;
  }
}

function goBackToClasses() {
  router.push("/teacher");
}
function viewAttemptHistory(studentId) {
  router.push({
    name: "teacher-student-attempt-history",
    params: {
      classroomId: classroomId.value,
      studentId,
    },
  });
}

function formatPercentage(percentage) {
  if (percentage === null || percentage === undefined) {
    return "No quiz yet";
  }

  return `${percentage}%`;
}

function formatDate(dateValue) {
  if (!dateValue) {
    return "No activity yet";
  }

  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(dateValue));
}

onMounted(loadAnalytics);
</script>

<template>
  <section class="analytics-page">
    <button type="button" class="back-button" @click="goBackToClasses">
      ← Back to classes
    </button>

    <p v-if="isLoading" class="status-note" role="status">
      Loading class analytics...
    </p>

    <section v-else-if="loadError" class="error-state">
      <h1>Could not load analytics</h1>
      <p>{{ loadError }}</p>

      <div class="error-actions">
        <button type="button" class="secondary-button" @click="loadAnalytics">
          Try again
        </button>

        <button type="button" class="primary-button" @click="goBackToClasses">
          Back to classes
        </button>
      </div>
    </section>

    <template v-else-if="analytics">
      <header class="analytics-header">
        <p class="eyebrow">CLASS ANALYTICS</p>
        <h1>{{ analytics.classroom.name }}</h1>
        <p class="intro">
          Student progress, recent quiz result, ar kon topic-e extra support
          lagte pare—sob ekhane dekhte parbe.
        </p>

        <div class="join-code">
          <span>JOIN CODE</span>
          <code>{{ analytics.classroom.join_code }}</code>
        </div>
      </header>
      <TeacherClassExams :key="classroomId" :classroom-id="classroomId" />

      <section class="summary-grid" aria-label="Class summary">
        <article class="summary-card">
          <span>Students</span>
          <strong>{{ analytics.summary.student_count }}</strong>
          <small>Total joined students</small>
        </article>

        <article class="summary-card">
          <span>Started learning</span>
          <strong>{{ analytics.summary.students_started_learning }}</strong>
          <small>At least one quiz completed</small>
        </article>

        <article class="summary-card">
          <span>Quiz attempts</span>
          <strong>{{ analytics.summary.total_quiz_attempts }}</strong>
          <small>All students combined</small>
        </article>

        <article class="summary-card">
          <span>Class average</span>
          <strong>
            {{
              formatPercentage(
                analytics.summary.class_average_latest_percentage,
              )
            }}
          </strong>
          <small>Latest quiz result per student</small>
        </article>
      </section>
      <section
        v-if="analytics.students.length > 0"
        class="attention-panel"
        aria-labelledby="attention-heading"
      >
        <div class="panel-heading">
          <div>
            <p class="eyebrow">TEACHER FOCUS</p>
            <h2 id="attention-heading">Needs attention</h2>
          </div>

          <span class="attention-count">
            {{ studentsNeedingAttention.length }} students
          </span>
        </div>

        <p v-if="studentsNeedingAttention.length === 0" class="all-clear">
          Great! Every student has started learning and no latest quiz score is
          below 50%.
        </p>

        <div v-else class="attention-list">
          <article
            v-for="student in studentsNeedingAttention"
            :key="student.id"
            class="attention-card"
          >
            <div>
              <h3>{{ student.name }}</h3>
              <p>{{ student.email }}</p>
            </div>

            <div class="attention-reason">
              <template v-if="student.total_attempts === 0">
                <strong>Has not started a quiz yet</strong>
                <small>Ask the student to begin with any ICT topic.</small>
              </template>

              <template v-else>
                <strong>{{ student.latest_percentage }}% latest result</strong>
                <small v-if="student.weakest_topic">
                  Practice: {{ student.weakest_topic.title }}
                </small>
              </template>
            </div>
          </article>
        </div>
      </section>

      <section class="students-panel" aria-labelledby="students-heading">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">STUDENT PERFORMANCE</p>
            <h2 id="students-heading">Students in this class</h2>
          </div>

          <span class="student-count">
            {{ analytics.students.length }} students
          </span>
        </div>

        <div v-if="analytics.students.length === 0" class="empty-state">
          <h3>No students have joined yet</h3>
          <p>
            Join code-ta share koro. Student-ra join korle tader learning
            activity ekhane dekhabe.
          </p>
        </div>

        <div v-else class="student-list">
          <article
            v-for="student in analytics.students"
            :key="student.id"
            class="student-card"
          >
            <div class="student-main">
              <div class="student-avatar" aria-hidden="true">
                {{ student.name.charAt(0).toUpperCase() }}
              </div>

              <div>
                <h3>{{ student.name }}</h3>
                <p>{{ student.email }}</p>
                <small>Joined {{ formatDate(student.joined_at) }}</small>
              </div>
            </div>

            <div class="student-stat">
              <span>Latest result</span>
              <strong
                :class="{
                  'good-score': student.latest_percentage >= 70,
                  'needs-support':
                    student.latest_percentage !== null &&
                    student.latest_percentage < 50,
                }"
              >
                {{ formatPercentage(student.latest_percentage) }}
              </strong>
            </div>

            <div class="student-stat">
              <span>Quiz attempts</span>
              <strong>{{ student.total_attempts }}</strong>
            </div>

            <div class="student-stat weakness">
              <span>Needs practice</span>

              <template v-if="student.weakest_topic">
                <strong>{{ student.weakest_topic.title }}</strong>
                <small
                  >{{ student.weakest_topic.percentage }}% latest score</small
                >
              </template>

              <strong v-else>Not enough data</strong>
            </div>

            <div class="student-actions">
              <div class="student-stat">
                <span>Last quiz activity</span>
                <small>{{ formatDate(student.last_quiz_at) }}</small>
              </div>

              <button
                type="button"
                class="history-button"
                @click="viewAttemptHistory(student.id)"
              >
                View history
              </button>
            </div>
            <TeacherParentEmailCorrection
              class="parent-correction-row"
              :classroom-id="classroomId"
              :student-id="student.id"
              :student-name="student.name"
            />
          </article>
        </div>
      </section>
    </template>
  </section>
</template>

<style scoped>
.analytics-page {
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

.back-button:hover,
.secondary-button:hover {
  background: var(--nav-hover);
}

.primary-button {
  background: var(--accent-color);
  color: var(--surface-color);
}

.primary-button:hover {
  background: var(--accent-hover);
}

.back-button:active,
.primary-button:active,
.secondary-button:active {
  transform: scale(0.97);
}

button:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

.analytics-header {
  min-width: 0;
}

.eyebrow {
  margin: 0 0 0.6rem;
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

.intro {
  max-width: 44rem;
  margin: 0.85rem 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.join-code {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  margin-top: 1.25rem;
}

.join-code span,
.student-stat > span {
  color: var(--text-secondary);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.join-code code {
  border: 1px solid var(--border-color);
  border-radius: 0.55rem;
  padding: 0.5rem 0.7rem;
  background: var(--surface-color);
  color: var(--accent-color);
  font-size: 1rem;
  font-weight: 800;
  letter-spacing: 0.11em;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
}

.summary-card,
.students-panel,
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
  line-height: 1.4;
}

.summary-card strong {
  color: var(--text-primary);
  font-size: 1.7rem;
  line-height: 1.2;
}
.attention-panel {
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  padding: 1.5rem;
  background: var(--surface-color);
}

.attention-count {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 0.4rem 0.65rem;
  background: #fef3c7;
  color: #92400e;
  font-size: 0.82rem;
  font-weight: 800;
}

.attention-list {
  display: grid;
  gap: 0.75rem;
  margin-top: 1.2rem;
}

.attention-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  border: 1px solid var(--border-color);
  border-left: 4px solid #f59e0b;
  border-radius: 0.8rem;
  padding: 1rem;
  background: var(--page-background);
}

.attention-card p,
.attention-reason small {
  display: block;
  margin: 0.25rem 0 0;
  color: var(--text-secondary);
  font-size: 0.85rem;
  line-height: 1.45;
}

.attention-reason {
  display: grid;
  gap: 0.25rem;
  text-align: right;
}

.attention-reason strong {
  color: #b45309;
  font-size: 0.92rem;
}

.all-clear {
  margin: 1.1rem 0 0;
  border-radius: 0.75rem;
  padding: 0.9rem 1rem;
  background: var(--nav-hover);
  color: var(--text-secondary);
  line-height: 1.6;
}

:global(.dark-theme) .attention-count {
  background: #4a3410;
  color: #fde68a;
}

:global(.dark-theme) .attention-reason strong {
  color: #fcd34d;
}

.students-panel {
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

.student-count {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 0.4rem 0.65rem;
  background: var(--nav-hover);
  color: var(--accent-color);
  font-size: 0.82rem;
  font-weight: 700;
}

.student-list {
  display: grid;
  gap: 0.8rem;
  margin-top: 1.35rem;
}

.student-card {
  display: grid;
  grid-template-columns: minmax(12rem, 1.5fr) 0.8fr 0.8fr 1.2fr 1.15fr;
  align-items: center;
  gap: 1rem;
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 0.85rem;
  padding: 1rem;
  background: var(--page-background);
}

.student-main {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 0.75rem;
}

.student-avatar {
  display: grid;
  flex: 0 0 auto;
  width: 2.5rem;
  height: 2.5rem;
  place-items: center;
  border-radius: 50%;
  background: var(--nav-hover);
  color: var(--accent-color);
  font-weight: 800;
}

.student-main p,
.student-main small,
.student-stat small {
  display: block;
  color: var(--text-secondary);
}

.student-main p {
  overflow: hidden;
  margin: 0.2rem 0;
  font-size: 0.85rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.student-main small,
.student-stat small {
  font-size: 0.75rem;
  line-height: 1.45;
}
.student-actions {
  display: grid;
  gap: 0.7rem;
  min-width: 0;
}

.history-button {
  width: fit-content;
  border: 1px solid var(--border-color);
  border-radius: 0.55rem;
  padding: 0.5rem 0.65rem;
  background: var(--surface-color);
  color: var(--accent-color);
  cursor: pointer;
  font: inherit;
  font-size: 0.82rem;
  font-weight: 700;
  transition:
    background-color 0.2s ease,
    transform 0.2s ease;
}

.history-button:hover {
  background: var(--nav-hover);
}

.history-button:active {
  transform: scale(0.97);
}

.history-button:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

.student-stat {
  display: grid;
  gap: 0.35rem;
  min-width: 0;
}

.student-stat strong {
  color: var(--text-primary);
  font-size: 0.95rem;
  overflow-wrap: anywhere;
}

.good-score {
  color: #15803d !important;
}

.needs-support {
  color: #dc2626 !important;
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
}

@media (max-width: 1080px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .student-card {
    grid-template-columns: minmax(12rem, 1.4fr) 1fr 1fr;
  }

  .weakness,
  .last-activity {
    grid-column: span 1;
  }
}

@media (max-width: 680px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .attention-panel,
  .students-panel {
    padding: 1rem;
  }

  .panel-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .attention-card {
    align-items: flex-start;
    flex-direction: column;
  }

  .attention-reason {
    text-align: left;
  }

  .student-card {
    grid-template-columns: 1fr 1fr;
    gap: 1rem 0.75rem;
  }

  .student-main {
    grid-column: 1 / -1;
  }

  .last-activity {
    grid-column: 1 / -1;
  }
  .student-actions {
    grid-column: 1 / -1;
  }
}
.analytics-page :deep(button) {
  border: 1px solid #2450db;
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

.analytics-page :deep(button:hover:not(:disabled)) {
  border-color: #1d3fb8;
  background: #1d3fb8;
  color: #fff;
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.analytics-page :deep(button:active:not(:disabled)) {
  transform: scale(0.98);
}

.analytics-page :deep(button:focus-visible) {
  outline: 2px solid #2450db;
  outline-offset: 3px;
}

.analytics-page :deep(button:disabled) {
  opacity: 0.55;
  cursor: not-allowed;
}
.parent-correction-row {
  grid-column: 1 / -1;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-color);
}
</style>
