<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useStore } from "vuex";

const router = useRouter();
const route = useRoute();
const store = useStore();
const API_BASE = "http://127.0.0.1:5000";

const academicLevel = computed(
  () => store.state.auth.currentUser?.academic_level,
);

const studyLevelLabel = computed(() =>
  ["ssc", "hsc"].includes(academicLevel.value)
    ? academicLevel.value.toUpperCase()
    : "",
);

const searchText = ref("");
const topics = ref([]);
const selectedTopic = ref(null);
const currentPage = ref(0);
const hasMore = ref(false);

const isLoading = ref(false);
const isGenerating = ref(false);
const errorMessage = ref("");

const responseLanguage = ref("banglish");
const learningMode = ref("personal_growth");

let loadedSearch = "";

function isCurrentRequest(token) {
  return store.state.auth.accessToken === token;
}

async function apiRequest(path, token, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
      Authorization: `Bearer ${token}`,
    },
  });

  if (!isCurrentRequest(token)) {
    return null;
  }

  if (response.status === 401) {
    store.commit("auth/CLEAR_AUTH");
    await router.replace("/login");
    return null;
  }

  const data = await response.json().catch(() => null);

  if (!isCurrentRequest(token)) {
    return null;
  }

  if (!response.ok) {
    throw new Error(data?.error || data?.msg || "Request failed. Try again.");
  }

  if (!data || typeof data !== "object") {
    throw new Error("Server returned an invalid response.");
  }

  return data;
}

function isTopicAvailable(topic) {
  return (
    topic.subject === "ict" &&
    topic.academic_level === academicLevel.value &&
    (topic.slug === "number-systems" ||
      (academicLevel.value === "ssc" && topic.slug.startsWith("ssc-ict-")))
  );
}

async function searchTopics(loadMore = false) {
  if (isLoading.value || isGenerating.value) {
    return;
  }

  if (loadMore && !hasMore.value) {
    return;
  }

  const token = store.state.auth.accessToken;

  if (!token) {
    await router.replace("/login");
    return;
  }

  const query = searchText.value.trim();
  const append = loadMore && query === loadedSearch;
  const page = append ? currentPage.value + 1 : 1;

  isLoading.value = true;
  errorMessage.value = "";

  if (!append) {
    topics.value = [];
    hasMore.value = false;
  }

  try {
    const params = new URLSearchParams({
      q: query,
      page: String(page),
    });

    const data = await apiRequest(`/api/topics/search?${params}`, token);

    if (!data) {
      return;
    }

    if (!Array.isArray(data.topics) || !data.pagination) {
      throw new Error("Server returned invalid topics.");
    }

    const combined = append ? [...topics.value, ...data.topics] : data.topics;

    topics.value = [
      ...new Map(combined.map((topic) => [topic.id, topic])).values(),
    ];

    currentPage.value = data.pagination.page;
    hasMore.value = Boolean(data.pagination.has_more);
    loadedSearch = query;
  } catch (error) {
    if (isCurrentRequest(token)) {
      errorMessage.value =
        error instanceof Error ? error.message : "Could not load topics.";
    }
  } finally {
    isLoading.value = false;
  }
}

function selectTopic(topic) {
  if (isGenerating.value || !isTopicAvailable(topic)) {
    return;
  }

  selectedTopic.value = topic;
  errorMessage.value = "";
}

async function generateQuiz() {
  if (!selectedTopic.value || isGenerating.value || isLoading.value) {
    return;
  }

  const token = store.state.auth.accessToken;

  if (!token) {
    await router.replace("/login");
    return;
  }

  const topic = selectedTopic.value;

  isGenerating.value = true;
  errorMessage.value = "";

  try {
    const data = await apiRequest("/api/generated-quizzes", token, {
      method: "POST",
      body: JSON.stringify({
        topic_slug: topic.slug,
        response_language: responseLanguage.value,
        learning_mode: learningMode.value,
      }),
    });

    if (!data) {
      return;
    }

    if (
      typeof data.quiz?.id !== "string" ||
      data.quiz.topic?.slug !== topic.slug ||
      !Array.isArray(data.quiz.questions) ||
      data.quiz.questions.length !== 5
    ) {
      throw new Error("Server returned an incomplete quiz.");
    }

    await router.push({
      name: "quiz",
      params: {
        slug: topic.slug,
      },
      query: {
        generated_quiz_id: data.quiz.id,
      },
    });
  } catch (error) {
    if (isCurrentRequest(token)) {
      errorMessage.value =
        error instanceof Error
          ? error.message
          : "Could not generate your quiz. Try again.";
    }
  } finally {
    isGenerating.value = false;
  }
}

