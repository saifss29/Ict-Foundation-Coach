<script setup>
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { useRoute, useRouter } from "vue-router";
import { useStore } from "vuex";

const route = useRoute();
const router = useRouter();
const store = useStore();

const accessToken = store.state.auth.accessToken;
const ownerId = store.state.auth.currentUser?.id;
const isStudent = computed(
  () => store.state.auth.currentUser?.role === "student",
);

const conversations = ref([]);
const teachers = ref([]);
const selectedTeacher = ref("");
const currentConversation = ref(null);
const messages = ref([]);
const draft = ref("");
const errorMessage = ref("");

const directoryError = ref("");
const isLoading = ref(false);
const isSending = ref(false);
const isStarting = ref(false);
const isLoadingOlder = ref(false);
const hasOlderMessages = ref(false);
const messageContainer = ref(null);

const conversationPage = ref(1);
const hasMoreConversations = ref(false);
const teacherPage = ref(1);
const hasMoreTeachers = ref(false);

let active = true;
let requestVersion = 0;
let refreshTimer;
let refreshing = false;
let loadingConversations = false;
let loadingTeachers = false;

const conversationId = computed(() => {
  const value = route.params.conversationId;

  if (!value) return null;

  const text = String(value);

  if (!/^[1-9]\d*$/.test(text)) return null;

  const id = Number(text);
  return Number.isSafeInteger(id) ? id : null;
});

function isCurrentAccount() {
  return (
    active &&
    store.state.auth.accessToken === accessToken &&
    store.state.auth.currentUser?.id === ownerId
  );
}

function errorText(error) {
  return error instanceof Error
    ? error.message
    : "Could not complete the request.";
}

async function requestMessages(path, options = {}) {
  if (!isCurrentAccount()) {
    throw new Error("Your session has changed.");
  }

  const response = await fetch(`http://127.0.0.1:5000/api/messages${path}`, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!isCurrentAccount()) {
    throw new Error("Your session has changed.");
  }

  if (response.status === 401) {
    store.commit("auth/CLEAR_AUTH");
    await router.replace("/login");
    throw new Error("Your session has expired. Please log in again.");
  }

  const data = await response.json();

  if (!isCurrentAccount()) {
    throw new Error("Your session has changed.");
  }

  if (!response.ok) {
    const validationMessage = Object.values(data.messages || {})
      .flat()
      .find((value) => typeof value === "string");

    throw new Error(
      validationMessage || data.error || "Could not complete the request.",
    );
  }

  return data;
}

function mergeById(existing, incoming) {
  const items = new Map(existing.map((item) => [item.id, item]));

  for (const item of incoming) {
    items.set(item.id, item);
  }

  return [...items.values()];
}

function formatDate(value) {
  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}

async function scrollToBottom() {
  await nextTick();

  if (messageContainer.value) {
    messageContainer.value.scrollTop = messageContainer.value.scrollHeight;
  }
}

async function loadConversations(page = 1) {
  if (loadingConversations || !isCurrentAccount()) return;

  loadingConversations = true;

  try {
    const data = await requestMessages(`/conversations?page=${page}`);

    conversations.value =
      page === 1
        ? mergeById(conversations.value, data.conversations)
        : mergeById(conversations.value, data.conversations);

    conversations.value.sort(
      (first, second) =>
        new Date(second.updated_at).getTime() -
          new Date(first.updated_at).getTime() || second.id - first.id,
    );

    conversationPage.value = page;
    hasMoreConversations.value = data.pagination.has_more;
  } catch (error) {
    if (isCurrentAccount()) {
      errorMessage.value = errorText(error);
    }
  } finally {
    loadingConversations = false;
  }
}

async function loadTeachers(page = 1) {
  if (loadingTeachers || !isStudent.value || !isCurrentAccount()) return;

  loadingTeachers = true;
  directoryError.value = "";

  try {
    const data = await requestMessages(`/teachers?page=${page}`);

    teachers.value =
      page === 1 ? data.teachers : mergeById(teachers.value, data.teachers);

    teacherPage.value = page;
    hasMoreTeachers.value = data.pagination.has_more;
  } catch (error) {
    if (isCurrentAccount()) {
      directoryError.value = errorText(error);
    }
  } finally {
    loadingTeachers = false;
  }
}

