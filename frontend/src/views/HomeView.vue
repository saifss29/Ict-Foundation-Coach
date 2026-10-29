<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { useStore } from "vuex";

const router = useRouter();
const store = useStore();
const API_BASE = "http://127.0.0.1:5000";

const currentUser = computed(() => store.state.auth.currentUser);
const academicLevel = computed(() => currentUser.value?.academic_level);

const hasAcademicLevel = computed(() =>
  ["ssc", "hsc"].includes(academicLevel.value),
);

const studyLevelLabel = computed(() =>
  hasAcademicLevel.value ? academicLevel.value.toUpperCase() : "",
);

const selectedAcademicLevel = ref("");
const isSavingLevel = ref(false);
const levelError = ref("");

const topics = ref([]);
const isTopicsLoading = ref(true);
const isLoading = ref(false);
const errorMessage = ref("");

const conversations = ref([]);
const isHistoryLoading = ref(false);
const isConversationLoading = ref(false);
const historyError = ref("");
const historyPage = ref(0);
const historyHasNext = ref(false);

const savedResponseLanguage = localStorage.getItem(
  "ict-coach-response-language",
);

const responseLanguage = ref(
  ["banglish", "english"].includes(savedResponseLanguage)
    ? savedResponseLanguage
    : "banglish",
);

const selectedTopic = computed({
  get: () => store.state.tutor.selectedTopic,
  set: (value) => store.commit("tutor/SET_SELECTED_TOPIC", value),
});

const message = computed({
  get: () => store.state.tutor.draftMessage,
  set: (value) => store.commit("tutor/SET_DRAFT_MESSAGE", value),
});

const sessionId = computed({
  get: () => store.state.tutor.sessionId,
  set: (value) => store.commit("tutor/SET_SESSION_ID", value),
});

const messages = computed(() => store.state.tutor.messages);

const learningMode = computed({
  get: () => store.state.tutor.learningMode,
  set: (value) => store.commit("tutor/SET_LEARNING_MODE", value),
});

const selectedTopicData = computed(() =>
  topics.value.find((topic) => topic.title === selectedTopic.value),
);

const subjectTopics = computed(() =>
  topics.value.filter(
    (topic) =>
      topic.subject === "ict" &&
      topic.academic_level === academicLevel.value &&
      topic.slug === `${academicLevel.value}-ict`,
  ),
);

// Quiz selection is separate from the tutor conversation.
const quizSearch = ref("");
const quizTopics = ref([]);
const quizPage = ref(0);
const quizHasMore = ref(false);
const isQuizSearchLoading = ref(false);
const isGeneratingQuiz = ref(false);
const quizError = ref("");
const selectedQuizTopic = ref(null);
const quizLanguage = ref(responseLanguage.value);
const quizMode = ref("personal_growth");

let loadedQuizSearch = "";

function getLearningModeLabel(mode) {
  return mode === "exam_preparation" ? "Exam Preparation" : "Personal Growth";
}

function setLearningMode(mode) {
  if (
    isLoading.value ||
    !["exam_preparation", "personal_growth"].includes(mode) ||
    learningMode.value === mode
  ) {
    return;
  }

  learningMode.value = mode;
  startNewChat();
}

function getWelcomeMessage(language, topicTitle = "") {
  if (!topicTitle) {
    return language === "banglish"
      ? "Hi! Age ekta learning topic select koro, tarpor tomar ICT question koro."
      : "Hi! Select a learning topic first, then ask your ICT question.";
  }

  return language === "banglish"
    ? `"${topicTitle}" topic select kora hoise. Ekhon ei topic niye tomar question koro.`
    : `"${topicTitle}" is selected. You can now ask a question about this topic.`;
}

function setWelcomeMessage() {
  store.commit("tutor/SET_MESSAGES", [
    {
      id: "welcome",
      role: "assistant",
      text: getWelcomeMessage(responseLanguage.value, selectedTopic.value),
    },
  ]);
}

function initializeConversation() {
  const userId = currentUser.value?.id ?? null;

  if (store.state.tutor.ownerId !== userId) {
    store.commit("tutor/RESET_STATE", userId);
  }

  if (messages.value.length === 0) {
    setWelcomeMessage();
  }
}

function startNewChat() {
  if (isLoading.value) {
    return;
  }

  sessionId.value = null;
  message.value = "";
  errorMessage.value = "";
  setWelcomeMessage();
}

function selectTopic(topicTitle) {
  if (isLoading.value || selectedTopic.value === topicTitle) {
    return;
  }

  selectedTopic.value = topicTitle;
  startNewChat();
}

function setResponseLanguage(language) {
  if (
    isLoading.value ||
    !["banglish", "english"].includes(language) ||
    responseLanguage.value === language
  ) {
    return;
  }

  responseLanguage.value = language;

  localStorage.setItem("ict-coach-response-language", language);

  startNewChat();
}

function escapeHtml(value) {
  const replacements = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  };

  return String(value ?? "").replace(
    /[&<>"']/g,
    (character) => replacements[character],
  );
}

