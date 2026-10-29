<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useStore } from "vuex";

const router = useRouter();
const store = useStore();

const classes = ref([]);
const joinCode = ref("");
const isLoading = ref(false);
const isJoining = ref(false);
const leavingClassId = ref(null);
const confirmingClassId = ref(null);
const loadError = ref("");
const joinError = ref("");
const leaveError = ref("");
const successMessage = ref("");

const isBusy = computed(
  () => isLoading.value || isJoining.value || leavingClassId.value !== null,
);

async function requestClasses(path = "", options = {}) {
  const response = await fetch(`http://127.0.0.1:5000/api/classes${path}`, {
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
  if (isBusy.value) return;

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

async function joinClass() {
  if (isBusy.value) return;

  joinError.value = "";
  leaveError.value = "";
  successMessage.value = "";
  confirmingClassId.value = null;

  const code = joinCode.value.trim().toUpperCase();

  if (!/^[A-Z0-9]{8}$/.test(code)) {
    joinError.value = "Enter the 8-character code given by your teacher.";
    return;
  }

  let refreshNeeded = false;
  isJoining.value = true;

  try {
    const data = await requestClasses("/join", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ join_code: code }),
    });

    joinCode.value = "";
    successMessage.value = `You joined ${data.classroom.name}.`;
    refreshNeeded = Boolean(loadError.value);

    if (
      !classes.value.some((classroom) => classroom.id === data.classroom.id)
    ) {
      classes.value = [data.classroom, ...classes.value];
    }
  } catch (error) {
    joinError.value =
      error instanceof Error ? error.message : "Could not join class.";
  } finally {
    isJoining.value = false;
  }

  if (refreshNeeded) {
    await loadClasses();
  }
}

function confirmLeave(classroomId) {
  if (isBusy.value) return;

  confirmingClassId.value = classroomId;
  leaveError.value = "";
  successMessage.value = "";
}

async function leaveClass(classroom) {
  if (isBusy.value || confirmingClassId.value !== classroom.id) {
    return;
  }

  leavingClassId.value = classroom.id;
  leaveError.value = "";
  successMessage.value = "";

  try {
    await requestClasses(`/${classroom.id}/membership`, {
      method: "DELETE",
    });

    classes.value = classes.value.filter((item) => item.id !== classroom.id);

    confirmingClassId.value = null;
    successMessage.value = `You left ${classroom.name}. Your learning history is saved.`;
  } catch (error) {
    leaveError.value =
      error instanceof Error ? error.message : "Could not leave class.";
  } finally {
    leavingClassId.value = null;
  }
}

onMounted(loadClasses);
</script>

<template>
  <section class="student-classes" aria-labelledby="student-classes-heading">
    <h2 id="student-classes-heading">Your classes</h2>

    <p class="intro">
      Teacher-er code diye join korle tini tomar quiz progress dekhte parben.
    </p>

    <form class="join-form" @submit.prevent="joinClass">
      <label for="class-join-code">Class code</label>

      <div class="form-row">
        <input
          id="class-join-code"
          v-model="joinCode"
          type="text"
          placeholder="Example: A7K9M2PX"
          autocomplete="off"
          autocapitalize="characters"
          :spellcheck="false"
          :disabled="isBusy"
          required
        />

        <button type="submit" :disabled="isBusy">
          {{ isJoining ? "Joining..." : "Join class" }}
        </button>
      </div>

      <p v-if="joinError" class="error-message" role="alert">
        {{ joinError }}
      </p>
    </form>

    <p v-if="successMessage" class="success-message" role="status">
      {{ successMessage }}
    </p>

    <p v-if="leaveError" class="error-message leave-error" role="alert">
      {{ leaveError }}
    </p>

    <div class="class-list" :aria-busy="isLoading || leavingClassId !== null">
      <p v-if="isLoading" class="status-message" role="status">
        Loading your classes...
      </p>

      <div v-else-if="loadError">
        <p class="error-message" role="alert">{{ loadError }}</p>

        <button
          type="button"
          class="retry-button"
          :disabled="isBusy"
          @click="loadClasses"
        >
          Try again
        </button>
      </div>

      <p v-else-if="classes.length === 0" class="status-message">
        You have not joined a class yet. You can still use the tutor and
        quizzes.
      </p>

      <ul v-else>
        <li v-for="classroom in classes" :key="classroom.id">
          <div class="class-row">
            <span class="class-icon" aria-hidden="true">▤</span>

            <div class="class-info">
              <strong>{{ classroom.name }}</strong>
              <small>
                Teacher: {{ classroom.teacher_name || "Teacher" }}
              </small>
            </div>

            <button
              type="button"
              class="leave-button"
              :disabled="isBusy"
              :aria-label="`Leave ${classroom.name}`"
              @click="confirmLeave(classroom.id)"
            >
              Leave class
            </button>
          </div>

          <div
            v-if="confirmingClassId === classroom.id"
            class="leave-confirmation"
          >
            <p>
              Leave {{ classroom.name }}? Ei class-er maddhome teacher ar tomar
              progress dekhte parben na. Tomar quiz ar chat history saved
              thakbe.
            </p>

            <div class="confirmation-actions">
              <button
                type="button"
                class="leave-button"
                :disabled="isBusy"
                @click="leaveClass(classroom)"
              >
                {{
                  leavingClassId === classroom.id ? "Leaving..." : "Yes, leave"
                }}
              </button>

              <button
                type="button"
                class="cancel-button"
                :disabled="isBusy"
                @click="confirmingClassId = null"
              >
                Cancel
              </button>
            </div>
          </div>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.student-classes {
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 1.1rem;
  padding: 1.5rem;
  background: var(--surface-color);
}