async function openConversation(id) {
  if (isSending.value || isStarting.value) return;

  await router.push({
    name: "messages",
    params: { conversationId: String(id) },
  });
}

async function startConversation() {
  if (!selectedTeacher.value || isStarting.value) return;

  isStarting.value = true;
  errorMessage.value = "";

  try {
    const data = await requestMessages("/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recipient_id: Number(selectedTeacher.value),
      }),
    });

    conversations.value = mergeById(conversations.value, [data.conversation]);

    await router.push({
      name: "messages",
      params: { conversationId: String(data.conversation.id) },
    });
  } catch (error) {
    if (isCurrentAccount()) {
      errorMessage.value = errorText(error);
    }
  } finally {
    isStarting.value = false;
  }
}

async function markRead(id, lastMessageId) {
  const data = await requestMessages(`/conversations/${id}/read`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ last_message_id: lastMessageId }),
  });

  const conversation = conversations.value.find((item) => item.id === id);

  if (conversation) {
    conversation.unread_count = data.unread_count;
  }
}

async function loadCurrentConversation() {
  const version = ++requestVersion;
  const id = conversationId.value;

  currentConversation.value = null;
  messages.value = [];
  draft.value = "";
  errorMessage.value = "";
  hasOlderMessages.value = false;
  isLoadingOlder.value = false;

  if (!id) {
    isLoading.value = false;

    if (route.params.conversationId) {
      errorMessage.value = "Invalid conversation ID.";
    }

    return;
  }

  isLoading.value = true;

  try {
    const data = await requestMessages(`/conversations/${id}/messages`);

    if (version !== requestVersion || !isCurrentAccount()) return;

    currentConversation.value = data.conversation;
    messages.value = data.messages;
    hasOlderMessages.value = data.pagination.has_more;

    conversations.value = mergeById(conversations.value, [data.conversation]);

    await scrollToBottom();

    const lastMessage = messages.value.at(-1);

    if (lastMessage) {
      await markRead(id, lastMessage.id);
    }
  } catch (error) {
    if (version === requestVersion && isCurrentAccount()) {
      errorMessage.value = errorText(error);
    }
  } finally {
    if (version === requestVersion) {
      isLoading.value = false;
    }
  }
}

async function loadOlderMessages() {
  const id = conversationId.value;
  const firstMessage = messages.value[0];
  const version = requestVersion;

  if (!id || !firstMessage || isLoadingOlder.value || isSending.value) return;

  isLoadingOlder.value = true;
  errorMessage.value = "";

  try {
    const container = messageContainer.value;
    const previousHeight = container?.scrollHeight || 0;
    const previousTop = container?.scrollTop || 0;

    const data = await requestMessages(
      `/conversations/${id}/messages?before_id=${firstMessage.id}`,
    );

    if (version !== requestVersion || !isCurrentAccount()) return;

    messages.value = mergeById(messages.value, data.messages).sort(
      (first, second) => first.id - second.id,
    );
    hasOlderMessages.value = data.pagination.has_more;

    await nextTick();

    if (container) {
      container.scrollTop =
        previousTop + container.scrollHeight - previousHeight;
    }
  } catch (error) {
    if (version === requestVersion && isCurrentAccount()) {
      errorMessage.value = errorText(error);
    }
  } finally {
    if (version === requestVersion) {
      isLoadingOlder.value = false;
    }
  }
}

