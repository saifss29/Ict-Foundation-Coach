<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { useStore } from "vuex";

const route = useRoute();
const router = useRouter();
const store = useStore();

const API_BASE = "http://127.0.0.1:5000";
const topicSlug = String(route.params.slug);

const topic = ref(null);
const questions = ref([]);
const selectedAnswers = ref({});
const quizResult = ref(null);

const isLoading = ref(true);
const isSubmitting = ref(false);
const isGenerating = ref(false);
const errorMessage = ref("");

const generatedQuizId = ref(null);
const generatedQuizExpiresAt = ref(null);
const generatedQuizUnavailable = ref(false);

const selectedLearningMode = ref("personal_growth");
const generatedQuizLearningMode = ref(null);
const generatedPracticeTopic = ref(null);

const requestController = new AbortController();
let isDisposed = false;

const isGeneratedQuiz = computed(() => Boolean(generatedQuizId.value));

const generatedModeLabel = computed(() => {
  return generatedQuizLearningMode.value === "exam_preparation"
    ? "Exam preparation"
    : "Personal growth";
});

const supportsAIQuiz = computed(() => topicSlug === "number-systems");

const isBusy = computed(
  () => isLoading.value || isSubmitting.value || isGenerating.value,
);

const answeredQuestionCount = computed(
  () =>
    questions.value.filter((question) =>
      ["A", "B", "C", "D"].includes(selectedAnswers.value[question.id]),
    ).length,
);

const canSubmit = computed(
  () =>
    questions.value.length > 0 &&
    answeredQuestionCount.value === questions.value.length &&
    !isBusy.value &&
    !generatedQuizUnavailable.value,
);

const expiryLabel = computed(() => {
  if (!generatedQuizExpiresAt.value) {
    return "";
  }

  const expiry = new Date(generatedQuizExpiresAt.value);

  if (Number.isNaN(expiry.getTime())) {
    return "";
  }

  return expiry.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
});

const scorePercentage = computed(() => {
  const attempt = quizResult.value?.attempt;

  if (!attempt?.total_questions) {
    return 0;
  }

  return Math.round((attempt.score / attempt.total_questions) * 100);
});

const incorrectQuestionCount = computed(
  () =>
    quizResult.value?.results?.filter((result) => !result.is_correct).length ||
    0,
);

const performanceFeedback = computed(() => {
  if (scorePercentage.value >= 80) {
    return {
      tone: "strong",
      title: "Excellent work. You are ready to move forward!",
      description:
        "Tumi ei topic-er core concept bhalo bujhecho. Ekhon next topic-e giye learning continue korte paro.",
      action: "Next topic-e jawar age explanation gula ekbar dekhe nao.",
    };
  }

  if (scorePercentage.value >= 60) {
    return {
      tone: "developing",
      title: "Good progress. A little more practice will help.",
      description:
        "Tomar basic understanding ache, but kichu concept aro clear kora dorkar.",
      action:
        "Je question-gula wrong hoyeche, explanation pore abar Try Again koro.",
    };
  }

  return {
    tone: "needs-practice",
    title: "This topic needs a little more revision.",
    description:
      "Kono problem nai—wrong answer thekeo learning hoy. Age explanation gula poro, then Maira-ke question koro.",
    action: "Tutor-er help niye concept revise kore abar practice koro.",
  };
});

function getResponseLanguage() {
  const language = localStorage.getItem("ict-coach-response-language");

  return ["banglish", "english"].includes(language) ? language : "banglish";
}

function clearAuthAndRedirect() {
  store.commit("auth/CLEAR_AUTH");
  router.replace("/login");
}

function getErrorText(error, fallback) {
  return error instanceof Error ? error.message : fallback;
}

async function apiRequest(path, options = {}) {
  const accessToken = store.state.auth.accessToken;

  if (!accessToken) {
    router.replace("/login");
    return null;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    signal: requestController.signal,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
      Authorization: `Bearer ${accessToken}`,
    },
  });

  // Ignore a response if this page or the signed-in session changed.
  if (isDisposed || store.state.auth.accessToken !== accessToken) {
    return null;
  }

  if (response.status === 401) {
    clearAuthAndRedirect();
    return null;
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const error = new Error(
      data?.error || data?.msg || "Request failed. Please try again.",
    );

    error.status = response.status;
    throw error;
  }

  if (!data || typeof data !== "object") {
    throw new Error("Server returned an invalid response. Please try again.");
  }

  return data;
}

