<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";
import { useStore } from "vuex";
import NotificationPanel from "./components/NotificationPanel.vue";
import ConfirmDialog from "./components/ConfirmDialog.vue";

const router = useRouter();
const route = useRoute();
const store = useStore();

const showAppHeader = computed(() => {
  return ![
    "login",
    "register",
    "forgot-password",
    "reset-password",
    "verify-email",
  ].includes(route.name);
});

const logoutError = ref("");
const isSidebarExpanded = ref(true);
const shouldAnimateRoute = ref(false);

onMounted(() => {
  shouldAnimateRoute.value = true;
});

const savedTheme = localStorage.getItem("ict-coach-theme");
const theme = ref(savedTheme === "dark" ? "dark" : "light");

const isAuthenticated = computed(() => {
  return store.getters["auth/isAuthenticated"];
});

const currentUser = computed(() => {
  return store.state.auth.currentUser;
});
const isTeacher = computed(() => {
  return store.getters["auth/isTeacher"];
});

const isStudent = computed(() => {
  return store.getters["auth/isStudent"];
});

const dashboardPath = computed(() => {
  return isTeacher.value ? "/teacher" : "/dashboard";
});

const accountLabel = computed(() => {
  return isTeacher.value ? "TEACHER" : "STUDENT";
});

function toggleTheme() {
  theme.value = theme.value === "light" ? "dark" : "light";

  localStorage.setItem("ict-coach-theme", theme.value);
}

async function logout() {
  logoutError.value = "";

  try {
    await store.dispatch("auth/logout");
    router.push("/login");
  } catch (error) {
    logoutError.value = error.message;
  }
}
</script>