async function sendMessage() {
  const content = draft.value.trim();
  const id = conversationId.value;
  const version = requestVersion;

  if (
    !content ||
    !id ||
    !currentConversation.value ||
    isSending.value ||
    isLoading.value
  ) {
    return;
  }

  if (content.length > 2000) {
    errorMessage.value = "Message must be 2000 characters or fewer.";
    return;
  }

  isSending.value = true;
  errorMessage.value = "";

  try {
    const data = await requestMessages(`/conversations/${id}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });

    if (version !== requestVersion || !isCurrentAccount()) return;

    messages.value = mergeById(messages.value, [data.message]).sort(
      (first, second) => first.id - second.id,
    );
    draft.value = "";

    await scrollToBottom();
    await loadConversations();
  } catch (error) {
    if (version === requestVersion && isCurrentAccount()) {
      errorMessage.value = errorText(error);
    }
  } finally {
    isSending.value = false;
  }
}

async function refreshMessages() {
  if (
    refreshing ||
    isLoading.value ||
    isSending.value ||
    isLoadingOlder.value ||
    !isCurrentAccount()
  ) {
    return;
  }

  refreshing = true;
  const version = requestVersion;
  const id = conversationId.value;

  try {
    await loadConversations();

    if (!id || !currentConversation.value) return;

    const data = await requestMessages(`/conversations/${id}/messages`);

    if (version !== requestVersion || !isCurrentAccount()) return;

    const container = messageContainer.value;
    const nearBottom =
      !container ||
      container.scrollHeight - container.scrollTop - container.clientHeight <
        100;

    const previousLastId = messages.value.at(-1)?.id;

    messages.value = mergeById(messages.value, data.messages).sort(
      (first, second) => first.id - second.id,
    );

    // A long gap between refreshes may contain messages beyond
    // the latest page. Reload the conversation to paginate safely.
    if (
      previousLastId &&
      data.pagination.has_more &&
      !data.messages.some((item) => item.id === previousLastId)
    ) {
      await loadCurrentConversation();
      return;
    }

    if (nearBottom) {
      await scrollToBottom();
    }

    const lastMessage = messages.value.at(-1);

    if (lastMessage) {
      await markRead(id, lastMessage.id);
    }
  } catch (error) {
    if (version === requestVersion && isCurrentAccount()) {
      errorMessage.value = errorText(error);
    }
  } finally {
    refreshing = false;
  }
}

watch(() => route.params.conversationId, loadCurrentConversation, {
  immediate: true,
});

onMounted(() => {
  loadConversations();

  if (isStudent.value) {
    loadTeachers();
  }

  refreshTimer = window.setInterval(() => {
    if (document.visibilityState === "visible") {
      refreshMessages();
    }
  }, 15000);
});

onBeforeUnmount(() => {
  active = false;
  requestVersion += 1;
  window.clearInterval(refreshTimer);
});
</script>

<template>
  <section class="messages-page">
    <header class="page-heading">
      <div>
        <h1>Messages</h1>
        <p>Teacher ar student-er direct conversation.</p>
      </div>

      <button type="button" class="secondary-button" @click="refreshMessages">
        Refresh
      </button>
    </header>

    <p v-if="errorMessage" class="error-message" role="alert">
      {{ errorMessage }}
    </p>

    <div class="messages-layout">
      <aside class="conversation-panel" aria-label="Conversations">
        <form
          v-if="isStudent"
          class="new-conversation"
          @submit.prevent="startConversation"
        >
          <h2>Contact a teacher</h2>
          <p>Class-e join na koreo teacher-ke message dite parbe.</p>

          <label for="message-teacher">Teacher</label>
          <select
            id="message-teacher"
            v-model="selectedTeacher"
            :disabled="isStarting"
            required
          >
            <option value="">Select a teacher</option>
            <option
              v-for="teacher in teachers"
              :key="teacher.id"
              :value="teacher.id"
            >
              {{ teacher.name }}
            </option>
          </select>

          <button type="submit" :disabled="!selectedTeacher || isStarting">
            {{ isStarting ? "Opening..." : "Start conversation" }}
          </button>

          <button
            v-if="hasMoreTeachers"
            type="button"
            class="secondary-button"
            @click="loadTeachers(teacherPage + 1)"
          >
            Load more teachers
          </button>

          <p v-if="directoryError" class="error-message" role="alert">
            {{ directoryError }}
          </p>

          <button
            v-if="directoryError"
            type="button"
            class="secondary-button"
            @click="loadTeachers()"
          >
            Retry teacher list
          </button>
        </form>

        <h2>Your conversations</h2>

        <p v-if="conversations.length === 0" class="muted">
          No conversations yet.
        </p>

        <div class="conversation-list">
          <button
            v-for="conversation in conversations"
            :key="conversation.id"
            type="button"
            class="conversation-button"
            :class="{ selected: conversation.id === conversationId }"
            :disabled="isSending || isStarting"
            :aria-pressed="conversation.id === conversationId"
            @click="openConversation(conversation.id)"
          >
            <span>
              <strong>{{ conversation.other_user.name }}</strong>
              <small>{{ conversation.other_user.role }}</small>
            </span>

            <span v-if="conversation.unread_count" class="unread-badge">
              {{ conversation.unread_count }}
            </span>
          </button>
        </div>

        <button
          v-if="hasMoreConversations"
          type="button"
          class="secondary-button load-more"
          @click="loadConversations(conversationPage + 1)"
        >
          Load more conversations
        </button>
      </aside>

      <section class="chat-panel" aria-label="Direct chat">
        <p v-if="isLoading" class="empty-state" role="status">
          Loading conversation...
        </p>

        <template v-else-if="currentConversation">
          <header class="chat-heading">
            <h2>{{ currentConversation.other_user.name }}</h2>
            <span>{{ currentConversation.other_user.role }}</span>
          </header>

          <div
            ref="messageContainer"
            class="message-list"
            aria-label="Conversation messages"
          >
            <button
              v-if="hasOlderMessages"
              type="button"
              class="secondary-button older-button"
              :disabled="isLoadingOlder"
              @click="loadOlderMessages"
            >
              {{ isLoadingOlder ? "Loading..." : "Load older messages" }}
            </button>

            <p v-if="messages.length === 0" class="muted">
              Send a message to start this conversation.
            </p>

            <article
              v-for="item in messages"
              :key="item.id"
              class="message-bubble"
              :class="{ mine: item.is_mine }"
            >
              <p>{{ item.content }}</p>
              <small>{{ formatDate(item.created_at) }}</small>
            </article>
          </div>

          <form class="message-form" @submit.prevent="sendMessage">
            <label class="sr-only" for="direct-message">Your message</label>

            <textarea
              id="direct-message"
              v-model="draft"
              placeholder="Write your message..."
              maxlength="2000"
              rows="3"
              :disabled="isSending"
              required
            ></textarea>

            <div class="compose-footer">
              <small>{{ draft.length }}/2000</small>

              <button type="submit" :disabled="!draft.trim() || isSending">
                {{ isSending ? "Sending..." : "Send message" }}
              </button>
            </div>
          </form>
        </template>

        <p v-else class="empty-state">
          Select a conversation to read or send messages.
        </p>
      </section>
    </div>
  </section>
</template>

<style scoped>
.messages-page {
  color: var(--text-primary);
}

.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

h1,
h2,
p {
  margin: 0;
}

h1 {
  font-size: 1.8rem;
}

h2 {
  font-size: 1.05rem;
}

.page-heading p,
.muted,
.new-conversation p {
  margin-top: 0.6rem;
  color: var(--text-secondary);
  line-height: 1.6;
}

.messages-layout {
  display: grid;
  grid-template-columns: minmax(240px, 300px) minmax(0, 1fr);
  gap: 1rem;
}

.conversation-panel,
.chat-panel {
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  background: var(--surface-color);
}

.conversation-panel {
  padding: 1.2rem;
}

.new-conversation {
  display: grid;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.new-conversation p {
  font-size: 0.85rem;
}

label {
  font-size: 0.9rem;
  font-weight: 700;
}

button,
select,
textarea {
  font: inherit;
}

button {
  border: 0;
  border-radius: 0.7rem;
  padding: 0.75rem 1rem;
  background: var(--accent-color);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
  transition:
    transform 0.15s ease,
    opacity 0.15s ease;
}

button:hover:not(:disabled) {
  opacity: 0.85;
}

button:active:not(:disabled) {
  transform: scale(0.98);
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.secondary-button {
  border: 1px solid var(--border-color);
  background: var(--page-background);
  color: var(--text-primary);
}

select,
textarea {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid var(--border-color);
  border-radius: 0.7rem;
  padding: 0.8rem;
  background: var(--page-background);
  color: var(--text-primary);
}

textarea {
  resize: vertical;
}

button:focus-visible,
select:focus-visible,
textarea:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

.conversation-list {
  display: grid;
  gap: 0.6rem;
  margin-top: 1rem;
}

.conversation-button {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  border: 1px solid var(--border-color);
  background: var(--page-background);
  color: var(--text-primary);
  text-align: left;
}

.conversation-button.selected {
  border-color: var(--accent-color);
}

.conversation-button strong {
  overflow-wrap: anywhere;
}

.conversation-button small {
  display: block;
  margin-top: 0.3rem;
  color: var(--text-secondary);
  font-weight: 400;
}

.unread-badge {
  flex-shrink: 0;
  border-radius: 999px;
  padding: 0.2rem 0.5rem;
  background: var(--accent-color);
  color: #fff;
  font-size: 0.75rem;
}

.load-more {
  margin-top: 1rem;
  width: 100%;
}

.chat-panel {
  display: flex;
  flex-direction: column;
  min-height: 560px;
}

.chat-heading {
  padding: 1.2rem;
  border-bottom: 1px solid var(--border-color);
}

.chat-heading span {
  display: block;
  margin-top: 0.35rem;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  height: 380px;
  overflow-y: auto;
  padding: 1.2rem;
}

.message-bubble {
  align-self: flex-start;
  max-width: 85%;
  border: 1px solid var(--border-color);
  border-radius: 0.9rem;
  padding: 0.85rem 1rem;
  background: var(--page-background);
}

.message-bubble.mine {
  align-self: flex-end;
  background: var(--accent-color);
  color: #fff;
  border-color: transparent;
}

.message-bubble p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.6;
}

.message-bubble small {
  display: block;
  margin-top: 0.5rem;
  font-size: 0.7rem;
  opacity: 0.75;
}

.older-button {
  align-self: center;
}

.message-form {
  margin-top: auto;
  padding: 1rem;
  border-top: 1px solid var(--border-color);
}

.compose-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 0.6rem;
}

.compose-footer small {
  color: var(--text-secondary);
}

.empty-state {
  margin: auto;
  padding: 2rem;
  color: var(--text-secondary);
  text-align: center;
  line-height: 1.6;
}

.error-message {
  margin-bottom: 1rem;
  color: #dc2626;
  line-height: 1.6;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}

@media (max-width: 800px) {
  .messages-layout {
    grid-template-columns: 1fr;
  }

  .chat-panel {
    min-height: 480px;
  }

  .message-list {
    height: 320px;
  }

  .message-bubble {
    max-width: 90%;
  }
}

@media (prefers-reduced-motion: reduce) {
  button {
    transition: none;
  }
}
.messages-page .page-heading button,
.messages-page .new-conversation button {
  border: 1px solid transparent;
  background: #2450db;
  color: #fff;
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.messages-page .page-heading button:hover:not(:disabled),
.messages-page .new-conversation button:hover:not(:disabled) {
  background: #1d3fb8;
  color: #fff;
  opacity: 1;
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.messages-page .conversation-button {
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.messages-page .conversation-button:hover:not(:disabled) {
  border-color: #2450db;
  background: var(--nav-hover);
  opacity: 1;
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.messages-page .page-heading button:active:not(:disabled),
.messages-page .new-conversation button:active:not(:disabled),
.messages-page .conversation-button:active:not(:disabled) {
  transform: scale(0.98);
}
</style>
