<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useStore } from "vuex";

const router = useRouter();
const store = useStore();

const classes = ref([]);
const className = ref("");
const isLoading = ref(false);
const isCreating = ref(false);
const loadError = ref("");
const createError = ref("");
const successMessage = ref("");
const copiedCode = ref("");

const teacherName = computed(() => {
  return store.state.auth.currentUser?.name || "Teacher";
});

async function requestClasses(options = {}) {
  const response = await fetch("http://127.0.0.1:5000/api/classes", {
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

  const data = await response.json();

  if (!response.ok) {
    const validationMessage = Object.values(data.messages || {})
      .flat()
      .find((message) => typeof message === "string");

    throw new Error(
      validationMessage || data.error || "Could not complete the request.",
    );
  }

  return data;
}

async function loadClasses() {
  if (isLoading.value) return;

  isLoading.value = true;
  loadError.value = "";

  try {
    const data = await requestClasses();
    classes.value = data.classes;
  } catch (error) {
    loadError.value =
      error instanceof Error ? error.message : "Could not load classes.";
  } finally {
    isLoading.value = false;
  }
}

async function createClass() {
  if (isCreating.value || isLoading.value) return;

  createError.value = "";
  successMessage.value = "";

  const name = className.value.trim();

  if (name.length < 2 || name.length > 100) {
    createError.value = "Class name must be between 2 and 100 characters.";
    return;
  }

  isCreating.value = true;

  try {
    const data = await requestClasses({
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ name }),
    });

    className.value = "";
    successMessage.value = `${data.classroom.name} created successfully.`;

    // Keep a previously failed list visible as an error until it is reloaded.
    if (loadError.value) {
      await loadClasses();
    } else {
      classes.value = [data.classroom, ...classes.value];
    }
  } catch (error) {
    createError.value =
      error instanceof Error ? error.message : "Could not create class.";
  } finally {
    isCreating.value = false;
  }
}
async function copyJoinCode(joinCode) {
  try {
    await navigator.clipboard.writeText(joinCode);
  } catch {
    const temporaryInput = document.createElement("textarea");

    temporaryInput.value = joinCode;
    temporaryInput.setAttribute("readonly", "");
    temporaryInput.style.position = "fixed";
    temporaryInput.style.opacity = "0";

    document.body.appendChild(temporaryInput);
    temporaryInput.select();

    document.execCommand("copy");
    temporaryInput.remove();
  }

  copiedCode.value = joinCode;

  window.setTimeout(() => {
    if (copiedCode.value === joinCode) {
      copiedCode.value = "";
    }
  }, 1800);
}
function viewClassAnalytics(classroomId) {
  router.push(`/teacher/classes/${classroomId}`);
}

onMounted(loadClasses);
</script>

<template>
  <section class="teacher-dashboard">
    <header class="dashboard-header">
      <p class="eyebrow">TEACHER DASHBOARD</p>
      <h1>Welcome, {{ teacherName }}</h1>
      <p class="intro">
        Tomar class create koro, ar join code student-der sathe share koro.
      </p>
    </header>

    <section class="class-panel" aria-labelledby="create-heading">
      <h2 id="create-heading">Create a class</h2>
      <p class="panel-description">
        Example: HSC ICT Batch A or Class 11 Section B.
      </p>

      <form class="create-form" @submit.prevent="createClass">
        <label for="class-name">Class name</label>

        <div class="form-row">
          <input
            id="class-name"
            v-model="className"
            type="text"
            placeholder="HSC ICT Batch A"
            minlength="2"
            maxlength="100"
            :disabled="isCreating"
            required
          />

          <button
            type="submit"
            class="primary-button"
            :disabled="isCreating || isLoading"
          >
            {{ isCreating ? "Creating..." : "Create class" }}
          </button>
        </div>

        <p v-if="createError" class="error-message" role="alert">
          {{ createError }}
        </p>

        <p v-if="successMessage" class="success-message" role="status">
          {{ successMessage }}
        </p>
      </form>
    </section>

    <section
      class="class-panel"
      aria-labelledby="class-heading"
      :aria-busy="isLoading"
    >
      <div class="panel-heading">
        <span class="class-icon" aria-hidden="true">▤</span>

        <div>
          <h2 id="class-heading">Your classes</h2>
          <p>Student-ra join code diye ei classes-e join korte parbe.</p>
        </div>
      </div>

      <p v-if="isLoading" class="status-note" role="status">
        Loading your classes...
      </p>

      <div v-else-if="loadError" class="status-note">
        <p class="error-message" role="alert">{{ loadError }}</p>

        <button
          type="button"
          class="secondary-button"
          :disabled="isCreating"
          @click="loadClasses"
        >
          Try again
        </button>
      </div>

      <div v-else-if="classes.length === 0" class="empty-state">
        <h3>Create your first class</h3>
        <p>
          Uporer form diye class create koro. Tarpor join code student-der dao.
        </p>
      </div>

      <TransitionGroup v-else name="class-card" tag="div" class="class-grid">
        <article
          v-for="classroom in classes"
          :key="classroom.id"
          class="class-card"
        >
          <h3>{{ classroom.name }}</h3>

          <div class="join-code">
            <span>JOIN CODE</span>

            <div class="join-code-row">
              <code>{{ classroom.join_code }}</code>

              <button
                type="button"
                class="copy-button"
                :aria-label="`Copy join code ${classroom.join_code}`"
                @click="copyJoinCode(classroom.join_code)"
              >
                {{ copiedCode === classroom.join_code ? "Copied!" : "Copy" }}
              </button>
            </div>
          </div>

          <p class="card-note">
            Ei code tomar class-er student-der sathe share koro.
          </p>

          <button
            type="button"
            class="analytics-button"
            @click="viewClassAnalytics(classroom.id)"
          >
            View analytics
          </button>
        </article>
      </TransitionGroup>
    </section>
  </section>