function formatAssistantText(text) {
  return escapeHtml(text)
    .split("\n")
    .map((line) => {
      if (/^\s*---+\s*$/.test(line)) {
        return "<hr>";
      }

      const inlineText = line
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/`([^`]+)`/g, "<code>$1</code>");

      const heading = inlineText.match(/^#{1,3}\s+(.+)$/);

      if (heading) {
        return `<h3>${heading[1]}</h3>`;
      }

      const listItem = inlineText.match(/^\s*[-*•]\s+(.+)$/);

      if (listItem) {
        return `<p class="markdown-list-item">• ${listItem[1]}</p>`;
      }

      if (!inlineText.trim()) {
        return '<div class="markdown-spacer"></div>';
      }

      return `<p>${inlineText}</p>`;
    })
    .join("");
}

function clearAuthAndRedirect() {
  store.commit("auth/CLEAR_AUTH");
  router.replace("/login");
}

function getErrorText(error, fallback) {
  return error instanceof Error ? error.message : fallback;
}

function isCurrentRequest(accessToken) {
  return store.state.auth.accessToken === accessToken;
}

async function apiRequest(path, accessToken, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!isCurrentRequest(accessToken)) {
    return null;
  }

  if (response.status === 401) {
    clearAuthAndRedirect();
    return null;
  }

  const data = await response.json().catch(() => null);

  if (!isCurrentRequest(accessToken)) {
    return null;
  }

  if (!response.ok) {
    throw new Error(
      data?.error || data?.msg || "Request failed. Please try again.",
    );
  }

  if (!data || typeof data !== "object") {
    throw new Error("Server returned an invalid response.");
  }

  return data;
}

async function loadTopics() {
  const accessToken = store.state.auth.accessToken;

  if (!accessToken) {
    router.replace("/login");
    isTopicsLoading.value = false;
    return;
  }

  try {
    const data = await apiRequest("/api/topics", accessToken);

    if (!data) {
      return;
    }

    if (!Array.isArray(data.topics)) {
      throw new Error("Server returned invalid learning topics.");
    }

    topics.value = data.topics;

    const selectedStillAvailable = topics.value.some(
      (topic) => topic.title === selectedTopic.value,
    );

    const selectedIsSubject = subjectTopics.value.some(
      (topic) => topic.title === selectedTopic.value,
    );

    // Preserve saved legacy chats; use ICT for new chats.
    if (!selectedStillAvailable || (!sessionId.value && !selectedIsSubject)) {
      selectedTopic.value = subjectTopics.value[0]?.title || "";

      startNewChat();
    }
  } catch (error) {
    if (isCurrentRequest(accessToken)) {
      errorMessage.value = getErrorText(
        error,
        "Could not load learning topics.",
      );
    }
  } finally {
    isTopicsLoading.value = false;
  }
}

async function loadHistory(loadMore = false) {
  const accessToken = store.state.auth.accessToken;

  if (!accessToken || isHistoryLoading.value) {
    return;
  }

  if (loadMore && !historyHasNext.value) {
    return;
  }

  isHistoryLoading.value = true;
  historyError.value = "";

  const nextPage = loadMore ? historyPage.value + 1 : 1;

  try {
    const data = await apiRequest(
      `/api/chat/conversations?page=${nextPage}`,
      accessToken,
    );

    if (!data) {
      return;
    }

    if (!Array.isArray(data.conversations) || !data.pagination) {
      throw new Error("Server returned invalid history data.");
    }

    const combined = loadMore
      ? [...conversations.value, ...data.conversations]
      : data.conversations;

    conversations.value = [
      ...new Map(
        combined.map((conversation) => [conversation.id, conversation]),
      ).values(),
    ];

    historyPage.value = nextPage;
    historyHasNext.value = data.pagination.has_next;
  } catch (error) {
    if (isCurrentRequest(accessToken)) {
      historyError.value = getErrorText(error, "Could not load chat history.");
    }
  } finally {
    isHistoryLoading.value = false;
  }
}

async function openConversation(conversationId) {
  const accessToken = store.state.auth.accessToken;

  if (!accessToken || isLoading.value || isTopicsLoading.value) {
    return;
  }

  isLoading.value = true;
  isConversationLoading.value = true;
  historyError.value = "";

  try {
    let page = 1;
    let hasNext = true;
    let conversation = null;
    const loadedMessages = [];

    while (hasNext) {
      const data = await apiRequest(
        `/api/chat/conversations/${encodeURIComponent(conversationId)}?page=${page}`,
        accessToken,
      );

      if (!data) {
        return;
      }

      if (
        !data.conversation ||
        !Array.isArray(data.messages) ||
        !data.pagination
      ) {
        throw new Error("Server returned invalid conversation data.");
      }

      conversation = data.conversation;
      loadedMessages.push(...data.messages);

      hasNext = data.pagination.has_next;
      page += 1;
    }

    if (!conversation || !isCurrentRequest(accessToken)) {
      return;
    }

    if (!["banglish", "english"].includes(conversation.response_language)) {
      throw new Error("Conversation has an unsupported language.");
    }

    if (
      !["exam_preparation", "personal_growth"].includes(
        conversation.learning_mode,
      )
    ) {
      throw new Error("Conversation has an unsupported learning mode.");
    }

    const conversationTopic = topics.value.find(
      (topic) => topic.title === conversation.topic,
    );

    selectedTopic.value = conversation.topic;
    responseLanguage.value = conversation.response_language;
    learningMode.value = conversation.learning_mode;
    sessionId.value = conversation.id;
    message.value = "";
    errorMessage.value = "";

    localStorage.setItem(
      "ict-coach-response-language",
      conversation.response_language,
    );

    store.commit(
      "tutor/SET_MESSAGES",
      loadedMessages.map((chatMessage) => ({
        ...chatMessage,
        id: `saved-${chatMessage.id}`,
        topicTitle:
          chatMessage.role === "assistant" ? conversation.topic : undefined,
        topicSlug:
          chatMessage.role === "assistant"
            ? conversationTopic?.slug
            : undefined,
      })),
    );
  } catch (error) {
    if (isCurrentRequest(accessToken)) {
      historyError.value = getErrorText(
        error,
        "Could not open this conversation.",
      );
    }
  } finally {
    isConversationLoading.value = false;
    isLoading.value = false;
  }
}

function formatHistoryDate(value) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return date.toLocaleDateString([], {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

async function sendMessage() {
  const studentMessage = message.value.trim();
  const accessToken = store.state.auth.accessToken;
  const questionTopic = selectedTopicData.value;

  if (!accessToken) {
    router.replace("/login");
    return;
  }

  if (
    !studentMessage ||
    !questionTopic ||
    isLoading.value ||
    isTopicsLoading.value
  ) {
    return;
  }

  const questionTopicTitle = questionTopic.title;
  const questionTopicSlug = questionTopic.slug;
  const questionLanguage = responseLanguage.value;
  const questionLearningMode = learningMode.value;
  const requestSessionId = sessionId.value;
  const studentMessageId = `student-${crypto.randomUUID()}`;

  store.commit("tutor/ADD_MESSAGE", {
    id: studentMessageId,
    role: "student",
    text: studentMessage,
  });

  message.value = "";
  errorMessage.value = "";
  isLoading.value = true;

  try {
    const data = await apiRequest("/api/chat", accessToken, {
      method: "POST",
      body: JSON.stringify({
        message: studentMessage,
        topic: questionTopicTitle,
        topic_slug: questionTopicSlug,
        session_id: requestSessionId,
        response_language: questionLanguage,
        learning_mode: questionLearningMode,
      }),
    });

    if (!data) {
      return;
    }

    if (
      typeof data.answer !== "string" ||
      !data.answer.trim() ||
      typeof data.session_id !== "string"
    ) {
      throw new Error("Tutor returned an incomplete answer.");
    }

    sessionId.value = data.session_id;

    store.commit("tutor/ADD_MESSAGE", {
      id: `assistant-${crypto.randomUUID()}`,
      role: "assistant",
      text: data.answer,
      topicTitle: questionTopicTitle,
      topicSlug: questionTopicSlug,
    });

    await loadHistory();
  } catch (error) {
    if (isCurrentRequest(accessToken)) {
      store.commit(
        "tutor/SET_MESSAGES",
        messages.value.filter(
          (chatMessage) => chatMessage.id !== studentMessageId,
        ),
      );

      message.value = studentMessage;

      errorMessage.value = getErrorText(error, "Chat request failed.");
    }
  } finally {
    isLoading.value = false;
  }
}

async function loadLearningContent() {
  initializeConversation();
  await loadTopics();

  if (store.getters["auth/isAuthenticated"] && hasAcademicLevel.value) {
    await loadHistory();
  }
}

async function saveAcademicLevel() {
  if (isSavingLevel.value) {
    return;
  }

  levelError.value = "";

  if (!["ssc", "hsc"].includes(selectedAcademicLevel.value)) {
    levelError.value = "Select SSC or HSC.";
    return;
  }

  const accessToken = store.state.auth.accessToken;

  if (!accessToken) {
    await router.replace("/login");
    return;
  }

  isSavingLevel.value = true;

  try {
    const data = await apiRequest("/api/auth/me/academic-level", accessToken, {
      method: "PATCH",
      body: JSON.stringify({
        academic_level: selectedAcademicLevel.value,
      }),
    });

    if (!data) {
      return;
    }

    if (!data.user || !["ssc", "hsc"].includes(data.user.academic_level)) {
      throw new Error("Server returned an invalid study level.");
    }

    store.commit("auth/SET_AUTH", {
      token: accessToken,
      user: data.user,
    });

    store.commit("tutor/RESET_STATE", data.user.id);

    await loadLearningContent();
  } catch (error) {
    if (isCurrentRequest(accessToken)) {
      levelError.value = getErrorText(error, "Could not save study level.");
    }
  } finally {
    isSavingLevel.value = false;
  }
}

onMounted(async () => {
  const accessToken = store.state.auth.accessToken;

  if (!accessToken) {
    await router.replace("/login");
    return;
  }

  try {
    const data = await apiRequest("/api/auth/me", accessToken);

    if (!data) {
      return;
    }

    if (!data.user || data.user.role !== "student") {
      throw new Error("Could not load your student profile.");
    }

    store.commit("auth/SET_AUTH", {
      token: accessToken,
      user: data.user,
    });

    if (hasAcademicLevel.value) {
      await loadLearningContent();
    }
  } catch (error) {
    if (isCurrentRequest(accessToken)) {
      levelError.value = getErrorText(
        error,
        "Could not load your profile. Refresh the page to try again.",
      );
    }
  }
});
</script>

<template>
  <section class="home-page">
    <header class="tutor-page-heading">
      <div>
        <p class="eyebrow">MAIRA TUTOR</p>
        <h1>Tomar learning space</h1>
        <p class="tutor-page-intro">
          Maira-ke question koro, topic bujhe nao, ar nijer moto kore shekho.
        </p>
      </div>

      <RouterLink
        class="tutor-dashboard-link"
        :to="{ name: 'student-dashboard' }"
      >
        Dashboard-e jao →
      </RouterLink>
    </header>

    <section
      v-if="!hasAcademicLevel"
      class="study-level-card"
      aria-labelledby="study-level-heading"
    >
      <p class="eyebrow">YOUR LEARNING PATH</p>
      <h2 id="study-level-heading">Select your study level</h2>

      <p>
        Tomar learning topics dekhte SSC ba HSC select koro. Save korar por ei
        selection change kora jabe na.
      </p>

      <form @submit.prevent="saveAcademicLevel">
        <label for="student-study-level"> Study level </label>

        <select
          id="student-study-level"
          v-model="selectedAcademicLevel"
          :disabled="isSavingLevel"
          required
        >
          <option value="" disabled>Select your study level</option>
          <option value="ssc">SSC</option>
          <option value="hsc">HSC</option>
        </select>

        <p v-if="levelError" class="error-message" role="alert">
          {{ levelError }}
        </p>

        <button type="submit" class="history-action" :disabled="isSavingLevel">
          {{ isSavingLevel ? "Saving..." : "Save and continue" }}
        </button>
      </form>
    </section>

    <p v-if="hasAcademicLevel && levelError" class="error-message" role="alert">
      {{ levelError }}
    </p>

    <div v-if="hasAcademicLevel" class="learning-layout">
      <section class="topics-panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">YOUR SUBJECT</p>
            <h2>Subject select koro</h2>
          </div>
        </div>

        <p class="section-intro">
          ICT select kore Maira-ke tomar question koro.
        </p>

        <p v-if="isTopicsLoading" class="loading-message">
          Subjects loading...
        </p>

        <p v-else-if="!subjectTopics.length" class="section-intro">
          No subject available yet.
        </p>

        <div v-else class="topic-grid">
          <button
            v-for="subject in subjectTopics"
            :key="subject.id"
            type="button"
            class="topic-choice"
            :class="{
              selected: selectedTopic === subject.title,
            }"
            :aria-pressed="selectedTopic === subject.title"
            :disabled="isLoading"
            @click="selectTopic(subject.title)"
          >
            <span class="topic-icon" aria-hidden="true"> ✦ </span>

            <span class="topic-content">
              <small>{{ studyLevelLabel }}</small>
              <strong>ICT</strong>
              <span>ICT niye tomar question koro.</span>
            </span>

            <span class="topic-arrow" aria-hidden="true"> → </span>
          </button>
        </div>
      </section>

      <section class="chat-card" aria-label="Tutor conversation">
        <div class="chat-toolbar">
          <p class="eyebrow">
            {{ sessionId ? "SAVED CONVERSATION" : "NEW CONVERSATION" }}
          </p>

          <button
            type="button"
            class="history-action new-chat-button"
            :disabled="isLoading"
            @click="startNewChat"
          >
            + New Chat
          </button>
        </div>

        <details class="chat-history">
          <summary>Previous conversations</summary>

          <p class="history-intro">Open a saved chat to read or continue it.</p>

          <p v-if="historyError" class="error-message" role="alert">
            {{ historyError }}
          </p>

          <p
            v-if="!isHistoryLoading && !conversations.length && !historyError"
            class="history-empty"
          >
            No saved conversations yet.
          </p>

          <div class="history-list">
            <button
              v-for="conversation in conversations"
              :key="conversation.id"
              type="button"
              class="history-item"
              :class="{
                active: sessionId === conversation.id,
              }"
              :aria-pressed="sessionId === conversation.id"
              :disabled="isLoading || isTopicsLoading"
              @click="openConversation(conversation.id)"
            >
              <strong>
                {{ conversation.title }}
              </strong>

              <span>
                {{ conversation.topic }} ·
                {{ conversation.response_language }} ·
                {{ getLearningModeLabel(conversation.learning_mode) }}
              </span>

              <small>
                {{ formatHistoryDate(conversation.updated_at) }}
              </small>
            </button>
          </div>

          <p v-if="isHistoryLoading" class="loading-message" role="status">
            Loading history...
          </p>

          <div class="history-footer">
            <button
              v-if="historyHasNext"
              type="button"
              class="history-action"
              :disabled="isHistoryLoading || isLoading"
              @click="loadHistory(true)"
            >
              Load more
            </button>

            <button
              v-if="historyError"
              type="button"
              class="history-action"
              :disabled="isHistoryLoading || isLoading"
              @click="loadHistory()"
            >
              Retry history
            </button>
          </div>
        </details>

        <div class="section-heading chat-header">
          <div class="tutor-title">
            <span class="tutor-avatar" aria-hidden="true"> M </span>

            <div>
              <p class="eyebrow">AI LEARNING SUPPORT</p>
              <h2>Ask Maira</h2>
            </div>
          </div>

          <div class="language-switch" aria-label="Tutor response language">
            <button
              type="button"
              :class="{
                active: responseLanguage === 'banglish',
              }"
              :aria-pressed="responseLanguage === 'banglish'"
              :disabled="isLoading"
              @click="setResponseLanguage('banglish')"
            >
              Banglish
            </button>

            <button
              type="button"
              :class="{
                active: responseLanguage === 'english',
              }"
              :aria-pressed="responseLanguage === 'english'"
              :disabled="isLoading"
              @click="setResponseLanguage('english')"
            >
              English
            </button>
          </div>
        </div>

        <div class="tutor-mode-controls">
          <p class="eyebrow">LEARNING MODE</p>

          <div class="language-switch" aria-label="Tutor learning mode">
            <button
              type="button"
              :class="{
                active: learningMode === 'personal_growth',
              }"
              :aria-pressed="learningMode === 'personal_growth'"
              :disabled="isLoading"
              @click="setLearningMode('personal_growth')"
            >
              Personal Growth
            </button>

            <button
              type="button"
              :class="{
                active: learningMode === 'exam_preparation',
              }"
              :aria-pressed="learningMode === 'exam_preparation'"
              :disabled="isLoading"
              @click="setLearningMode('exam_preparation')"
            >
              Exam Preparation
            </button>
          </div>

          <p class="practice-hint">
            Current mode:
            {{ getLearningModeLabel(learningMode) }}. Changing mode starts a new
            chat.
          </p>
        </div>

        <div class="selected-topic-note">
          <span class="status-dot" aria-hidden="true"></span>

          <template v-if="selectedTopicData">
            Talking about
            <strong>
              {{ selectedTopicData.title }}
            </strong>
          </template>

          <template v-else-if="sessionId">
            This conversation's topic is currently unavailable.
          </template>

          <template v-else> Select a topic to start learning </template>
        </div>

        <section class="chat-box" aria-label="Messages">
          <article
            v-for="chatMessage in messages"
            :key="chatMessage.id"
            class="message"
            :class="chatMessage.role"
          >
            <span class="message-label">
              {{ chatMessage.role === "assistant" ? "MAIRA" : "YOU" }}
            </span>

            <div
              v-if="chatMessage.role === 'assistant'"
              class="message-content"
              v-html="formatAssistantText(chatMessage.text)"
            ></div>

            <p v-else class="student-message-text">
              {{ chatMessage.text }}
            </p>
          </article>

          <p v-if="isLoading" class="loading-message" role="status">
            {{
              isConversationLoading
                ? "Previous conversation loading..."
                : "Tutor answer ready kortese..."
            }}
          </p>

          <p v-if="errorMessage" class="error-message" role="alert">
            {{ errorMessage }}
          </p>
        </section>

        <form class="chat-form" @submit.prevent="sendMessage">
          <label for="message"> Your question </label>

          <div class="input-wrap">
            <textarea
              id="message"
              v-model="message"
              rows="3"
              maxlength="1000"
              :disabled="isLoading"
              :placeholder="
                responseLanguage === 'banglish'
                  ? 'Example: Binary number system ki?'
                  : 'Example: What is the binary number system?'
              "
            ></textarea>

            <button
              type="submit"
              :disabled="
                isTopicsLoading ||
                isLoading ||
                !selectedTopicData ||
                !message.trim()
              "
            >
              {{
                isConversationLoading
                  ? "Loading..."
                  : isLoading
                    ? "Thinking..."
                    : "Ask"
              }}
              <span aria-hidden="true">→</span>
            </button>
          </div>
        </form>
      </section>

      <aside class="learning-sidebar">
        <section class="path-card">
          <p class="eyebrow">HOW TO PRACTISE</p>
          <h2>Learn at your pace</h2>

          <p class="section-intro">
            Practice korte Quiz Practice page-e giye topic select koro.
          </p>

          <RouterLink class="practice-button" :to="{ name: 'quiz-practice' }">
            Open Quiz Practice →
          </RouterLink>

          <RouterLink class="practice-button" to="/progress">
            View progress →
          </RouterLink>
        </section>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.home-page {
  display: grid;
  gap: 1.3rem;
  min-width: 0;
}

.eyebrow,
.hero-label {
  margin: 0;
  color: var(--accent-color);
  font-size: 0.68rem;
  font-weight: 900;
  letter-spacing: 0.09em;
}

.welcome-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.5rem;
  overflow: hidden;
  border: 1px solid #efd263;
  border-radius: 1.25rem;
  padding: 1.75rem;
  background:
    radial-gradient(
      circle at 72% 0%,
      rgb(255 255 255 / 65%),
      transparent 18rem
    ),
    linear-gradient(120deg, #fff5c9, #fee58e 55%, #eaf1ff);
}

.hero-content {
  min-width: 0;
}

.hero-label {
  color: #8a5a00;
}

.welcome-card h1 {
  margin: 0.7rem 0 0.85rem;
  color: #172554;
  font-size: clamp(1.85rem, 3.6vw, 3rem);
  line-height: 1.1;
}

.welcome-card h1 span {
  color: #1d4ed8;
}

.welcome-card p:not(.hero-label) {
  max-width: 570px;
  margin: 0;
  color: #475569;
  line-height: 1.65;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin-top: 1.1rem;
}

.hero-meta span {
  border-radius: 99rem;
  padding: 0.43rem 0.65rem;
  background: rgb(255 255 255 / 58%);
  color: #475569;
  font-size: 0.75rem;
  font-weight: 800;
}

.hero-meta span:first-child {
  color: #15803d;
}

.hero-visual {
  position: relative;
  width: 13rem;
  height: 11rem;
  flex: 0 0 auto;
}

.hero-code,
.hero-book {
  position: absolute;
  display: grid;
  place-items: center;
  box-shadow: 0 1rem 2rem rgb(30 64 175 / 20%);
}

.hero-code {
  top: 1rem;
  left: 0.5rem;
  z-index: 2;
  width: 7.5rem;
  height: 7.5rem;
  border-radius: 2rem;
  background: #1d4ed8;
  color: #facc15;
  font-size: 2rem;
  font-weight: 900;
  transform: rotate(7deg);
}

.hero-book {
  right: 0.25rem;
  bottom: 0.3rem;
  z-index: 3;
  width: 4.1rem;
  height: 3rem;
  border-radius: 0.9rem;
  background: #fff;
  color: #1d4ed8;
  font-size: 0.82rem;
  font-weight: 950;
  transform: rotate(-8deg);
}

.hero-orb {
  position: absolute;
  border-radius: 50%;
}

.orb-one {
  top: 0.2rem;
  right: 0.8rem;
  width: 3rem;
  height: 3rem;
  background: rgb(249 115 22 / 82%);
}

.orb-two {
  bottom: 0.3rem;
  left: 1rem;
  width: 1.2rem;
  height: 1.2rem;
  background: #22c55e;
}

.hero-spark {
  position: absolute;
  z-index: 4;
  color: #fff;
  font-size: 1.35rem;
}

.spark-one {
  top: 0.2rem;
  left: 3.8rem;
}

.spark-two {
  right: 1.4rem;
  bottom: 3.4rem;
  color: #1d4ed8;
}

.learning-layout {
  display: grid;
  grid-template-columns:
    minmax(300px, 0.78fr)
    minmax(520px, 1.38fr)
    minmax(230px, 0.56fr);
  align-items: start;
  gap: 1.15rem;
}

.topics-panel,
.chat-card,
.path-card {
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 1.15rem;
  padding: 1.25rem;
  background: var(--surface-color);
  box-shadow: 0 0.7rem 1.7rem rgb(15 23 42 / 6%);
}

.section-heading,
.chat-header,
.tutor-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
}

.section-heading {
  align-items: flex-start;
}

.section-heading h2,
.path-card h2 {
  margin: 0.35rem 0 0;
  color: var(--text-primary);
  font-size: 1.3rem;
}

.section-intro,
.selected-topic-note,
.practice-hint {
  margin: 0.8rem 0 0;
  color: var(--text-secondary);
  font-size: 0.86rem;
  line-height: 1.55;
}

.topic-grid {
  display: grid;
  gap: 0.75rem;
  margin-top: 1rem;
}

.topic-choice {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.95rem;
  padding: 0.85rem;
  background: var(--page-background);
  color: var(--text-primary);
  cursor: pointer;
  font: inherit;
  text-align: left;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background-color 0.2s ease;
}

.topic-choice:hover:not(:disabled) {
  border-color: var(--accent-color);
  box-shadow: 0 0.7rem 1.2rem rgb(29 78 216 / 10%);
  transform: translateY(-2px);
}

.topic-choice.selected {
  border-color: var(--accent-color);
  background: var(--nav-hover);
  box-shadow: 0 0 0 3px rgb(29 78 216 / 10%);
}

.topic-choice:disabled {
  cursor: wait;
  opacity: 0.7;
}

.topic-icon {
  display: grid;
  width: 2.7rem;
  height: 2.7rem;
  place-items: center;
  border-radius: 0.85rem;
  background: #e9efff;
  color: var(--accent-color);
  font-size: 1.3rem;
  font-weight: 900;
}

.topic-choice.selected .topic-icon {
  background: var(--accent-color);
  color: #fff;
}

.topic-content {
  display: grid;
  gap: 0.22rem;
  min-width: 0;
}

.topic-content small {
  color: var(--accent-color);
  font-size: 0.62rem;
  font-weight: 900;
  letter-spacing: 0.08em;
}

.topic-content strong {
  color: var(--text-primary);
  font-size: 0.92rem;
}

.topic-content span {
  display: -webkit-box;
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 0.75rem;
  line-height: 1.4;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
  line-clamp: 1;
}

.topic-arrow {
  color: var(--accent-color);
  font-size: 1.1rem;
  font-weight: 900;
  transition: transform 0.2s ease;
}

.topic-choice:hover .topic-arrow,
.topic-choice.selected .topic-arrow {
  transform: translateX(3px);
}

.chat-card {
  min-height: 700px;
}

.tutor-title {
  justify-content: flex-start;
}

.tutor-avatar {
  display: grid;
  width: 2.7rem;
  height: 2.7rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.9rem;
  background: linear-gradient(135deg, #1d4ed8, #4d8dff);
  box-shadow: 0 0.55rem 1rem rgb(29 78 216 / 20%);
  color: #facc15;
  font-size: 1rem;
  font-weight: 950;
}

.language-switch {
  display: inline-flex;
  overflow: hidden;
  border: 1px solid var(--border-color);
  border-radius: 0.65rem;
  background: var(--page-background);
}

.language-switch button {
  border: 0;
  padding: 0.42rem 0.52rem;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font: inherit;
  font-size: 0.69rem;
  font-weight: 850;
}

.language-switch button.active {
  background: var(--accent-color);
  color: #fff;
}

.language-switch button:disabled {
  cursor: wait;
  opacity: 0.7;
}

.selected-topic-note {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-top: 1rem;
}

.selected-topic-note strong {
  color: var(--accent-color);
}

.status-dot {
  width: 0.52rem;
  height: 0.52rem;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #22c55e;
}

.chat-box {
  display: grid;
  align-content: start;
  gap: 0.8rem;
  min-height: 360px;
  max-height: 460px;
  margin-top: 0.9rem;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  padding: 0.9rem;
  background:
    radial-gradient(
      circle at 100% 0%,
      rgb(77 141 255 / 10%),
      transparent 12rem
    ),
    var(--page-background);
}

.message {
  width: fit-content;
  min-width: 0;
  max-width: 88%;
  box-sizing: border-box;
  border-radius: 1rem;
  padding: 0.75rem 0.85rem;
  overflow-wrap: anywhere;
  animation: message-enter 0.28s ease-out;
}

.message.assistant {
  border-bottom-left-radius: 0.2rem;
  background: var(--surface-color);
  color: var(--text-primary);
  box-shadow: 0 0.3rem 0.8rem rgb(15 23 42 / 7%);
}

.message.student {
  justify-self: end;
  border-bottom-right-radius: 0.2rem;
  background: var(--accent-color);
  color: #fff;
}

.message-label {
  display: block;
  margin-bottom: 0.2rem;
  color: var(--accent-color);
  font-size: 0.57rem;
  font-weight: 950;
  letter-spacing: 0.09em;
}

.message.student .message-label {
  color: #dbeafe;
}

.student-message-text {
  margin: 0;
  font-size: 0.86rem;
  line-height: 1.55;
  white-space: pre-wrap;
}

.message-content :deep(p) {
  margin: 0;
  font-size: 0.86rem;
  line-height: 1.55;
}

.message-content :deep(h3) {
  margin: 0.8rem 0 0.35rem;
  color: inherit;
  font-size: 0.92rem;
  line-height: 1.35;
}

.message-content :deep(h3:first-child) {
  margin-top: 0;
}

.message-content :deep(strong) {
  font-weight: 850;
}

.message-content :deep(code) {
  border-radius: 0.25rem;
  padding: 0.1rem 0.25rem;
  background: var(--nav-hover);
  font-size: 0.82rem;
}

.message-content :deep(.markdown-list-item) {
  padding-left: 0.15rem;
}

.message-content :deep(.markdown-spacer) {
  height: 0.45rem;
}

.message-content :deep(hr) {
  margin: 0.8rem 0;
  border: 0;
  border-top: 1px solid var(--border-color);
}

.loading-message,
.error-message {
  margin: 0;
  font-size: 0.84rem;
  line-height: 1.5;
}

.loading-message {
  color: var(--text-secondary);
  font-style: italic;
}

.error-message {
  color: #dc2626;
}

.chat-form {
  display: grid;
  gap: 0.5rem;
  margin-top: 0.9rem;
}

.chat-form label {
  color: var(--text-primary);
  font-size: 0.8rem;
  font-weight: 850;
}

.input-wrap {
  position: relative;
}

.chat-form textarea {
  width: 100%;
  box-sizing: border-box;
  min-height: 92px;
  padding: 0.75rem 4.7rem 0.75rem 0.8rem;
  resize: vertical;
  outline: none;
  border: 1px solid var(--border-color);
  border-radius: 0.85rem;
  background: var(--page-background);
  color: var(--text-primary);
  font: inherit;
  font-size: 0.84rem;
}

.chat-form textarea:focus {
  border-color: var(--accent-color);
  box-shadow: 0 0 0 3px rgb(29 78 216 / 12%);
}

.chat-form button {
  position: absolute;
  right: 0.45rem;
  bottom: 0.45rem;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border: 0;
  border-radius: 0.62rem;
  padding: 0.55rem 0.65rem;
  background: var(--accent-color);
  color: #fff;
  cursor: pointer;
  font: inherit;
  font-size: 0.74rem;
  font-weight: 850;
}

.chat-form button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.learning-sidebar {
  display: grid;
  gap: 1rem;
}

.practice-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.55rem;
  width: 100%;
  box-sizing: border-box;
  margin-top: 1.3rem;
  border-radius: 0.75rem;
  padding: 0.8rem 1rem;
  background: var(--accent-color);
  color: #fff;
  font-size: 0.86rem;
  font-weight: 850;
  text-decoration: none;
  transition:
    transform 0.2s ease,
    background-color 0.2s ease,
    box-shadow 0.2s ease;
}

.practice-button:hover {
  background: var(--accent-hover);
  box-shadow: 0 0.7rem 1.3rem rgb(29 78 216 / 22%);
  transform: translateY(-2px);
}

.practice-hint {
  padding-top: 0.4rem;
}

.chat-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.7rem;
  margin-bottom: 0.85rem;
}

.chat-history {
  margin-bottom: 1.2rem;
  border: 1px solid var(--border-color);
  border-radius: 0.85rem;
  padding: 0.9rem;
  background: var(--page-background);
}

.chat-history summary {
  color: var(--text-primary);
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 800;
}

.history-intro,
.history-empty {
  margin: 0.75rem 0;
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.5;
}

.history-list {
  display: grid;
  gap: 0.55rem;
  max-height: 17rem;
  overflow-y: auto;
}

.history-item {
  display: grid;
  gap: 0.3rem;
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 0.65rem;
  padding: 0.75rem;
  background: var(--surface-color);
  color: var(--text-primary);
  cursor: pointer;
  font: inherit;
  text-align: left;
  overflow-wrap: anywhere;
}

.history-item strong {
  font-size: 0.82rem;
}

.history-item span,
.history-item small {
  color: var(--text-secondary);
  font-size: 0.72rem;
}

.history-item:hover:not(:disabled),
.history-item.active {
  border-color: var(--accent-color);
  background: var(--nav-hover);
}

.history-action {
  border: 1px solid var(--border-color);
  border-radius: 0.6rem;
  padding: 0.5rem 0.7rem;
  background: var(--surface-color);
  color: var(--accent-color);
  cursor: pointer;
  font: inherit;
  font-size: 0.76rem;
  font-weight: 800;
}

.history-action:disabled,
.history-item:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.history-action:focus-visible,
.history-item:focus-visible,
.chat-history summary:focus-visible,
.practice-button:focus-visible,
.topic-choice:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

.history-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-top: 0.65rem;
}

.chat-history > .loading-message {
  margin-top: 0.65rem;
}

.tutor-mode-controls {
  display: grid;
  gap: 0.55rem;
  margin-top: 1rem;
}

.tutor-mode-controls .eyebrow,
.tutor-mode-controls .practice-hint {
  margin: 0;
}

.tutor-mode-controls .language-switch {
  justify-self: start;
  max-width: 100%;
}

.study-level-card {
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  padding: 1.5rem;
  background: var(--surface-color);
  color: var(--text-primary);
}

.study-level-card h2 {
  margin: 0.65rem 0;
}

.study-level-card > p:not(.eyebrow) {
  color: var(--text-secondary);
  line-height: 1.6;
}

.study-level-card form {
  display: grid;
  gap: 0.85rem;
  max-width: 24rem;
}

.study-level-card label {
  font-weight: 700;
}

.study-level-card select {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border-color);
  border-radius: 0.7rem;
  padding: 0.85rem;
  background: var(--page-background);
  color: var(--text-primary);
  font: inherit;
}

.study-level-card select:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

.study-level-card button {
  justify-self: start;
}

:global(.dark-theme) .welcome-card {
  border-color: #715d1f;
  background:
    radial-gradient(
      circle at 72% 0%,
      rgb(255 255 255 / 10%),
      transparent 18rem
    ),
    linear-gradient(120deg, #5d4d18, #352f22 55%, #132442);
}

:global(.dark-theme) .welcome-card h1 {
  color: #fff;
}

:global(.dark-theme) .welcome-card p:not(.hero-label) {
  color: #e2e8f0;
}

:global(.dark-theme) .topic-icon {
  background: #1b3156;
}

@media (max-width: 1280px) {
  .learning-layout {
    grid-template-columns:
      minmax(0, 1fr)
      minmax(340px, 0.9fr);
  }

  .learning-sidebar {
    grid-column: 1 / -1;
  }
}

@media (max-width: 860px) {
  .learning-layout,
  .learning-sidebar {
    grid-template-columns: 1fr;
  }

  .learning-sidebar {
    grid-column: auto;
  }

  .chat-card {
    min-height: auto;
  }
}

@media (max-width: 620px) {
  .welcome-card {
    align-items: flex-start;
    flex-direction: column;
    padding: 1.35rem;
  }

  .hero-visual {
    align-self: flex-end;
    width: 9rem;
    height: 7rem;
  }

  .hero-code {
    width: 5.5rem;
    height: 5.5rem;
    border-radius: 1.5rem;
    font-size: 1.55rem;
  }

  .hero-book {
    width: 3.2rem;
    height: 2.4rem;
  }

  .chat-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .language-switch {
    align-self: flex-start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .message {
    animation: none;
  }
}
.new-chat-button {
  border-color: transparent;
  background: var(--accent-color);
  color: #fff;
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.new-chat-button:hover:not(:disabled) {
  background: var(--accent-hover);
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.new-chat-button:active:not(:disabled),
.practice-button:active {
  transform: scale(0.98);
}

.topic-choice.selected:hover:not(:disabled) {
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
}
.chat-form button {
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.chat-form button:hover:not(:disabled) {
  background: var(--accent-hover);
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.chat-form button:active:not(:disabled) {
  transform: scale(0.98);
}

.chat-form button:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}
/* Compact tutor header */
.tutor-page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 1rem;
}

.tutor-page-heading .eyebrow {
  color: #800000;
}

.tutor-page-heading h1 {
  margin: 0.4rem 0 0;
  color: var(--text-primary);
  font-size: clamp(1.5rem, 3vw, 2rem);
  line-height: 1.2;
}

.tutor-page-intro {
  margin: 0.6rem 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.tutor-dashboard-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.75rem 1rem;
  border-radius: 0.65rem;
  background: #2450db;
  color: #fff;
  font-weight: 700;
  text-decoration: none;
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.tutor-dashboard-link:hover {
  background: #1d3fb8;
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

/* Subject upore, chat niche full width */
.home-page .learning-layout {
  grid-template-columns: minmax(0, 1fr);
}

.home-page .topics-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(240px, 360px);
  align-items: center;
  column-gap: 1.5rem;
  row-gap: 0.5rem;
  padding: 1rem 1.25rem;
}

.topics-panel .section-heading {
  grid-column: 1;
  grid-row: 1;
}

.topics-panel > .section-intro {
  grid-column: 1;
  grid-row: 2;
  margin: 0;
}

.topics-panel .topic-grid {
  grid-column: 2;
  grid-row: 1 / span 2;
  margin: 0;
}

.home-page .chat-card {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.home-page .chat-box {
  min-height: 420px;
  max-height: 65vh;
}

/* Maira panel-er maroon theme */
.home-page .chat-card {
  --accent-color: #800000;
  --accent-hover: #650000;
  --nav-hover: #f8e9ec;
}

.home-page .chat-card .tutor-avatar {
  background: linear-gradient(135deg, #800000, #a83248);
  box-shadow: 0 0.55rem 1rem rgb(128 0 0 / 20%);
}

.home-page .chat-box {
  background:
    radial-gradient(circle at 100% 0%, rgb(128 0 0 / 8%), transparent 15rem),
    var(--page-background);
}

.home-page .chat-card .new-chat-button,
.home-page .chat-card .chat-form button {
  background: #800000;
  border-color: #800000;
  color: #fff;
}

.home-page .chat-card .new-chat-button:hover:not(:disabled),
.home-page .chat-card .chat-form button:hover:not(:disabled) {
  background: #650000;
  border-color: #650000;
  box-shadow: 0 0.6rem 1rem rgb(128 0 0 / 20%);
}

.home-page .chat-card .language-switch button.active {
  background: #800000;
  color: #fff;
}

.tutor-dashboard-link:focus-visible {
  outline: 2px solid #2450db;
  outline-offset: 3px;
}

/* Dark mode-e readable maroon accents */
:global(.dark-theme) .home-page .chat-card {
  --accent-color: #f0a6b5;
  --accent-hover: #ffd1db;
  --nav-hover: #3b202d;
}

:global(.dark-theme) .tutor-page-heading .eyebrow {
  color: #f0a6b5;
}

@media (max-width: 680px) {
  .home-page .topics-panel {
    grid-template-columns: minmax(0, 1fr);
    gap: 0.75rem;
  }

  .topics-panel .section-heading,
  .topics-panel > .section-intro,
  .topics-panel .topic-grid {
    grid-column: 1;
    grid-row: auto;
  }

  .home-page .chat-box {
    min-height: 320px;
    max-height: 60vh;
  }
}
</style>
