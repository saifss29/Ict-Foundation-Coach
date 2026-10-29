<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useStore } from "vuex";

const router = useRouter();
const store = useStore();

const quizzes = ref([]);
const page = ref(1);
const hasMore = ref(false);
const busy = ref(false);
const loaded = ref(false);
const errorMessage = ref("");

let active = true;

function learningModeLabel(mode) {
  return (
    {
      personal_growth: "Personal growth",
      exam_preparation: "Exam preparation",
    }[mode] || "Mode unavailable"
  );
}

async function loadHistory(nextPage = 1) {
  if (busy.value) return;

  busy.value = true;
  errorMessage.value = "";

  const token = store.state.auth.accessToken;

  try {
    const response = await fetch(
      `http://127.0.0.1:5000/api/teacher-quizzes?view=history&page=${nextPage}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    if (!active || token !== store.state.auth.accessToken) return;

    if (response.status === 401) {
      store.commit("auth/CLEAR_AUTH");
      await router.replace("/login");
      return;
    }

    let data;

    try {
      data = await response.json();
    } catch {
      throw new Error("Could not read the server response. Try again.");
    }

    if (!active || token !== store.state.auth.accessToken) return;

    if (!response.ok) {
      throw new Error(data.error || "Could not load quiz history.");
    }

    quizzes.value = data.quizzes;
    page.value = data.pagination.page;
    hasMore.value = data.pagination.has_more;
    loaded.value = true;
  } catch (error) {
    if (active && token === store.state.auth.accessToken) {
      errorMessage.value =
        error instanceof Error ? error.message : "Could not load quiz history.";
    }
  } finally {
    if (active) busy.value = false;
  }
}

function openQuiz(quizId) {
  if (busy.value) return;

  router.push({
    name: "teacher-quiz-review",
    params: { quizId },
  });
}

onMounted(() => loadHistory());

onBeforeUnmount(() => {
  active = false;
});
</script>

<template>
  <section class="history-page" :aria-busy="busy">
    <header>
      <p class="eyebrow">TEACHER QUIZZES</p>
      <h1>Quiz History</h1>
      <p class="description">
        Removed quizzes ekhane saved ache. Quiz kholo, questions dekho, ar draft
        hole ager moto edit/publish korte parba.
      </p>

      <RouterLink :to="{ name: 'teacher-quizzes' }" class="back-link">
        Back to Generate quizzes
      </RouterLink>
    </header>

    <p v-if="errorMessage" class="error" role="alert">
      {{ errorMessage }}
    </p>

    <section class="panel">
      <div class="heading-row">
        <h2>Removed quizzes</h2>
        <button type="button" :disabled="busy" @click="loadHistory(page)">
          {{ busy ? "Loading..." : "Refresh" }}
        </button>
      </div>

      <p v-if="!loaded && busy" class="description" role="status">
        Loading quiz history...
      </p>

      <p v-else-if="loaded && quizzes.length === 0" class="description">
        No removed quizzes on this page.
      </p>

      <div class="quiz-list">
        <button
          v-for="quiz in quizzes"
          :key="quiz.id"
          type="button"
          class="quiz-item"
          :disabled="busy"
          @click="openQuiz(quiz.id)"
        >
          <strong>{{ quiz.title }}</strong>
          <span>
            {{ quiz.question_count }} questions · {{ quiz.response_language }} ·
            {{ quiz.status }} ·
            {{ learningModeLabel(quiz.learning_mode) }}
          </span>
          <span class="open-label">View quiz →</span>
        </button>
      </div>

      <div v-if="loaded" class="heading-row pagination">
        <button
          type="button"
          :disabled="busy || page <= 1"
          @click="loadHistory(page - 1)"
        >
          Previous
        </button>

        <span>Page {{ page }}</span>

        <button
          type="button"
          :disabled="busy || !hasMore"
          @click="loadHistory(page + 1)"
        >
          Next
        </button>
      </div>
    </section>
  </section>
</template>

<style scoped>
.history-page {
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
h2 {
  margin: 0;
  overflow-wrap: anywhere;
}

h1 {
  font-size: clamp(1.6rem, 4vw, 2.4rem);
}

h2 {
  font-size: 1.2rem;
}

.description {
  color: var(--text-secondary);
  line-height: 1.7;
}

.back-link {
  display: inline-block;
  color: var(--accent-color);
  font-weight: 700;
  text-underline-offset: 4px;
}

.panel {
  min-width: 0;
  padding: 1.5rem;
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 1rem;
}

.heading-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
}

button {
  box-sizing: border-box;
  padding: 0.75rem 1rem;
  font: inherit;
  font-weight: 700;
  color: var(--accent-color);
  background: var(--page-background);
  border: 1px solid var(--border-color);
  border-radius: 0.65rem;
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

button:focus-visible,
.back-link:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

.quiz-list {
  display: grid;
  gap: 0.75rem;
  margin-top: 1rem;
}

.quiz-item {
  display: grid;
  gap: 0.5rem;
  width: 100%;
  min-width: 0;
  text-align: left;
  overflow-wrap: anywhere;
}

.quiz-item span {
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.quiz-item .open-label {
  color: var(--accent-color);
}

.pagination {
  margin-top: 1rem;
}

.error {
  color: #dc2626;
  line-height: 1.6;
}

@media (max-width: 540px) {
  .panel {
    padding: 1rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  button {
    transition: none;
  }
}
</style>