function validateQuiz(quiz) {
  if (
    !quiz?.topic ||
    !Array.isArray(quiz.questions) ||
    quiz.questions.some(
      (question) =>
        question.id == null ||
        typeof question.question_text !== "string" ||
        !Array.isArray(question.options) ||
        question.options.length !== 4,
    )
  ) {
    throw new Error("Quiz data is incomplete. Please try again.");
  }
}

function resetAttempt() {
  selectedAnswers.value = {};
  quizResult.value = null;
  generatedQuizUnavailable.value = false;
}

async function loadQuiz() {
  if (isSubmitting.value || isGenerating.value) {
    return;
  }

  isLoading.value = true;
  errorMessage.value = "";

  try {
    const data = await apiRequest(
      `/api/topics/${encodeURIComponent(topicSlug)}/quiz`,
    );

    if (!data) {
      return;
    }

    validateQuiz(data);

    topic.value = data.topic;
    questions.value = data.questions;
    generatedQuizId.value = null;
    generatedQuizExpiresAt.value = null;
    generatedQuizLearningMode.value = null;
    generatedPracticeTopic.value = null;
    resetAttempt();

    if (questions.value.length === 0) {
      errorMessage.value = "Ei topic-er practice question ekhono add hoyni.";
    }
  } catch (error) {
    if (!isDisposed) {
      errorMessage.value = getErrorText(error, "Could not load quiz.");
    }
  } finally {
    if (!isDisposed) {
      isLoading.value = false;
    }
  }
}

async function generateAIQuiz() {
  if (!supportsAIQuiz.value || isBusy.value) {
    return;
  }

  isGenerating.value = true;
  errorMessage.value = "";

  try {
    const data = await apiRequest("/api/generated-quizzes", {
      method: "POST",
      body: JSON.stringify({
        topic_slug: topicSlug,
        response_language: getResponseLanguage(),
        learning_mode: selectedLearningMode.value,
      }),
    });

    if (!data) {
      return;
    }

    validateQuiz(data.quiz);

    if (!data.quiz.id || data.quiz.questions.length !== 5) {
      throw new Error("AI returned an incomplete quiz. Please try again.");
    }

    if (
      !["exam_preparation", "personal_growth"].includes(data.quiz.learning_mode)
    ) {
      throw new Error("Server returned an invalid quiz learning mode.");
    }

    // Keep the existing quiz/result visible until generation succeeds.
    topic.value = data.quiz.topic;
    questions.value = data.quiz.questions;
    generatedQuizId.value = data.quiz.id;
    generatedQuizExpiresAt.value = data.quiz.expires_at;
    generatedQuizLearningMode.value = data.quiz.learning_mode;
    resetAttempt();
  } catch (error) {
    if (!isDisposed) {
      errorMessage.value = getErrorText(
        error,
        "Could not generate AI quiz. You can use the standard quiz.",
      );
    }
  } finally {
    if (!isDisposed) {
      isGenerating.value = false;
    }
  }
}

function tryAgain() {
  if (isBusy.value) {
    return;
  }

  if (isGeneratedQuiz.value) {
    router.push({ name: "quiz-practice" });
    return;
  }

  resetAttempt();
  errorMessage.value = "";

  window.scrollTo({
    top: 0,
    left: 0,
    behavior: "auto",
  });
}

