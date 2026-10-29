<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useStore } from "vuex";

const router = useRouter();
const store = useStore();

const feedbackItems = ref([]);
const currentPage = ref(0);
const hasMore = ref(false);
const isLoading = ref(false);
const errorMessage = ref("");
const openingFeedbackId = ref(null);
const chatError = ref("");
const chatErrorFeedbackId = ref(null);

let active = true;

onBeforeUnmount(() => {
  active = false;
});

async function loadFeedback(append = false) {
  if (isLoading.value) return;

  const accessToken = store.state.auth.accessToken;

  if (!accessToken) {
    await router.replace("/login");
    return;
  }

  const nextPage = append ? currentPage.value + 1 : 1;

  isLoading.value = true;
  errorMessage.value = "";

  try {
    const response = await fetch(
      `http://127.0.0.1:5000/api/feedback/me?page=${nextPage}`,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      },
    );

    if (response.status === 401) {
      store.commit("auth/CLEAR_AUTH");
      await router.replace("/login");
      return;
    }

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Could not load teacher feedback.");
    }

    if (append) {
      const existingIds = new Set(feedbackItems.value.map((item) => item.id));

      feedbackItems.value.push(
        ...data.feedback.filter((item) => !existingIds.has(item.id)),
      );
    } else {
      feedbackItems.value = data.feedback;
    }

    currentPage.value = data.pagination.page;
    hasMore.value = data.pagination.has_more;
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : "Could not load teacher feedback.";
  } finally {
    isLoading.value = false;
  }
}
async function messageTeacher(item) {
  if (openingFeedbackId.value !== null) return;

  chatError.value = "";
  chatErrorFeedbackId.value = item.id;

  const teacherId = item.teacher_id;

  if (!Number.isSafeInteger(teacherId) || teacherId < 1) {
    chatError.value = "Teacher information is unavailable.";
    return;
  }

  const accessToken = store.state.auth.accessToken;
  const ownerId = store.state.auth.currentUser?.id;

  if (!accessToken) {
    await router.replace("/login");
    return;
  }

  const isCurrentAccount = () =>
    active &&
    store.state.auth.accessToken === accessToken &&
    store.state.auth.currentUser?.id === ownerId;

  openingFeedbackId.value = item.id;

  try {
    const response = await fetch(
      "http://127.0.0.1:5000/api/messages/conversations",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          recipient_id: teacherId,
        }),
      },
    );

    if (!isCurrentAccount()) return;

    if (response.status === 401) {
      store.commit("auth/CLEAR_AUTH");
      await router.replace("/login");
      return;
    }

    const data = await response.json();

    if (!isCurrentAccount()) return;

    if (!response.ok) {
      const validationMessage = Object.values(data.messages || {})
        .flat()
        .find((value) => typeof value === "string");

      throw new Error(
        validationMessage ||
          data.error ||
          "Could not open teacher chat. Try again.",
      );
    }

    const conversationId = data.conversation?.id;

    if (!Number.isSafeInteger(conversationId) || conversationId < 1) {
      throw new Error("Could not open teacher chat. Try again.");
    }

    await router.push({
      name: "messages",
      params: {
        conversationId: String(conversationId),
      },
    });
  } catch (error) {
    if (isCurrentAccount()) {
      chatError.value =
        error instanceof Error
          ? error.message
          : "Could not open teacher chat. Try again.";
    }
  } finally {
    openingFeedbackId.value = null;
  }
}

