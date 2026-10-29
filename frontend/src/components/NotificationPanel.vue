<script setup>
import { onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useStore } from "vuex";

const router = useRouter();
const store = useStore();

const panelRoot = ref(null);
const toggleButton = ref(null);
const isOpen = ref(false);

const notifications = ref([]);
const unreadCount = ref(0);
const currentPage = ref(0);
const hasMore = ref(false);

const isLoading = ref(false);
const readingId = ref(null);
const errorMessage = ref("");

let refreshTimer = null;
let isActive = true;

function isCurrentRequest(token) {
  return isActive && store.state.auth.accessToken === token;
}

async function requestNotifications(path = "", options = {}) {
  const token = store.state.auth.accessToken;

  if (!token) return null;

  const response = await fetch(
    `http://127.0.0.1:5000/api/notifications${path}`,
    {
      ...options,
      headers: {
        ...options.headers,
        Authorization: `Bearer ${token}`,
      },
    },
  );

  if (!isCurrentRequest(token)) return null;

  if (response.status === 401) {
    store.commit("auth/CLEAR_AUTH");
    await router.replace("/login");
    return null;
  }

  const data = await response.json();

  if (!isCurrentRequest(token)) return null;

  if (!response.ok) {
    throw new Error(data.error || "Could not load notifications.");
  }

  return data;
}

async function refreshUnreadCount() {
  if (isLoading.value || readingId.value !== null) return;

  try {
    const data = await requestNotifications("/unread-count");

    if (data) {
      unreadCount.value = data.unread_count;
    }
  } catch {
    // Opening the panel will show any request error.
  }
}

async function loadNotifications(append = false) {
  if (isLoading.value || readingId.value !== null) return;

  const nextPage = append ? currentPage.value + 1 : 1;

  isLoading.value = true;
  errorMessage.value = "";

  try {
    const data = await requestNotifications(`?page=${nextPage}`);

    if (!data) return;

    if (append) {
      const existingIds = new Set(notifications.value.map((item) => item.id));

      notifications.value.push(
        ...data.notifications.filter((item) => !existingIds.has(item.id)),
      );
    } else {
      notifications.value = data.notifications;
    }

    unreadCount.value = data.unread_count;
    currentPage.value = data.pagination.page;
    hasMore.value = data.pagination.has_more;
  } catch (error) {
    if (!isActive) return;

    errorMessage.value =
      error instanceof Error ? error.message : "Could not load notifications.";
  } finally {
    isLoading.value = false;
  }
}

async function markRead(item) {
  if (isLoading.value || readingId.value !== null) return false;
  if (item.is_read) return true;

  readingId.value = item.id;
  errorMessage.value = "";

  try {
    const data = await requestNotifications(`/${item.id}/read`, {
      method: "PATCH",
    });

    if (!data) return false;

    notifications.value = notifications.value.map((notification) =>
      notification.id === item.id ? data.notification : notification,
    );

    unreadCount.value = data.unread_count;

    return true;
  } catch (error) {
    if (isActive) {
      errorMessage.value =
        error instanceof Error
          ? error.message
          : "Could not mark notification as read.";
    }

    return false;
  } finally {
    readingId.value = null;
  }
}

async function viewFeedback(item) {
  const success = await markRead(item);

  if (!success || !isActive) return;

  await router.push({ name: "student-feedback" });
  isOpen.value = false;
}

async function openChat(item) {
  const conversationId = item.conversation_id;

  if (!Number.isSafeInteger(conversationId) || conversationId <= 0) {
    errorMessage.value = "This conversation is unavailable.";
    return;
  }

  const success = await markRead(item);

  if (!success || !isActive) return;

  try {
    await router.push({
      name: "messages",
      params: {
        conversationId: String(conversationId),
      },
    });

    isOpen.value = false;
  } catch (error) {
    if (isActive) {
      errorMessage.value =
        error instanceof Error
          ? error.message
          : "Could not open the conversation.";
    }
  }
}
async function openLearningAssignments(item) {
  const success = await markRead(item);

  if (!success || !isActive) return;

  try {
    await router.push({
      name: "student-learning-assignments",
    });

    isOpen.value = false;
  } catch (error) {
    if (isActive) {
      errorMessage.value =
        error instanceof Error
          ? error.message
          : "Could not open learning assignments.";
    }
  }
}

function togglePanel() {
  isOpen.value = !isOpen.value;

  if (isOpen.value) {
    loadNotifications();
  }
}