onMounted(async () => {
  const token = store.state.auth.accessToken;

  if (!token) {
    await router.replace("/login");
    return;
  }

  try {
    const data = await apiRequest("/api/auth/me", token);

    if (!data) {
      return;
    }

    if (!data.user || data.user.role !== "student") {
      throw new Error("Could not load your student profile.");
    }

    store.commit("auth/SET_AUTH", {
      token,
      user: data.user,
    });

    if (!["ssc", "hsc"].includes(data.user.academic_level)) {
      await router.replace("/");
      return;
    }

    const requestedSlug = route.query.topic_slug;

    if (requestedSlug !== undefined) {
      if (
        typeof requestedSlug !== "string" ||
        !requestedSlug.trim() ||
        requestedSlug.length > 100
      ) {
        throw new Error("Invalid practice topic link.");
      }

      const topicData = await apiRequest("/api/topics", token);

      if (!topicData) return;

      if (!Array.isArray(topicData.topics)) {
        throw new Error("Could not load the requested topic.");
      }

      const requestedTopic = topicData.topics.find(
        (topic) => topic.slug === requestedSlug,
      );

      if (!requestedTopic || !isTopicAvailable(requestedTopic)) {
        throw new Error(
          "This topic is not available for quiz practice at your study level.",
        );
      }

      searchText.value = requestedTopic.title;
      await searchTopics();

      if (!isCurrentRequest(token)) return;

      selectTopic(requestedTopic);
    } else {
      await searchTopics();
    }
  } catch (error) {
    if (isCurrentRequest(token)) {
      errorMessage.value =
        error instanceof Error
          ? error.message
          : "Could not load quiz practice.";
    }
  }
});
</script>

<template>
  <section class="practice-page">
    <header class="page-header">
      <p class="eyebrow">
        QUIZ PRACTICE
        <template v-if="studyLevelLabel"> · {{ studyLevelLabel }} </template>
      </p>

      <h1>Choose a topic to practise</h1>

      <p class="intro">
        ICT topic search kore select koro. Tarpor 5ta question answer diye tomar
        understanding check koro.
      </p>
    </header>

    <div class="practice-layout">
      <section
        class="topics-panel"
        aria-labelledby="topics-heading"
        :aria-busy="isLoading"
      >
        <h2 id="topics-heading">Find a topic</h2>

        <form class="search-form" @submit.prevent="searchTopics()">
          <label for="practice-search"> Search by topic name </label>

          <div class="search-row">
            <input
              id="practice-search"
              v-model="searchText"
              type="search"
              maxlength="100"
              placeholder="Example: Save or binary"
              :disabled="isLoading || isGenerating"
            />

            <button
              type="submit"
              class="secondary-button"
              :disabled="isLoading || isGenerating"
            >
              {{ isLoading ? "Searching..." : "Search" }}
            </button>
          </div>
        </form>

        <p v-if="isLoading" class="status-message" role="status">
          Loading topics...
        </p>

        <p v-else-if="!topics.length && !errorMessage" class="status-message">
          No matching topics. Try another word.
        </p>

        <div class="topic-list">
          <button
            v-for="topic in topics"
            :key="topic.id"
            type="button"
            class="topic-button"
            :class="{
              selected: selectedTopic?.id === topic.id,
            }"
            :aria-pressed="selectedTopic?.id === topic.id"
            :disabled="isGenerating || !isTopicAvailable(topic)"
            @click="selectTopic(topic)"
          >
            <span>{{ topic.title }}</span>

            <small v-if="!isTopicAvailable(topic)">
              Quiz not available yet
            </small>

            <small v-else-if="selectedTopic?.id === topic.id"> Selected </small>
          </button>
        </div>

        <button
          v-if="hasMore"
          type="button"
          class="secondary-button load-more"
          :disabled="isLoading || isGenerating"
          @click="searchTopics(true)"
        >
          Load more topics
        </button>
      </section>

      <section
        class="quiz-panel"
        aria-labelledby="quiz-settings-heading"
        :aria-busy="isGenerating"
      >
        <p class="eyebrow">YOUR PRACTICE</p>
        <h2 id="quiz-settings-heading">Quiz settings</h2>

        <div class="selected-topic">
          <span>Selected topic</span>

          <strong>
            {{
              selectedTopic
                ? selectedTopic.title
                : "Choose a topic from the list"
            }}
          </strong>
        </div>

        <div class="settings">
          <label for="practice-language">Quiz language</label>

          <select
            id="practice-language"
            v-model="responseLanguage"
            :disabled="isGenerating"
          >
            <option value="banglish">Banglish</option>
            <option value="english">English</option>
          </select>

          <label for="practice-mode">Learning mode</label>

          <select
            id="practice-mode"
            v-model="learningMode"
            :disabled="isGenerating"
          >
            <option value="personal_growth">Personal Growth</option>

            <option value="exam_preparation">Exam Preparation</option>
          </select>
        </div>

        <p v-if="errorMessage" class="error-message" role="alert">
          {{ errorMessage }}
        </p>

        <button
          type="button"
          class="generate-button"
          :disabled="!selectedTopic || isGenerating || isLoading"
          @click="generateQuiz"
        >
          {{ isGenerating ? "Generating quiz..." : "Generate quiz" }}
        </button>

        <p v-if="isGenerating" class="status-message" role="status">
          Quiz ready hote kichu shomoy lagte pare.
        </p>

        <p v-else class="practice-note">
          Quiz selected topic-er upor hobe. Submit korar por score ar
          explanation dekhte parbe.
        </p>
      </section>
    </div>
  </section>
