<script setup>
import { computed, ref } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();

const consent = ref(false);
const loading = ref(false);
const success = ref(false);
const errorMessage = ref("");

const token = computed(() =>
  typeof route.query.token === "string" ? route.query.token : "",
);

async function confirmReports() {
  if (loading.value || success.value || !consent.value || !token.value) {
    return;
  }

  loading.value = true;
  errorMessage.value = "";

  try {
    const response = await fetch(
      "http://127.0.0.1:5000/api/parent-reports/verify",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          token: token.value,
          consent: true,
        }),
      },
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Verification complete kora jayni.");
    }

    success.value = true;
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : "Verification complete kora jayni. Abar try korun.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="verify-page">
    <section class="verify-card">
      <p class="eyebrow">ICT FOUNDATION COACH</p>
      <h1>Parent progress reports</h1>

      <template v-if="success">
        <p class="success" role="status">
          Email confirm hoyeche. Progress reports receive kora enabled.
        </p>
        <p>Ei page ekhon close korte paren.</p>
      </template>

      <template v-else-if="!token">
        <p class="error" role="alert">
          Verification link missing. Email-er full link open korun.
        </p>
      </template>

      <form v-else @submit.prevent="confirmReports">
        <p>
          Report-e student-er quiz progress, practice dorkar emon topics ar
          assignment progress thakbe. Summary AI diye generate hobe.
        </p>

        <p>
          Regular delivery weekly. Testing-er shomoy 5 minute porpor report aste
          pare. Parent report email-er unsubscribe link diye delivery bondho
          korte parben.
        </p>

        <label class="consent">
          <input v-model="consent" type="checkbox" :disabled="loading" />
          <span>
            Ami ei student-er progress receive korar authorised parent/guardian,
            ar ei email-e report receive korte agree korchi.
          </span>
        </label>

        <p v-if="errorMessage" class="error" role="alert">
          {{ errorMessage }}
        </p>

        <button type="submit" :disabled="!consent || loading">
          {{ loading ? "Confirm hocche…" : "Confirm and enable reports" }}
        </button>
      </form>
    </section>
  </main>
</template>

<style scoped>
.verify-page {
  display: grid;
  place-items: center;
  min-height: 60vh;
  padding: 1rem;
}

.verify-card {
  width: 100%;
  max-width: 36rem;
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
  overflow-wrap: anywhere;
}

.consent {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  margin: 1.25rem 0;
  line-height: 1.6;
}

input {
  margin-top: 0.3rem;
  flex-shrink: 0;
  accent-color: #2450db;
}

button {
  border: 0;
  border-radius: 0.65rem;
  padding: 0.8rem 1rem;
  background: #2450db;
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
  background: #1d3fb8;
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

button:active:not(:disabled) {
  transform: scale(0.98);
}

button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

button:focus-visible,
input:focus-visible {
  outline: 2px solid #2450db;
  outline-offset: 3px;
}

.error {
  color: #dc2626;
}

.success {
  color: #15803d;
}
</style>