function handleOutsideClick(event) {
  if (
    event.target instanceof Node &&
    panelRoot.value &&
    !panelRoot.value.contains(event.target)
  ) {
    isOpen.value = false;
  }
}

function handleKeydown(event) {
  if (event.key === "Escape" && isOpen.value) {
    isOpen.value = false;
    toggleButton.value?.focus();
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

onMounted(() => {
  refreshUnreadCount();

  // Update the badge every minute while this component is mounted.
  refreshTimer = window.setInterval(() => {
    if (!document.hidden) {
      refreshUnreadCount();
    }
  }, 60000);

  document.addEventListener("click", handleOutsideClick);
  document.addEventListener("keydown", handleKeydown);
});

onUnmounted(() => {
  isActive = false;

  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
  }

  document.removeEventListener("click", handleOutsideClick);
  document.removeEventListener("keydown", handleKeydown);
});
</script>

<template>
  <div ref="panelRoot" class="notification-root">
    <button
      ref="toggleButton"
      type="button"
      class="notification-toggle"
      :aria-expanded="isOpen"
      aria-controls="notification-panel"
      :aria-label="`Notifications: ${unreadCount} unread`"
      @click="togglePanel"
    >
      <span aria-hidden="true">🔔</span>
      <span>Notifications</span>
      <span v-if="unreadCount > 0" class="unread-badge">
        {{ unreadCount > 99 ? "99+" : unreadCount }}
      </span>
    </button>

    <section
      v-if="isOpen"
      id="notification-panel"
      class="notification-panel"
      aria-labelledby="notification-heading"
      :aria-busy="isLoading"
    >
      <header class="panel-header">
        <div>
          <h2 id="notification-heading">Notifications</h2>
          <p>{{ unreadCount }} unread</p>
        </div>

        <button
          type="button"
          class="text-button"
          :disabled="isLoading || readingId !== null"
          @click="loadNotifications()"
        >
          Refresh
        </button>
      </header>

      <p v-if="errorMessage" class="error-message" role="alert">
        {{ errorMessage }}
      </p>

      <p
        v-if="isLoading && notifications.length === 0"
        class="status-message"
        role="status"
      >
        Loading notifications...
      </p>

      <p
        v-else-if="notifications.length === 0 && !errorMessage"
        class="status-message"
      >
        No notifications yet.
      </p>

      <div v-if="notifications.length > 0" class="notification-list">
        <article
          v-for="item in notifications"
          :key="item.id"
          class="notification-item"
          :class="{ unread: !item.is_read }"
        >
          <div class="item-heading">
            <h3>{{ item.title }}</h3>
            <span v-if="!item.is_read" class="new-label">New</span>
          </div>

          <p class="notification-message">{{ item.message }}</p>

          <time :datetime="item.created_at">
            {{ formatDate(item.created_at) }}
          </time>

          <div class="item-actions">
            <button
              v-if="
                store.state.auth.currentUser?.role === 'student' &&
                ['learning_assignment', 'learning_assignment_review'].includes(
                  item.notification_type,
                )
              "
              type="button"
              class="text-button"
              :disabled="isLoading || readingId !== null"
              @click="openLearningAssignments(item)"
            >
              {{
                item.notification_type === "learning_assignment_review"
                  ? "View marks and feedback"
                  : "Open learning assignments"
              }}
            </button>
            <button
              v-if="
                item.notification_type === 'direct_message' &&
                Number.isSafeInteger(item.conversation_id) &&
                item.conversation_id > 0
              "
              type="button"
              class="text-button"
              :disabled="isLoading || readingId !== null"
              @click="openChat(item)"
            >
              Open chat
            </button>
            <button
              v-if="
                item.notification_type === 'teacher_feedback' &&
                item.feedback_id !== null
              "
              type="button"
              class="text-button"
              :disabled="isLoading || readingId !== null"
              @click="viewFeedback(item)"
            >
              View feedback
            </button>

            <button
              v-if="!item.is_read"
              type="button"
              class="text-button"
              :disabled="isLoading || readingId !== null"
              @click="markRead(item)"
            >
              {{ readingId === item.id ? "Saving..." : "Mark as read" }}
            </button>

            <span v-else class="read-label">Read</span>
          </div>
        </article>
      </div>

      <button
        v-if="errorMessage"
        type="button"
        class="footer-button"
        :disabled="isLoading || readingId !== null"
        @click="loadNotifications()"
      >
        Try again
      </button>

      <button
        v-else-if="hasMore"
        type="button"
        class="footer-button"
        :disabled="isLoading || readingId !== null"
        @click="loadNotifications(true)"
      >
        {{ isLoading ? "Loading..." : "Load older notifications" }}
      </button>
    </section>
  </div>
</template>

<style scoped>
.notification-root {
  position: relative;
  min-width: 0;
}

.notification-toggle {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  border: 1px solid var(--border-color);
  border-radius: 0.8rem;
  padding: 0.75rem 0.9rem;
  background: var(--surface-color);
  color: var(--text-primary);
  cursor: pointer;
  font: inherit;
  font-size: 0.85rem;
  font-weight: 700;
}

.notification-toggle:hover {
  background: var(--nav-hover);
}

.unread-badge {
  display: grid;
  min-width: 1.4rem;
  min-height: 1.4rem;
  box-sizing: border-box;
  place-items: center;
  border-radius: 999px;
  padding: 0.15rem 0.35rem;
  background: #dc2626;
  color: #fff;
  font-size: 0.7rem;
}

.notification-panel {
  position: absolute;
  top: calc(100% + 0.65rem);
  right: 0;
  z-index: 30;
  width: min(24rem, calc(100vw - 3rem));
  max-height: 70vh;
  box-sizing: border-box;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  padding: 1rem;
  background: var(--surface-color);
  box-shadow: 0 1rem 2.5rem rgb(15 23 42 / 20%);
}

.panel-header,
.item-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
}