async function submitQuiz() {
  if (!canSubmit.value) {
    return;
  }

  isSubmitting.value = true;
  errorMessage.value = "";

  const answers = questions.value.map((question) => ({
    question_id: question.id,
    selected_option: selectedAnswers.value[question.id],
  }));

  const endpoint = isGeneratedQuiz.value
    ? `/api/generated-quizzes/${encodeURIComponent(generatedQuizId.value)}/submit`
    : `/api/topics/${encodeURIComponent(topicSlug)}/quiz/submit`;

  try {
    const data = await apiRequest(endpoint, {
      method: "POST",
      body: JSON.stringify({ answers }),
    });

    if (!data) {
      return;
    }

    if (!data.attempt || !Array.isArray(data.results)) {
      throw new Error("Server returned an incomplete quiz result.");
    }

    quizResult.value = {
      ...data,
      results: data.results.map((result) => ({
        ...result,
        question_text:
          questions.value.find(
            (question) => String(question.id) === String(result.question_id),
          )?.question_text || "",
      })),
    };
  } catch (error) {
    if (!isDisposed) {
      if (isGeneratedQuiz.value && [409, 410].includes(error?.status)) {
        generatedQuizUnavailable.value = true;
      }

      errorMessage.value = getErrorText(error, "Could not submit quiz.");
    }
  } finally {
    if (!isDisposed) {
      isSubmitting.value = false;
    }
  }
}

async function loadGeneratedQuiz(quizId) {
  isLoading.value = true;
  errorMessage.value = "";

  try {
    const data = await apiRequest(
      `/api/generated-quizzes/${encodeURIComponent(quizId)}`,
    );

    if (!data) return;

    validateQuiz(data.quiz);

    if (
      data.quiz.id !== quizId ||
      data.quiz.topic.slug !== topicSlug ||
      data.quiz.questions.length !== 5 ||
      !["exam_preparation", "personal_growth"].includes(data.quiz.learning_mode)
    ) {
      throw new Error("Server returned an invalid generated quiz.");
    }

    topic.value = data.quiz.topic;
    questions.value = data.quiz.questions;
    generatedQuizId.value = data.quiz.id;
    generatedQuizExpiresAt.value = data.quiz.expires_at;
    generatedQuizLearningMode.value = data.quiz.learning_mode;
    generatedPracticeTopic.value = data.quiz.practice_topic ?? null;
    selectedLearningMode.value = data.quiz.learning_mode;
    resetAttempt();
  } catch (error) {
    if (!isDisposed) {
      questions.value = [];
      errorMessage.value = getErrorText(
        error,
        "Could not load the generated quiz. Return to Quiz Practice to generate another quiz.",
      );
    }
  } finally {
    if (!isDisposed) {
      isLoading.value = false;
    }
  }
}

onMounted(() => {
  const quizId = route.query.generated_quiz_id;

  if (quizId !== undefined) {
    if (typeof quizId !== "string" || !quizId.trim() || quizId.length > 36) {
      errorMessage.value = "Invalid generated quiz link.";
      isLoading.value = false;
      return;
    }

    loadGeneratedQuiz(quizId);
    return;
  }

  if (
    ["ssc-ict", "hsc-ict"].includes(topicSlug) ||
    topicSlug.startsWith("ssc-ict-")
  ) {
    errorMessage.value =
      "Quiz Practice page-e topic select kore Generate quiz click koro.";
    isLoading.value = false;
    return;
  }

  loadQuiz();
});

onBeforeUnmount(() => {
  isDisposed = true;
  requestController.abort();
});
</script>