<template>
  <div
    class="app-shell"
    :class="{
      'dark-theme': theme === 'dark',
      'has-sidebar': showAppHeader,
      'sidebar-expanded': isSidebarExpanded,
    }"
  >
    <aside
      v-if="showAppHeader"
      class="app-sidebar"
      @mouseenter="isSidebarExpanded = true"
      @mouseleave="isSidebarExpanded = false"
    >
      <RouterLink :to="dashboardPath" class="brand">
        <span class="brand-icon">&lt;/&gt;</span>

        <span class="brand-text">
          <span class="app-label">ICT FOUNDATION COACH</span>
          <strong>Learning Space</strong>
        </span>
      </RouterLink>

      <nav class="sidebar-nav" aria-label="Main navigation">
        <template v-if="isTeacher">
          <RouterLink
            to="/teacher"
            class="sidebar-link"
            aria-label="Teacher dashboard"
            title="Teacher dashboard"
          >
            <span class="nav-icon" aria-hidden="true">⌂</span>
            <span class="nav-label">Dashboard</span>
          </RouterLink>

          <RouterLink
            :to="{ name: 'teacher-quizzes' }"
            class="sidebar-link"
            aria-label="Teacher quizzes"
            title="Teacher quizzes"
          >
            <span class="nav-icon" aria-hidden="true">▤</span>
            <span class="nav-label">Teacher Quizzes</span>
          </RouterLink>
          <RouterLink
            :to="{ name: 'teacher-learning-assignments' }"
            class="sidebar-link"
            aria-label="Learning assignments"
            title="Learning assignments"
          >
            <span class="nav-icon" aria-hidden="true">✎</span>
            <span class="nav-label">Learning Assignments</span>
          </RouterLink>
        </template>

        <template v-else-if="isStudent">
          <RouterLink
            :to="{ name: 'student-dashboard' }"
            class="sidebar-link"
            aria-label="Student dashboard"
            title="Dashboard"
          >
            <span class="nav-icon" aria-hidden="true">⌂</span>
            <span class="nav-label">Dashboard</span>
          </RouterLink>
          <RouterLink
            to="/"
            class="sidebar-link"
            aria-label="Tutor"
            title="Tutor"
          >
            <span class="nav-icon" aria-hidden="true">✦</span>
            <span class="nav-label">Tutor</span>
          </RouterLink>

          <RouterLink
            :to="{ name: 'quiz-practice' }"
            class="sidebar-link"
            aria-label="Quiz Practice"
            title="Quiz Practice"
          >
            <span class="nav-icon" aria-hidden="true">?</span>
            <span class="nav-label">Quiz Practice</span>
          </RouterLink>

          <RouterLink
            to="/classes"
            class="sidebar-link"
            aria-label="My classes"
            title="My classes"
          >
            <span class="nav-icon" aria-hidden="true">▤</span>
            <span class="nav-label">My Classes</span>
          </RouterLink>
          <RouterLink
            :to="{ name: 'student-assignments' }"
            class="sidebar-link"
            aria-label="Assigned quizzes"
            title="Assigned quizzes"
          >
            <span class="nav-icon" aria-hidden="true">✓</span>
            <span class="nav-label">Assigned Quizzes</span>
          </RouterLink>
          <RouterLink
            :to="{ name: 'student-learning-assignments' }"
            class="sidebar-link"
            aria-label="Learning assignments"
            title="Learning assignments"
          >
            <span class="nav-icon" aria-hidden="true">✎</span>
            <span class="nav-label">Learning Assignments</span>
          </RouterLink>
          <RouterLink
            :to="{ name: 'student-exam-results' }"
            class="sidebar-link"
            aria-label="Exam results"
            title="Exam results"
          >
            <span class="nav-icon" aria-hidden="true">▥</span>
            <span class="nav-label">Exam Results</span>
          </RouterLink>

          <RouterLink
            to="/progress"
            class="sidebar-link"
            aria-label="Progress"
            title="Progress"
          >
            <span class="nav-icon" aria-hidden="true">↗</span>
            <span class="nav-label">Progress</span>
          </RouterLink>
          <RouterLink
            to="/feedback"
            class="sidebar-link"
            aria-label="Teacher feedback"
            title="Teacher feedback"
          >
            <span class="nav-icon" aria-hidden="true">✉</span>
            <span class="nav-label">Feedback</span>
          </RouterLink>
          <RouterLink
            :to="{ name: 'parent-report-settings' }"
            class="sidebar-link"
            aria-label="Parent reports"
            title="Parent reports"
          >
            <span class="nav-icon" aria-hidden="true">♡</span>
            <span class="nav-label">Parent Reports</span>
          </RouterLink>
        </template>

        <template v-else-if="!isAuthenticated">
          <RouterLink to="/login" class="sidebar-link" aria-label="Log in">
            <span class="nav-icon" aria-hidden="true">→</span>
            <span class="nav-label">Log in</span>
          </RouterLink>

          <RouterLink to="/register" class="sidebar-link" aria-label="Register">
            <span class="nav-icon" aria-hidden="true">+</span>
            <span class="nav-label">Register</span>
          </RouterLink>
        </template>

        <RouterLink
          v-if="isAuthenticated && (isStudent || isTeacher)"
          :to="{ name: 'calendar' }"
          class="sidebar-link"
          aria-label="Calendar"
          title="Calendar"
        >
          <span class="nav-icon" aria-hidden="true">▦</span>
          <span class="nav-label">Calendar</span>
        </RouterLink>

        <RouterLink
          v-if="isAuthenticated && (isStudent || isTeacher)"
          :to="{ name: 'messages' }"
          class="sidebar-link"
          aria-label="Messages"
          title="Messages"
        >
          <span class="nav-icon" aria-hidden="true">☏</span>
          <span class="nav-label">Messages</span>
        </RouterLink>
      </nav>

      <div class="sidebar-bottom">
        <div v-if="isAuthenticated" class="user-summary">
          <span class="user-avatar">
            {{ currentUser?.name?.charAt(0) || "S" }}
          </span>

          <span class="user-details">
            <small>{{ accountLabel }}</small>
            <strong>{{ currentUser?.name }}</strong>
          </span>
        </div>

        <button
          type="button"
          class="sidebar-action"
          :aria-pressed="theme === 'dark'"
          @click="toggleTheme"
        >
          <span class="sidebar-action-icon">
            {{ theme === "dark" ? "☀" : "◐" }}
          </span>

          <span class="sidebar-action-label">
            {{ theme === "dark" ? "Light mode" : "Dark mode" }}
          </span>
        </button>

        <button
          v-if="isAuthenticated"
          type="button"
          class="sidebar-action logout-button"
          @click="logout"
        >
          <span class="sidebar-action-icon">↪</span>
          <span class="sidebar-action-label">Log out</span>
        </button>

        <p v-if="logoutError" class="logout-error">
          {{ logoutError }}
        </p>
      </div>
    </aside>

    <main class="app-content">
      <div v-if="showAppHeader && isAuthenticated" class="app-topbar">
        <NotificationPanel :key="currentUser?.id" />
      </div>

      <div class="page-transition-wrapper">
        <RouterView v-slot="{ Component, route: currentRoute }">
          <Transition name="page" mode="out-in" :css="shouldAnimateRoute">
            <component
              :is="Component"
              :key="
                ['login', 'register'].includes(currentRoute.name)
                  ? 'auth-screen'
                  : currentRoute.fullPath
              "
            />
          </Transition>
        </RouterView>
      </div>
    </main>

    <ConfirmDialog />
  </div>