</template>

<style scoped>
.practice-page {
  display: grid;
  gap: 1.5rem;
  min-width: 0;
}

.eyebrow {
  margin: 0;
  color: var(--accent-color);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.08em;
}

h1,
h2 {
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

h1 {
  margin: 0.65rem 0 0;
  font-size: clamp(1.75rem, 4vw, 2.5rem);
  line-height: 1.2;
}

h2 {
  margin: 0;
  font-size: 1.15rem;
}

.intro,
.status-message,
.practice-note {
  color: var(--text-secondary);
  line-height: 1.65;
}

.intro {
  max-width: 42rem;
  margin: 0.85rem 0 0;
}

.practice-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(280px, 1fr);
  align-items: start;
  gap: 1.25rem;
}

.topics-panel,
.quiz-panel {
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  padding: 1.5rem;
  background: var(--surface-color);
}

.quiz-panel h2 {
  margin-top: 0.5rem;
}

.search-form,
.settings {
  display: grid;
  gap: 0.6rem;
  margin-top: 1.25rem;
}

label {
  color: var(--text-primary);
  font-size: 0.85rem;
  font-weight: 700;
}

.search-row {
  display: flex;
  gap: 0.65rem;
}

input,
select {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid var(--border-color);
  border-radius: 0.7rem;
  padding: 0.8rem;
  background: var(--page-background);
  color: var(--text-primary);
  font: inherit;
}

input:focus-visible,
select:focus-visible,
button:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

.secondary-button,
.generate-button {
  border: 1px solid var(--border-color);
  border-radius: 0.7rem;
  padding: 0.8rem 1rem;
  cursor: pointer;
  font: inherit;
  font-weight: 700;
  transition:
    background-color 0.2s ease,
    transform 0.2s ease;
}

.secondary-button {
  flex: 0 0 auto;
  background: var(--page-background);
  color: var(--accent-color);
}

.secondary-button:hover:not(:disabled) {
  background: var(--nav-hover);
}

.topic-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.7rem;
  margin-top: 1.25rem;
}

.topic-button {
  display: grid;
  align-content: start;
  gap: 0.45rem;
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 0.8rem;
  padding: 1rem;
  background: var(--page-background);
  color: var(--text-primary);
  cursor: pointer;
  font: inherit;
  text-align: left;
  overflow-wrap: anywhere;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    transform 0.2s ease;
}

.topic-button:hover:not(:disabled),
.topic-button.selected {
  border-color: var(--accent-color);
  background: var(--nav-hover);
}

.topic-button:hover:not(:disabled) {
  transform: translateY(-2px);
}

.topic-button small {
  color: var(--text-secondary);
  font-size: 0.75rem;
}

.topic-button.selected small {
  color: var(--accent-color);
  font-weight: 700;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.load-more {
  margin-top: 1rem;
}

.selected-topic {
  display: grid;
  gap: 0.5rem;
  margin-top: 1.25rem;
  border: 1px solid var(--border-color);
  border-radius: 0.8rem;
  padding: 1rem;
  background: var(--page-background);
}

.selected-topic span {
  color: var(--text-secondary);
  font-size: 0.8rem;
}

.selected-topic strong {
  color: var(--text-primary);
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.settings label:not(:first-child) {
  margin-top: 0.45rem;
}

.generate-button {
  width: 100%;
  margin-top: 1.25rem;
  border-color: var(--accent-color);
  background: var(--accent-color);
  color: var(--surface-color);
}

.generate-button:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-1px);
}

.status-message,
.practice-note {
  margin: 1rem 0 0;
  font-size: 0.85rem;
}

.error-message {
  margin: 1rem 0 0;
  color: #dc2626;
  font-size: 0.85rem;
  line-height: 1.6;
}

@media (max-width: 900px) {
  .practice-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 540px) {
  .topics-panel,
  .quiz-panel {
    padding: 1rem;
  }

  .topic-list {
    grid-template-columns: 1fr;
  }

  .search-row {
    flex-direction: column;
  }
}

.topic-button {
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.generate-button {
  color: #fff;
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.topic-button:hover:not(:disabled),
.generate-button:hover:not(:disabled) {
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.topic-button:active:not(:disabled),
.generate-button:active:not(:disabled) {
  transform: scale(0.98);
}
.search-row .secondary-button {
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.search-row .secondary-button:hover:not(:disabled) {
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.search-row .secondary-button:active:not(:disabled) {
  transform: scale(0.98);
}
.secondary-button.load-more {
  border-color: #2450db;
  background: #2450db;
  color: #fff;
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.secondary-button.load-more:hover:not(:disabled) {
  border-color: #1d3fb8;
  background: #1d3fb8;
  color: #fff;
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.secondary-button.load-more:active:not(:disabled) {
  transform: scale(0.98);
}
</style>