<template>
  <section class="quiz-page">
    <RouterLink class="back-link" :to="{ name: 'quiz-practice' }">
      <span>←</span>
      Back to Quiz Practice
    </RouterLink>
    <section
      v-if="(supportsAIQuiz || isGeneratedQuiz) && topic"
      class="quiz-mode-panel"
      aria-label="Quiz type"
      :aria-busy="isGenerating"
    >
      <div class="quiz-mode-description">
        <p class="quiz-mode-label">
          {{ isGeneratedQuiz ? "AI PRACTICE" : "STANDARD PRACTICE" }}
        </p>

        <p>
          {{
            isGeneratedQuiz
              ? "Maira-generated 5 questions diye ei topic practice koro."
              : "Existing questions practice koro, ba Maira diye notun quiz banao."
          }}
        </p>

        <small v-if="isGeneratedQuiz">
          Current quiz mode: {{ generatedModeLabel }}
        </small>

        <small v-if="isGeneratedQuiz && expiryLabel && !quizResult">
          Submit before {{ expiryLabel }}.
        </small>

        <small v-if="generatedQuizUnavailable">
          Ei quiz ar submit kora jabe na. Notun quiz generate koro.
        </small>
      </div>
      <div
        v-if="supportsAIQuiz && !isGeneratedQuiz"
        class="learning-mode-control"
      >
        <label for="quiz-learning-mode">New AI quiz learning mode</label>

        <select
          id="quiz-learning-mode"
          v-model="selectedLearningMode"
          :disabled="isBusy"
        >
          <option value="personal_growth">Personal growth</option>
          <option value="exam_preparation">Exam preparation</option>
        </select>

        <small>
          Currently supports 5 Number Systems MCQs. Full board-format practice
          is not available yet.
        </small>
      </div>

      <div class="quiz-mode-actions">
        <RouterLink
          v-if="isGeneratedQuiz"
          class="back-link"
          :to="{ name: 'quiz-practice' }"
        >
          Choose another quiz →
        </RouterLink>

        <button
          v-else-if="supportsAIQuiz"
          type="button"
          class="generate-quiz-button"
          :disabled="isBusy"
          @click="generateAIQuiz"
        >
          {{ isGenerating ? "Generating questions..." : "Generate AI quiz" }}
        </button>
      </div>

      <p v-if="isGenerating" class="generation-message" role="status">
        Maira questions toiri korche. Ektu opekkha koro…
      </p>
    </section>

    <p v-if="isLoading" class="loading-message">Quiz loading...</p>

    <template v-else-if="topic">
      <Transition name="quiz-content" mode="out-in">
        <section v-if="!quizResult" key="quiz" class="quiz-attempt">
          <section class="quiz-hero">
            <div>
              <p class="hero-label">
                {{ isGeneratedQuiz ? "AI-GENERATED QUIZ" : "MINI QUIZ" }}
              </p>
              <h1>
                {{ generatedPracticeTopic || topic.title }}
              </h1>
              <p>
                Shob question-er answer select koro, then submit kore result
                dekho.
              </p>
            </div>

            <div class="question-progress">
              <strong>{{ answeredQuestionCount }}</strong>
              <span>/ {{ questions.length }}</span>
              <small>answered</small>
            </div>
          </section>

          <form class="quiz-form" @submit.prevent="submitQuiz">
            <article
              v-for="(question, index) in questions"
              :key="question.id"
              class="question-card"
            >
              <div class="question-title">
                <span>{{ index + 1 }}</span>

                <div>
                  <p>QUESTION {{ index + 1 }}</p>
                  <h2>{{ question.question_text }}</h2>
                </div>
              </div>

              <div class="option-list">
                <label
                  v-for="option in question.options"
                  :key="option.key"
                  class="option"
                  :class="{
                    selected: selectedAnswers[question.id] === option.key,
                  }"
                >
                  <input
                    v-model="selectedAnswers[question.id]"
                    :name="`question-${question.id}`"
                    type="radio"
                    :value="option.key"
                    :disabled="isBusy || generatedQuizUnavailable"
                  />

                  <span class="option-key">{{ option.key }}</span>
                  <span class="option-text">{{ option.text }}</span>
                  <span class="check-mark">✓</span>
                </label>
              </div>
            </article>

            <section class="submit-panel">
              <div>
                <p>Ready to check your understanding?</p>
                <small>
                  {{ answeredQuestionCount }} of {{ questions.length }}
                  questions answered
                </small>
              </div>

              <button type="submit" :disabled="!canSubmit || isSubmitting">
                {{ isSubmitting ? "Checking..." : "Submit quiz" }}
                <span>→</span>
              </button>
            </section>
          </form>
        </section>

        <section v-else key="result" class="result-section">
          <section class="result-hero">
            <div>
              <p class="hero-label">QUIZ RESULT · {{ scorePercentage }}%</p>
              <h1>{{ performanceFeedback.title }}</h1>
              <p>{{ performanceFeedback.description }}</p>
            </div>

            <div class="score-display">
              <strong>{{ quizResult.attempt.score }}</strong>
              <span>/ {{ quizResult.attempt.total_questions }}</span>
              <small>score</small>
            </div>
          </section>

          <section class="learning-feedback" :class="performanceFeedback.tone">
            <div class="feedback-icon">
              {{
                performanceFeedback.tone === "strong"
                  ? "★"
                  : performanceFeedback.tone === "developing"
                    ? "↗"
                    : "↺"
              }}
            </div>

            <div>
              <p class="feedback-label">YOUR LEARNING GUIDANCE</p>
              <h2>{{ performanceFeedback.action }}</h2>

              <p v-if="incorrectQuestionCount">
                {{ incorrectQuestionCount }} ta question-e revise dorkar. Nicher
                explanation-gula age dekho.
              </p>

              <p v-else>
                Shob answer correct. Ekhon confidence niye next topic-e jao.
              </p>
            </div>

            <div class="feedback-actions">
              <button
                type="button"
                class="try-again-button"
                :disabled="isBusy"
                @click="tryAgain"
              >
                {{ isGeneratedQuiz ? "Back to Quiz Practice" : "Try Again" }}
                <span aria-hidden="true">↺</span>
              </button>

              <RouterLink class="ask-link" to="/">Ask Maira →</RouterLink>
            </div>
          </section>

          <div class="result-heading">
            <div>
              <p class="eyebrow">ANSWER REVIEW</p>
              <h2>See each explanation</h2>
            </div>
          </div>

          <article
            v-for="result in quizResult.results"
            :key="result.question_id"
            class="result-card"
            :class="{
              correct: result.is_correct,
              incorrect: !result.is_correct,
            }"
          >
            <span class="result-status">
              {{ result.is_correct ? "✓ Correct" : "↗ Review this" }}
            </span>

            <h3>{{ result.question_text }}</h3>

            <p class="answer-text">
              Your answer:
              <strong>{{ result.selected_option }}</strong>
              <span>·</span>
              Correct answer:
              <strong>{{ result.correct_option }}</strong>
            </p>

            <p class="explanation">{{ result.explanation }}</p>
          </article>
        </section>
      </Transition>
    </template>

    <p v-if="errorMessage" class="error-message">
      {{ errorMessage }}
    </p>
  </section>
