<script setup>
import { computed, ref } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();

const loading = ref(false);
const completedAction = ref("");
const errorMessage = ref("");

const token = computed(() =>
  typeof route.query.token === "string" ? route.query.token : "",
);

async function updateReports(action) {
  if (
    loading.value ||
    !token.value ||
    !["unsubscribe", "resume"].includes(action)
  ) {
    return;
  }

  loading.value = true;
  errorMessage.value = "";

  try {
    const response = await fetch(
      `http://127.0.0.1:5000/api/parent-reports/${action}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: token.value,
          confirm: true,
        }),
      },
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Settings update hoyni.");
    }

    completedAction.value = action;
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "Abar try korun.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="unsubscribe-page">
    <section class="panel">
      <p class="eyebrow">ICT FOUNDATION COACH</p>
      <h1>Parent report preferences</h1>

      <p v-if="!token" class="error" role="alert">
        Parent report link missing. Email-er full link open korun.
      </p>

      <template v-else>
        <p>
          Ei student-er progress report emails bondho ba abar chalu korte
          parben. Student-er learning data change hobe na.
        </p>

        <p v-if="completedAction" class="success" role="status">
          {{
            completedAction === "resume"
              ? "Progress report emails abar enabled hoyeche."
              : "Progress report emails bondho hoyeche."
          }}
        </p>

        <p v-if="errorMessage" class="error" role="alert">
          {{ errorMessage }}
        </p>

        <div class="report-actions">
          <button
            type="button"
            :disabled="loading || completedAction === 'unsubscribe'"
            @click="updateReports('unsubscribe')"
          >
            Stop report emails
          </button>

          <button
            type="button"
            class="resume-button"
            :disabled="loading || completedAction === 'resume'"
            @click="updateReports('resume')"
          >
            Enable reports again
          </button>
        </div>

        <p v-if="loading" role="status">Settings update hocche…</p>
      </template>
    </section>
  </main>
</template>
<style scoped>
.unsubscribe-page {
  display: grid;
  place-items: center;
  min-height: 60vh;
  padding: 1rem;
}

.panel {
  width: 100%;
  max-width: 34rem;
  box-sizing: border-box;
  padding: 1.5rem;
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  background: var(--surface-color);
  color: var(--text-primary);
}

.eyebrow {
  color: var(--accent-color);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.08em;
}

h1 {
  margin: 0;
}

p {
  line-height: 1.7;
}

button {
  padding: 0.8rem 1rem;
  border: 0;
  border-radius: 0.65rem;
  background: #dc2626;
  color: white;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

button:hover:not(:disabled) {
  background: #b91c1c;
  box-shadow: 0 0.6rem 1rem rgb(220 38 38 / 20%);
  transform: translateY(-2px);
}

button:active:not(:disabled) {
  transform: scale(0.98);
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

button:focus-visible {
  outline: 2px solid #dc2626;
  outline-offset: 3px;
}

.error {
  color: #dc2626;
}

.success {
  color: #15803d;
}
.report-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

button.resume-button {
  background: #2450db;
}

button.resume-button:hover:not(:disabled) {
  background: #1d3fb8;
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
}

button.resume-button:focus-visible {
  outline-color: #2450db;
}
</style>