function formatDate(value) {
  const date = new Date(value);

  if (!value || Number.isNaN(date.getTime())) {
    return "Date unavailable";
  }

  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

onMounted(() => loadFeedback());
</script>

<template>
  <section
    class="student-feedback"
    aria-labelledby="student-feedback-heading"
    :aria-busy="isLoading"
  >
    <header class="panel-heading">
      <div>
        <p class="eyebrow">TEACHER SUPPORT</p>
        <h2 id="student-feedback-heading">Your teacher's feedback</h2>
        <p class="intro">
          Teacher-er advice dekho ar shei onujayi practice koro.
        </p>
      </div>

      <button
        type="button"
        class="secondary-button"
        :disabled="isLoading"
        @click="loadFeedback()"
      >
        {{ isLoading ? "Loading..." : "Refresh" }}
      </button>
    </header>

    <p
      v-if="isLoading && feedbackItems.length === 0"
      class="status-message"
      role="status"
    >
      Loading teacher feedback...
    </p>

    <div v-if="errorMessage" class="error-state">
      <p class="error-message" role="alert">
        {{ errorMessage }}
      </p>
      <button
        type="button"
        class="secondary-button"
        :disabled="isLoading"
        @click="loadFeedback()"
      >
        Try again
      </button>
    </div>

    <p
      v-if="!isLoading && !errorMessage && feedbackItems.length === 0"
      class="status-message"
    >
      No feedback yet. Teacher feedback pathale ekhane dekhte parbe.
    </p>

    <div v-if="feedbackItems.length > 0" class="feedback-list">
      <article
        v-for="item in feedbackItems"
        :key="item.id"
        class="feedback-card"
      >
        <div class="feedback-header">
          <div class="teacher-details">
            <h3>{{ item.teacher_name }}</h3>
            <p>{{ item.classroom_name }}</p>
          </div>

          <time :datetime="item.created_at">
            {{ formatDate(item.created_at) }}
          </time>
        </div>

        <span class="feedback-type">
          {{
            item.attempt_id == null
              ? "General learning feedback"
              : `Quiz attempt #${item.attempt_id}`
          }}
        </span>

        <p class="feedback-content">{{ item.message }}</p>
        <div class="feedback-actions">
          <button
            type="button"
            class="secondary-button"
            :disabled="openingFeedbackId !== null"
            :aria-label="`Message teacher ${item.teacher_name}`"
            @click="messageTeacher(item)"
          >
            {{
              openingFeedbackId === item.id ? "Opening..." : "Message teacher"
            }}
          </button>

          <p
            v-if="chatError && chatErrorFeedbackId === item.id"
            class="error-message"
            role="alert"
          >
            {{ chatError }}
          </p>
        </div>
      </article>
    </div>

    <button
      v-if="hasMore && !errorMessage"
      type="button"
      class="secondary-button load-more"
      :disabled="isLoading"
      @click="loadFeedback(true)"
    >
      {{ isLoading ? "Loading..." : "Load older feedback" }}
    </button>
  </section>
</template>

<style scoped>
.student-feedback {
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 1.1rem;
  padding: 1.5rem;
  background: var(--surface-color);
}

.panel-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.eyebrow {
  margin: 0 0 0.5rem;
  color: var(--accent-color);
  font-size: 0.73rem;
  font-weight: 800;
  letter-spacing: 0.1em;
}

h2,
h3 {
  margin: 0;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

h2 {
  font-size: 1.15rem;
}

h3 {
  font-size: 0.95rem;
}

.intro,
.status-message {
  color: var(--text-secondary);
  font-size: 0.9rem;
  line-height: 1.6;
}

.intro {
  margin: 0.65rem 0 0;
}

.status-message {
  margin: 1.25rem 0 0;
}

.secondary-button {
  flex: 0 0 auto;
  width: fit-content;
  border: 0;
  border-radius: 0.65rem;
  padding: 0.75rem 0.95rem;
  background: var(--accent-color);
  color: #fff;
  cursor: pointer;
  font: inherit;
  font-weight: 700;
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.secondary-button:hover:not(:disabled) {
  background: var(--accent-hover);
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.secondary-button:active:not(:disabled) {
  transform: scale(0.98);
}

.secondary-button:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

.secondary-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.feedback-actions .secondary-button {
  background: #dbeafe;
  color: #1e40af;
}

.feedback-actions .secondary-button:hover:not(:disabled) {
  background: #bfdbfe;
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}
.feedback-list {
  display: grid;
  gap: 0.85rem;
  margin-top: 1.25rem;
}

.feedback-card {
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 0.85rem;
  padding: 1rem;
  background: var(--page-background);
}

.feedback-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

.teacher-details {
  min-width: 0;
}

.teacher-details p {
  margin: 0.3rem 0 0;
  color: var(--text-secondary);
  font-size: 0.82rem;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

time {
  flex: 0 0 auto;
  color: var(--text-secondary);
  font-size: 0.78rem;
  line-height: 1.5;
}

.feedback-type {
  display: inline-block;
  margin-top: 0.85rem;
  border-radius: 999px;
  padding: 0.35rem 0.65rem;
  background: var(--nav-hover);
  color: var(--accent-color);
  font-size: 0.75rem;
  font-weight: 700;
}

.feedback-content {
  margin: 0.85rem 0 0;
  color: var(--text-primary);
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.error-state {
  display: grid;
  gap: 0.75rem;
  margin-top: 1.25rem;
}

.error-message {
  margin: 0;
  color: #dc2626;
  font-size: 0.9rem;
  line-height: 1.6;
}

.load-more {
  margin-top: 1rem;
}

@media (max-width: 540px) {
  .student-feedback {
    padding: 1rem;
  }

  .panel-heading,
  .feedback-header {
    flex-direction: column;
  }
}

.feedback-actions {
  display: grid;
  gap: 0.75rem;
  margin-top: 1rem;
}
</style>