</template>
<style scoped>
.app-shell {
  --page-background: #f5f7ff;
  --header-background: #ffffff;
  --surface-color: #ffffff;
  --text-primary: #172554;
  --text-secondary: #64748b;
  --border-color: #dbe5ff;
  --accent-color: #1d4ed8;
  --accent-hover: #1e40af;
  --nav-hover: #eaf0ff;

  min-height: 100vh;
  background: var(--page-background);
  color: var(--text-primary);
  transition:
    background-color 0.25s ease,
    color 0.25s ease;
}

.app-shell.has-sidebar {
  display: grid;
  min-width: 0;
  grid-template-columns: 4.75rem minmax(0, 1fr);
  transition: grid-template-columns 0.75s ease;
}

.app-shell.has-sidebar.sidebar-expanded {
  grid-template-columns: 16rem minmax(0, 1fr);
}

.dark-theme {
  --page-background: #071226;
  --header-background: #0d1b35;
  --surface-color: #132442;
  --text-primary: #f8fafc;
  --text-secondary: #b7c5dc;
  --border-color: #263d64;
  --accent-color: #77a5ff;
  --accent-hover: #a8c4ff;
  --nav-hover: #1b3156;
}

.app-sidebar {
  position: sticky;
  top: 0;
  display: flex;
  min-height: 100vh;
  overflow: hidden;
  flex-direction: column;
  padding: 1.5rem 1rem;
  background: #1428bd;
  color: white;
  box-shadow: 0.75rem 0 2rem rgb(15 23 42 / 8%);
}

.dark-theme .app-sidebar {
  background: #0b1b63;
}

.brand {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  width: 100%;
  box-sizing: border-box;
  padding: 0.35rem 0 2rem;
  color: white;
  text-decoration: none;
  white-space: nowrap;
}

.sidebar-expanded .brand {
  justify-content: flex-start;
  gap: 0.75rem;
  padding: 0.35rem 0.5rem 2rem;
}

.brand-icon {
  display: grid;
  width: 2.6rem;
  height: 2.6rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.8rem;
  background: #facc15;
  color: #172554;
  font-size: 0.78rem;
  font-weight: 900;
}

.brand-text {
  display: grid;
  gap: 0.18rem;
}

.app-label {
  color: rgb(255 255 255 / 72%);
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.09em;
}

.brand strong {
  font-size: 0.98rem;
}

.sidebar-nav {
  display: grid;
  gap: 0.45rem;
}

.sidebar-link,
.sidebar-action {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  width: 100%;
  box-sizing: border-box;
  border: 0;
  border-radius: 0.75rem;
  padding: 0.8rem 0.85rem;
  color: rgb(255 255 255 / 80%);
  background: transparent;
  cursor: pointer;
  font: inherit;
  font-size: 0.94rem;
  font-weight: 700;
  text-align: left;
  text-decoration: none;
  white-space: nowrap;
  transition:
    color 0.2s ease,
    background-color 0.2s ease,
    transform 0.2s ease;
}

.sidebar-expanded .sidebar-link,
.sidebar-expanded .sidebar-action {
  justify-content: flex-start;
  gap: 0.75rem;
}

.sidebar-link:hover,
.sidebar-link.router-link-active,
.sidebar-action:hover {
  color: #ffffff;
  background: rgb(255 255 255 / 17%);
  transform: translateX(3px);
}

.sidebar-link.router-link-active {
  background: #ffffff;
  color: #1d4ed8;
  box-shadow: 0 0.6rem 1.2rem rgb(15 23 42 / 16%);
}

.nav-icon,
.sidebar-action-icon {
  display: grid;
  width: 1.25rem;
  flex: 0 0 1.25rem;
  place-items: center;
  color: #facc15;
  font-size: 1.15rem;
  font-weight: 800;
}

.sidebar-link.router-link-active .nav-icon {
  color: #1d4ed8;
}

.brand-text,
.nav-label,
.sidebar-action-label,
.user-details {
  max-width: 0;
  overflow: hidden;
  opacity: 0;
  transform: translateX(-0.45rem);
  white-space: nowrap;
  transition:
    max-width 0.35s ease,
    opacity 0.2s ease,
    transform 0.3s ease;
}

.sidebar-expanded .brand-text,
.sidebar-expanded .nav-label,
.sidebar-expanded .sidebar-action-label,
.sidebar-expanded .user-details {
  max-width: 13rem;
  opacity: 1;
  transform: translateX(0);
}