h2,
h3 {
  margin: 0;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

h2 {
  font-size: 1rem;
}

h3 {
  font-size: 0.88rem;
  line-height: 1.5;
}

.panel-header p {
  margin: 0.3rem 0 0;
  color: var(--text-secondary);
  font-size: 0.78rem;
}

.notification-list {
  display: grid;
  gap: 0.65rem;
  margin-top: 1rem;
}

.notification-item {
  border: 1px solid var(--border-color);
  border-radius: 0.75rem;
  padding: 0.85rem;
  background: var(--page-background);
}

.notification-item.unread {
  border-left: 3px solid var(--accent-color);
  background: var(--nav-hover);
}

.new-label {
  flex: 0 0 auto;
  color: var(--accent-color);
  font-size: 0.7rem;
  font-weight: 800;
}

.notification-message {
  margin: 0.5rem 0;
  color: var(--text-primary);
  font-size: 0.82rem;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

time,
.read-label {
  color: var(--text-secondary);
  font-size: 0.72rem;
}

.item-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

.text-button {
  border: 0;
  padding: 0.2rem;
  background: transparent;
  color: var(--accent-color);
  cursor: pointer;
  font: inherit;
  font-size: 0.78rem;
  font-weight: 700;
}

.text-button:hover:not(:disabled) {
  text-decoration: underline;
}

.footer-button {
  width: 100%;
  margin-top: 0.85rem;
  border: 1px solid var(--border-color);
  border-radius: 0.65rem;
  padding: 0.65rem;
  background: var(--page-background);
  color: var(--accent-color);
  cursor: pointer;
  font: inherit;
  font-size: 0.8rem;
  font-weight: 700;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

button:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

.status-message,
.error-message {
  margin: 1rem 0 0;
  font-size: 0.82rem;
  line-height: 1.6;
}

.status-message {
  color: var(--text-secondary);
}

.error-message {
  color: #dc2626;
}
.notification-root {
  --notification-orange: #c2410c;
}

.notification-root .notification-toggle,
.notification-root .text-button,
.notification-root .footer-button {
  border: 1px solid var(--notification-orange);
  border-radius: 0.65rem;
  background: transparent;
  color: var(--notification-orange);
  text-decoration: none;
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.notification-root .text-button {
  padding: 0.5rem 0.7rem;
}

.notification-root .notification-toggle:hover:not(:disabled),
.notification-root .text-button:hover:not(:disabled),
.notification-root .footer-button:hover:not(:disabled) {
  background: rgb(194 65 12 / 10%);
  color: var(--notification-orange);
  text-decoration: none;
  box-shadow: 0 0.6rem 1rem rgb(194 65 12 / 20%);
  transform: translateY(-2px);
}

.notification-root .notification-toggle:active:not(:disabled),
.notification-root .text-button:active:not(:disabled),
.notification-root .footer-button:active:not(:disabled) {
  transform: scale(0.98);
}

.notification-root button:focus-visible {
  outline: 2px solid var(--notification-orange);
  outline-offset: 3px;
}
</style>