h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.15rem;
}

.intro,
.status-message {
  color: var(--text-secondary);
  font-size: 0.9rem;
  line-height: 1.6;
}

.intro {
  margin: 0.65rem 0 1.25rem;
}

.join-form {
  display: grid;
  gap: 0.65rem;
}

label {
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

button {
  border: 0;
  border-radius: 0.7rem;
  padding: 0.85rem 1rem;
  background: var(--accent-color);
  color: var(--surface-color);
  cursor: pointer;
  font-weight: 700;
  white-space: nowrap;
  transition:
    background-color 0.2s ease,
    transform 0.2s ease;
}

button:hover:not(:disabled) {
  background: var(--accent-hover);
}

button:active:not(:disabled) {
  transform: scale(0.97);
}

input:focus-visible,
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
  margin-top: 0.75rem;
  color: var(--accent-color);
}

.leave-error {
  margin-top: 0.75rem;
}

.class-list {
  margin-top: 1.25rem;
}

.status-message {
  margin: 0;
}

.retry-button {
  margin-top: 0.75rem;
}

ul {
  display: grid;
  gap: 0.65rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

li {
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 0.75rem;
  padding: 0.9rem;
  background: var(--page-background);
  color: var(--text-primary);
}

.class-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.class-icon {
  color: var(--accent-color);
}

.class-info {
  flex: 1;
  min-width: 0;
}

.class-info strong {
  display: block;
  overflow-wrap: anywhere;
}

.class-info small {
  display: block;
  margin-top: 0.3rem;
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.leave-button {
  border: 1px solid #dc2626;
  background: transparent;
  color: #dc2626;
}

.leave-button:hover:not(:disabled) {
  background: rgb(220 38 38 / 10%);
}

.cancel-button {
  border: 1px solid var(--border-color);
  background: var(--surface-color);
  color: var(--text-primary);
}

.cancel-button:hover:not(:disabled) {
  background: var(--page-background);
}

.leave-confirmation {
  margin-top: 0.85rem;
  border-top: 1px solid var(--border-color);
  padding-top: 0.85rem;
}

.leave-confirmation p {
  margin: 0 0 0.75rem;
  color: var(--text-secondary);
  font-size: 0.9rem;
  line-height: 1.6;
}

.confirmation-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
}

@media (max-width: 540px) {
  .student-classes {
    padding: 1rem;
  }

  .form-row {
    flex-direction: column;
  }

  .class-row {
    flex-wrap: wrap;
  }

  .class-row > .leave-button {
    width: 100%;
  }
}

button {
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.join-form button {
  color: #fff;
}

.join-form button:hover:not(:disabled) {
  background: var(--accent-hover);
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.leave-button:hover:not(:disabled) {
  background: rgb(220 38 38 / 10%);
  box-shadow: 0 0.6rem 1rem rgb(220 38 38 / 20%);
  transform: translateY(-2px);
}

.join-form button:active:not(:disabled),
.leave-button:active:not(:disabled) {
  transform: scale(0.98);
}
</style>