.sidebar-bottom {
  display: grid;
  gap: 0.65rem;
  margin-top: auto;
}

.user-summary {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin-bottom: 0.35rem;
  padding: 0.8rem 0;
  border-top: 1px solid rgb(255 255 255 / 18%);
  white-space: nowrap;
}

.sidebar-expanded .user-summary {
  justify-content: flex-start;
  gap: 0.7rem;
  padding: 0.8rem 0.45rem;
}

.user-avatar {
  display: grid;
  width: 2rem;
  height: 2rem;
  flex: 0 0 2rem;
  place-items: center;
  border-radius: 50%;
  background: #facc15;
  color: #172554;
  font-size: 0.85rem;
  font-weight: 900;
}

.user-summary small,
.user-summary strong {
  display: block;
}

.user-summary small {
  color: rgb(255 255 255 / 60%);
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.user-summary strong {
  max-width: 10rem;
  overflow: hidden;
  margin-top: 0.15rem;
  font-size: 0.85rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.logout-button {
  color: #fecaca;
}

.logout-button:hover {
  color: #ffffff;
  background: rgb(220 38 38 / 75%);
}

.logout-error {
  margin: 0;
  color: #fecaca;
  font-size: 0.78rem;
  line-height: 1.4;
}

.app-content {
  width: min(100%, 1120px);
  margin: 0 auto;
  padding: 1.5rem;
}

.has-sidebar .app-content {
  width: 100%;
  max-width: 1440px;
  min-width: 0;
  box-sizing: border-box;
  margin: 0;
  padding: 2rem;
}

.page-transition-wrapper {
  position: relative;
  min-width: 0;
}

@media (max-width: 780px) {
  .app-shell.has-sidebar,
  .app-shell.has-sidebar.sidebar-expanded {
    display: block;
  }

  .app-sidebar {
    position: sticky;
    z-index: 10;
    min-height: auto;
    overflow: visible;
    padding: 0.8rem 1rem;
  }

  .brand,
  .sidebar-expanded .brand {
    justify-content: flex-start;
    gap: 0.75rem;
    padding: 0.2rem 0.35rem 0.85rem;
  }

  .sidebar-nav {
    display: flex;
    overflow-x: auto;
    padding-bottom: 0.15rem;
  }

  .sidebar-link,
  .sidebar-action,
  .sidebar-expanded .sidebar-link,
  .sidebar-expanded .sidebar-action {
    justify-content: flex-start;
    gap: 0.75rem;
    width: auto;
    flex: 0 0 auto;
  }

  .brand-text,
  .nav-label,
  .sidebar-action-label,
  .user-details {
    max-width: 13rem;
    opacity: 1;
    transform: none;
  }

  .sidebar-bottom {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    margin-top: 0.65rem;
  }

  .user-summary {
    display: none;
  }

  .has-sidebar .app-content {
    padding: 1.25rem;
  }
}
.app-topbar {
  position: relative;
  z-index: 20;
  display: flex;
  justify-content: flex-end;
  min-width: 0;
  margin-bottom: 1rem;
}
</style>

<style>
.page-enter-active {
  transition:
    opacity 0.45s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);
}

.page-leave-active {
  position: absolute;
  z-index: 1;
  inset: 0;
  width: 100%;
  pointer-events: none;
  transition:
    opacity 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.page-enter-from {
  opacity: 0;
  transform: translateY(26px) scale(0.99);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.995);
}

.quiz-button,
.quiz-link,
.recommendation-card a,
.chat-form button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0.45rem 1rem rgb(29 78 216 / 12%);
  transition:
    transform 0.22s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.22s ease,
    background-color 0.22s ease,
    color 0.22s ease;
}

.quiz-button:hover:not(:disabled),
.quiz-link:hover:not(:disabled),
.recommendation-card a:hover,
.chat-form button:hover:not(:disabled) {
  transform: translateY(-3px);
  box-shadow: 0 0.85rem 1.5rem rgb(29 78 216 / 22%);
}

.quiz-button:active:not(:disabled),
.quiz-link:active:not(:disabled),
.recommendation-card a:active,
.chat-form button:active:not(:disabled) {
  transform: translateY(1px) scale(0.97);
  box-shadow: 0 0.3rem 0.65rem rgb(29 78 216 / 14%);
}

@media (prefers-reduced-motion: reduce) {
  .quiz-button,
  .quiz-link,
  .recommendation-card a,
  .chat-form button {
    transition: none;
  }
}
</style>