</template>

<style scoped>
.quiz-page {
  display: grid;
  gap: 1.4rem;
  min-width: 0;
}

.back-link,
.ask-link {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  width: fit-content;
  color: var(--accent-color);
  font-size: 0.9rem;
  font-weight: 800;
  text-decoration: none;
  transition:
    color 0.2s ease,
    transform 0.2s ease;
}

.back-link:hover {
  color: var(--accent-hover);
  transform: translateX(-3px);
}

.ask-link:hover {
  color: var(--accent-hover);
  transform: translateX(3px);
}

.quiz-hero,
.result-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 2rem;
  overflow: hidden;
  min-height: 190px;
  padding: 2rem;
  border: 1px solid #f3dd91;
  border-radius: 1.35rem;
  background:
    radial-gradient(
      circle at 88% 20%,
      rgb(255 255 255 / 54%),
      transparent 11rem
    ),
    linear-gradient(120deg, #f4d774, #f8e8ad 52%, #f4f7ff);
}

.quiz-hero > div:first-child,
.result-hero > div:first-child {
  max-width: 650px;
}

.hero-label,
.eyebrow,
.feedback-label {
  margin: 0;
  color: #7c5c00;
  font-size: 0.7rem;
  font-weight: 850;
  letter-spacing: 0.11em;
}

.quiz-hero h1,
.result-hero h1 {
  margin: 0.55rem 0;
  color: #172554;
  font-size: clamp(1.7rem, 3.5vw, 2.6rem);
  line-height: 1.12;
}

.quiz-hero p:not(.hero-label),
.result-hero p:not(.hero-label) {
  margin: 0;
  color: #475569;
  line-height: 1.65;
}

.question-progress,
.score-display {
  display: grid;
  width: 8rem;
  height: 8rem;
  flex: 0 0 auto;
  place-content: center;
  justify-items: center;
  border-radius: 2rem;
  background: #1d4ed8;
  box-shadow: 0 1rem 2rem rgb(30 64 175 / 25%);
  color: #ffffff;
  transform: rotate(7deg);
}

.question-progress strong,
.score-display strong {
  font-size: 2.3rem;
  line-height: 1;
}