</template>

<style scoped>
.teacher-dashboard {
  display: grid;
  gap: 1.75rem;
  min-width: 0;
}

.eyebrow {
  margin: 0 0 0.65rem;
  color: var(--accent-color);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.1em;
}

h1 {
  margin: 0;
  color: var(--text-primary);
  font-size: clamp(1.75rem, 4vw, 2.5rem);
  line-height: 1.2;
  overflow-wrap: anywhere;
}

.intro,
.panel-description {
  margin: 0.85rem 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.class-panel {
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 1.1rem;
  padding: 1.5rem;
  background: var(--surface-color);
}

.panel-heading {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.class-icon {
  display: grid;
  flex: 0 0 auto;
  width: 2.75rem;
  height: 2.75rem;
  place-items: center;
  border-radius: 0.8rem;
  background: var(--nav-hover);
  color: var(--accent-color);
  font-size: 1.5rem;
}

h2,
h3 {
  margin: 0;
  color: var(--text-primary);
}

h2 {
  font-size: 1.15rem;
}

h3 {
  font-size: 1rem;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.panel-heading p {
  margin: 0.35rem 0 0;
  color: var(--text-secondary);
  font-size: 0.9rem;
  line-height: 1.5;
}

.create-form {
  display: grid;
  gap: 0.7rem;
  margin-top: 1.25rem;
}

.create-form label {
  color: var(--text-primary);
  font-size: 0.9rem;
  font-weight: 700;
}

.form-row {
  display: flex;
  gap: 0.75rem;
}

input,
button {
  font: inherit;
}

input {
  flex: 1;
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid var(--border-color);
  border-radius: 0.7rem;
  padding: 0.85rem 0.9rem;
  background: var(--page-background);
  color: var(--text-primary);
}

input:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
}

button {
  border: 1px solid transparent;
  border-radius: 0.7rem;
  padding: 0.85rem 1rem;
  cursor: pointer;
  font-weight: 700;
  transition:
    background-color 0.2s ease,
    transform 0.2s ease;
}

.primary-button {
  background: var(--accent-color);
  color: var(--surface-color);
  white-space: nowrap;
}

.primary-button:hover:not(:disabled) {
  background: var(--accent-hover);
}

.secondary-button {
  border-color: var(--border-color);
  background: var(--nav-hover);
  color: var(--accent-color);
}

button:active:not(:disabled) {
  transform: scale(0.97);
}

button:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 3px;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.error-message,
.success-message {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.6;
}

.error-message {
  color: #dc2626;
}

.success-message {
  color: var(--accent-color);
}

.status-note,
.empty-state {
  margin-top: 1.5rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.status-note .secondary-button {
  margin-top: 0.75rem;
}

.empty-state {
  border: 1px dashed var(--border-color);
  border-radius: 0.85rem;
  padding: 1.5rem;
  background: var(--page-background);
}

.empty-state p {
  margin: 0.65rem 0 0;
}

.class-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 16rem), 1fr));
  gap: 1rem;
  margin-top: 1.5rem;
}

.class-card {
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 0.85rem;
  padding: 1.25rem;
  background: var(--page-background);
}

.join-code {
  display: grid;
  gap: 0.5rem;
  margin-top: 1.25rem;
}

.join-code span {
  color: var(--text-secondary);
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.1em;
}

.join-code code {
  width: fit-content;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.5rem 0.7rem;
  background: var(--surface-color);
  color: var(--accent-color);
  font-size: 1.1rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  user-select: all;
}
.join-code-row {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  min-width: 0;
}

.copy-button {
  flex: 0 0 auto;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  padding: 0.5rem 0.7rem;
  background: var(--surface-color);
  color: var(--accent-color);
  font-size: 0.85rem;
}

.card-note {
  margin: 1rem 0 0;
  color: var(--text-secondary);
  font-size: 0.85rem;
  line-height: 1.6;
}

.class-card-enter-active,
.class-card-move {
  transition:
    opacity 0.35s ease,
    transform 0.35s ease;
}

.class-card-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

@media (max-width: 540px) {
  .class-panel,
  .empty-state {
    padding: 1rem;
  }

  .form-row {
    flex-direction: column;
  }
}

@media (prefers-reduced-motion: reduce) {
  button,
  .class-card-enter-active,
  .class-card-move {
    transition: none;
  }
}
.analytics-button {
  width: 100%;
  margin-top: 1rem;
  border-color: var(--border-color);
  background: var(--surface-color);
  color: var(--accent-color);
}

.analytics-button:hover {
  background: var(--nav-hover);
}
.teacher-dashboard button {
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.teacher-dashboard .primary-button {
  background: #2450db;
  color: #fff;
}

.teacher-dashboard .primary-button:hover:not(:disabled) {
  background: #1d3fb8;
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.teacher-dashboard .copy-button:hover:not(:disabled),
.teacher-dashboard .secondary-button:hover:not(:disabled) {
  border-color: #2450db;
  background: var(--nav-hover);
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.teacher-dashboard .analytics-button {
  border-color: #7c3aed;
  background: transparent;
  color: #7c3aed;
}

.teacher-dashboard .analytics-button:hover:not(:disabled) {
  background: rgb(124 58 237 / 10%);
  color: #7c3aed;
  box-shadow: 0 0.6rem 1rem rgb(124 58 237 / 20%);
  transform: translateY(-2px);
}

.teacher-dashboard .analytics-button:focus-visible {
  outline-color: #7c3aed;
}

.teacher-dashboard button:active:not(:disabled) {
  transform: scale(0.98);
}
</style>