.question-progress span,
.score-display span {
  margin-top: 0.15rem;
  color: #bfdbfe;
  font-weight: 800;
}

.question-progress small,
.score-display small {
  margin-top: 0.3rem;
  color: #facc15;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.quiz-attempt {
  display: grid;
  gap: 1rem;
}

.quiz-content-enter-active {
  transition: opacity 0.3s ease-out;
}

.quiz-content-leave-active {
  transition: opacity 0.2s ease-in;
}

.quiz-content-enter-from,
.quiz-content-leave-to {
  opacity: 0;
}
.quiz-form,
.result-section {
  display: grid;
  gap: 1rem;
}

.question-card,
.result-card,
.submit-panel,
.learning-feedback {
  border: 1px solid var(--border-color);
  border-radius: 1.1rem;
  padding: 1.3rem;
  background: var(--surface-color);
  box-shadow: 0 0.7rem 1.7rem rgb(15 23 42 / 6%);
}

.question-card {
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.question-card:hover {
  border-color: color-mix(
    in srgb,
    var(--accent-color) 55%,
    var(--border-color)
  );
  box-shadow: 0 0.9rem 1.8rem rgb(15 23 42 / 10%);
  transform: translateY(-2px);
}

.question-title {
  display: flex;
  align-items: flex-start;
  gap: 0.8rem;
  margin-bottom: 1.1rem;
}

.question-title > span {
  display: grid;
  width: 2.3rem;
  height: 2.3rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.75rem;
  background: var(--accent-color);
  color: #ffffff;
  font-size: 0.86rem;
  font-weight: 900;
}

.question-title p {
  margin: 0;
  color: var(--accent-color);
  font-size: 0.66rem;
  font-weight: 850;
  letter-spacing: 0.1em;
}

.question-title h2 {
  margin: 0.35rem 0 0;
  color: var(--text-primary);
  font-size: 1.05rem;
  line-height: 1.5;
}

.option-list {
  display: grid;
  gap: 0.7rem;
}

.option {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.8rem;
  padding: 0.8rem;
  background: var(--page-background);
  color: var(--text-primary);
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    background-color 0.18s ease,
    transform 0.18s ease,
    box-shadow 0.18s ease;
}

.option:hover {
  border-color: var(--accent-color);
  transform: translateX(3px);
}

.option.selected {
  border-color: var(--accent-color);
  background: var(--nav-hover);
  box-shadow: 0 0 0 3px rgb(29 78 216 / 10%);
}

.option input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
}

.option-key {
  display: grid;
  width: 2rem;
  height: 2rem;
  place-items: center;
  border: 1px solid var(--border-color);
  border-radius: 50%;
  background: var(--surface-color);
  color: var(--text-secondary);
  font-size: 0.82rem;
  font-weight: 900;
}

.option.selected .option-key {
  border-color: var(--accent-color);
  background: var(--accent-color);
  color: #ffffff;
}

.option-text {
  line-height: 1.5;
}

.check-mark {
  opacity: 0;
  color: var(--accent-color);
  font-size: 1.1rem;
  font-weight: 900;
  transform: scale(0.7);
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.option.selected .check-mark {
  opacity: 1;
  transform: scale(1);
}

.submit-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  border-color: #d5e0ff;
  background: linear-gradient(135deg, var(--nav-hover), var(--surface-color));
}

.submit-panel p {
  margin: 0;
  color: var(--text-primary);
  font-weight: 800;
}

.submit-panel small {
  display: block;
  margin-top: 0.35rem;
  color: var(--text-secondary);
}

.submit-panel button,
.try-again-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.55rem;
  border: 0;
  border-radius: 0.7rem;
  padding: 0.8rem 1rem;
  background: var(--accent-color);
  color: #ffffff;
  cursor: pointer;
  font: inherit;
  font-size: 0.88rem;
  font-weight: 850;
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease,
    opacity 0.2s ease;
}

.submit-panel button {
  flex: 0 0 auto;
}

.submit-panel button:hover:not(:disabled),
.try-again-button:hover {
  background: var(--accent-hover);
  box-shadow: 0 0.7rem 1.2rem rgb(30 64 175 / 22%);
  transform: translateY(-2px);
}

.submit-panel button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.learning-feedback {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 1rem;
  border-left-width: 5px;
}

.learning-feedback h2 {
  margin: 0.35rem 0;
  color: var(--text-primary);
  font-size: 1rem;
  line-height: 1.5;
}

.learning-feedback p:not(.feedback-label) {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.88rem;
  line-height: 1.55;
}

.feedback-icon {
  display: grid;
  width: 2.8rem;
  height: 2.8rem;
  place-items: center;
  border-radius: 0.85rem;
  font-size: 1.2rem;
  font-weight: 900;
}

.learning-feedback.strong {
  border-left-color: #16a34a;
  background: color-mix(in srgb, #22c55e 9%, var(--surface-color));
}

.learning-feedback.strong .feedback-icon {
  background: rgb(34 197 94 / 17%);
  color: #15803d;
}

.learning-feedback.developing {
  border-left-color: #d97706;
  background: color-mix(in srgb, #f59e0b 10%, var(--surface-color));
}

.learning-feedback.developing .feedback-icon {
  background: rgb(245 158 11 / 17%);
  color: #b45309;
}

.learning-feedback.needs-practice {
  border-left-color: #dc2626;
  background: color-mix(in srgb, #ef4444 8%, var(--surface-color));
}

.learning-feedback.needs-practice .feedback-icon {
  background: rgb(239 68 68 / 15%);
  color: #b91c1c;
}

.feedback-actions {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.result-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 0.5rem;
}

.result-heading h2 {
  margin: 0.4rem 0 0;
  color: var(--text-primary);
  font-size: 1.35rem;
}

.result-card {
  border-left-width: 5px;
  animation: result-enter 0.35s ease-out both;
}

.result-card.correct {
  border-left-color: #16a34a;
  background: color-mix(in srgb, #22c55e 7%, var(--surface-color));
}

.result-card.incorrect {
  border-left-color: #dc2626;
  background: color-mix(in srgb, #ef4444 7%, var(--surface-color));
}

.result-status {
  display: inline-flex;
  align-items: center;
  border-radius: 99rem;
  padding: 0.32rem 0.6rem;
  font-size: 0.72rem;
  font-weight: 850;
}

.correct .result-status {
  background: rgb(34 197 94 / 15%);
  color: #15803d;
}

.incorrect .result-status {
  background: rgb(220 38 38 / 14%);
  color: #b91c1c;
}

.result-card h3 {
  margin: 0.75rem 0;
  color: var(--text-primary);
  font-size: 1rem;
  line-height: 1.55;
}

.answer-text,
.explanation {
  color: var(--text-secondary);
  line-height: 1.65;
}

.answer-text {
  margin: 0;
}

.answer-text strong {
  color: var(--text-primary);
}

.answer-text span {
  margin: 0 0.2rem;
}

.explanation {
  margin: 0.65rem 0 0;
}

.loading-message,
.error-message {
  margin: 0;
  font-size: 0.9rem;
}

.loading-message {
  color: var(--text-secondary);
}

.error-message {
  border-radius: 0.7rem;
  padding: 0.8rem;
  background: rgb(220 38 38 / 10%);
  color: #dc2626;
}

@keyframes result-enter {
  from {
    opacity: 0;
    transform: translateY(10px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

:global(.dark-theme) .quiz-hero,
:global(.dark-theme) .result-hero {
  border-color: #715d1f;
  background:
    radial-gradient(
      circle at 88% 20%,
      rgb(255 255 255 / 8%),
      transparent 11rem
    ),
    linear-gradient(120deg, #5d4d18, #352f22 55%, #132442);
}

:global(.dark-theme) .quiz-hero h1,
:global(.dark-theme) .result-hero h1 {
  color: #ffffff;
}

:global(.dark-theme) .quiz-hero p:not(.hero-label),
:global(.dark-theme) .result-hero p:not(.hero-label) {
  color: #e2e8f0;
}

:global(.dark-theme) .correct .result-status,
:global(.dark-theme) .learning-feedback.strong .feedback-icon {
  color: #86efac;
}

:global(.dark-theme) .incorrect .result-status,
:global(.dark-theme) .learning-feedback.needs-practice .feedback-icon {
  color: #fca5a5;
}

@media (max-width: 780px) {
  .learning-feedback {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .feedback-actions {
    grid-column: 1 / -1;
    justify-content: flex-start;
  }
}

@media (max-width: 680px) {
  .quiz-hero,
  .result-hero,
  .submit-panel,
  .result-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .question-progress,
  .score-display {
    align-self: flex-end;
  }

  .submit-panel button {
    width: 100%;
    justify-content: center;
  }
}

@media (max-width: 480px) {
  .quiz-hero,
  .result-hero,
  .question-card,
  .result-card,
  .submit-panel,
  .learning-feedback {
    padding: 1.1rem;
  }

  .option {
    align-items: start;
  }

  .learning-feedback {
    grid-template-columns: 1fr;
  }

  .feedback-actions {
    grid-column: auto;
    width: 100%;
  }

  .try-again-button {
    width: 100%;
  }
}
.quiz-mode-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 1rem;
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  padding: 1.15rem;
  background: var(--surface-color);
}

.quiz-mode-description {
  flex: 1 1 16rem;
  min-width: 0;
}

.quiz-mode-label {
  margin: 0 0 0.45rem;
  color: var(--accent-color);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.quiz-mode-description > p:not(.quiz-mode-label) {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.9rem;
  line-height: 1.6;
}

.quiz-mode-description small {
  display: block;
  margin-top: 0.5rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

.quiz-mode-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}

.generate-quiz-button,
.standard-quiz-button {
  border: 1px solid var(--border-color);
  border-radius: 0.7rem;
  padding: 0.8rem 1rem;
  font: inherit;
  font-size: 0.85rem;
  font-weight: 700;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    color 0.2s ease;
}

.generate-quiz-button {
  border-color: transparent;
  background: var(--accent-color);
  color: #ffffff;
}

.generate-quiz-button:hover:not(:disabled) {
  background: var(--accent-hover);
}

.standard-quiz-button {
  background: var(--surface-color);
  color: var(--text-primary);
}

.standard-quiz-button:hover:not(:disabled) {
  background: var(--nav-hover);
}

.generate-quiz-button:disabled,
.standard-quiz-button:disabled,
.try-again-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
  transform: none;
}

.generate-quiz-button:focus-visible,
.standard-quiz-button:focus-visible {
  outline: 3px solid var(--accent-color);
  outline-offset: 3px;
}

.generation-message {
  flex-basis: 100%;
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.85rem;
  line-height: 1.6;
}
.learning-mode-control {
  display: grid;
  gap: 0.45rem;
  flex: 1 1 14rem;
  min-width: 0;
}

.learning-mode-control label {
  color: var(--text-primary);
  font-size: 0.85rem;
  font-weight: 700;
}

.learning-mode-control select {
  width: 100%;
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 0.7rem;
  padding: 0.75rem;
  background: var(--surface-color);
  color: var(--text-primary);
  font: inherit;
}

.learning-mode-control select:focus-visible {
  outline: 3px solid var(--accent-color);
  outline-offset: 3px;
}

.learning-mode-control select:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.learning-mode-control small {
  color: var(--text-secondary);
  line-height: 1.5;
}
/* Link gula button-er shape pabe */
.quiz-page .back-link,
.quiz-page .ask-link {
  padding: 0.8rem 1rem;
  border-radius: 0.7rem;
  color: #fff;
}

/* Back to Quiz Practice — blue */
.quiz-page .back-link,
.quiz-page .try-again-button {
  background: #2450db;
  color: #fff;
}

.quiz-page .back-link:hover,
.quiz-page .try-again-button:hover:not(:disabled) {
  background: #1d3fb8;
  color: #fff;
}

/* Choose another quiz — green */
.quiz-mode-actions .back-link {
  background: #15803d;
  color: #fff;
}

.quiz-mode-actions .back-link:hover {
  background: #166534;
  color: #fff;
}

/* Ask Maira — maroon */
.quiz-page .ask-link {
  background: #800000;
  color: #fff;
}

.quiz-page .ask-link:hover {
  background: #650000;
  color: #fff;
}
</style>
