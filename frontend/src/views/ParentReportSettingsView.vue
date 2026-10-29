<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useStore } from "vuex";

const router = useRouter();
const store = useStore();

const parentEmail = ref("");
const preferences = ref(null);
const loading = ref(false);
const busy = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

let disposed = false;
let controller = null;

async function apiRequest(method = "GET", body = undefined) {
  const accessToken = store.state.auth.accessToken;

  if (!accessToken) {
    await router.push({ name: "login" });
    throw new Error("Abar login koro.");
  }

  controller = new AbortController();

  const response = await fetch(
    `http://127.0.0.1:5000/api/parent-reports${
      method === "POST" ? "/request-verification" : ""
    }`,
    {
      method,
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${accessToken}`,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    },
  );

  if (disposed || store.state.auth.accessToken !== accessToken) {
    throw new DOMException("Request cancelled", "AbortError");
  }

  if (response.status === 401) {
    store.commit("auth/CLEAR_AUTH");
    await router.push({ name: "login" });
    throw new Error("Session expire hoyeche. Abar login koro.");
  }

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || "Request complete kora jayni.");
  }

  return data;
}

function showError(error) {
  if (!disposed && error?.name !== "AbortError") {
    errorMessage.value =
      error instanceof Error ? error.message : "Abar try koro.";
  }
}

async function loadPreferences() {
  if (loading.value || busy.value) return;

  loading.value = true;
  errorMessage.value = "";

  try {
    const data = await apiRequest();

    if (!disposed) {
      preferences.value = data;
      parentEmail.value = data.parent_email || "";
    }
  } catch (error) {
    showError(error);
  } finally {
    if (!disposed) loading.value = false;
  }
}

async function requestVerification() {
  if (busy.value || loading.value || !preferences.value) return;

  busy.value = true;
  errorMessage.value = "";
  successMessage.value = "";

  try {
    await apiRequest("POST", {
      parent_email: parentEmail.value.trim(),
    });

    if (!disposed) {
      preferences.value = {
        parent_email: parentEmail.value.trim(),
        verified: false,
        enabled: false,
      };
      successMessage.value =
        "Verification email pathano hoyeche. Parent link open kore consent confirm korle reports enabled hobe.";
    }
  } catch (error) {
    showError(error);
  } finally {
    if (!disposed) busy.value = false;
  }
}

onMounted(loadPreferences);

onBeforeUnmount(() => {
  disposed = true;
  controller?.abort();
});
</script>

<template>
  <main class="parent-page">
    <header class="heading">
      <div>
        <p class="eyebrow">FAMILY LEARNING SUPPORT</p>
        <h1>Weekly Progress Reports</h1>
      </div>

      <button :disabled="loading || busy" @click="loadPreferences">
        {{ loading ? "Loading…" : "Refresh status" }}
      </button>
    </header>

    <section class="panel">
      <p>
        Parent-er email add koro. Email owner consent confirm korar por learning
        progress report automatic oi inbox-e jabe. Parent-er student account-e
        login korte hobe na.
      </p>

      <p v-if="loading" role="status">Settings load hocche…</p>
      <p v-if="errorMessage" class="error" role="alert">
        {{ errorMessage }}
      </p>
      <p v-if="successMessage" class="success" role="status">
        {{ successMessage }}
      </p>

      <template v-if="preferences">
        <p class="status">
          Status:
          <strong>
            {{
              preferences.verified
                ? preferences.enabled
                  ? "Enabled"
                  : "Disabled by parent"
                : preferences.parent_email
                  ? "Parent confirmation pending"
                  : "Not configured"
            }}
          </strong>
        </p>

        <p v-if="preferences.parent_email" class="saved-email">
          Saved email: {{ preferences.parent_email }}
        </p>

        <p v-if="preferences.verified" class="hint">
          Parent email verified. Ei email student change korte parbe na. Parent
          report email-er unsubscribe link diye delivery bondho korte parbe.
        </p>

        <form
          v-if="!preferences.verified"
          @submit.prevent="requestVerification"
        >
          <label for="parent-email">Parent/guardian email</label>
          <input
            id="parent-email"
            v-model="parentEmail"
            type="email"
            required
            maxlength="255"
            autocomplete="email"
            :disabled="busy || loading"
            placeholder="parent@example.com"
          />

          <p class="hint">
            Nijer parent/guardian-er permission niye email dao. Email change ba
            verification resend korle reports abar confirmation-er age bondho
            thakbe.
          </p>

          <div class="actions">
            <button type="submit" :disabled="busy || loading">
              {{ busy ? "Processing…" : "Send verification email" }}
            </button>

            <button
              v-if="preferences.parent_email"
              type="button"
              class="danger"
              :disabled="busy || loading"
              @click="disableReports"
            >
              Disable reports
            </button>
          </div>
        </form>
      </template>
    </section>
  </main>
</template>

<style scoped>
.parent-page {
  display: grid;
  gap: 1.5rem;
  min-width: 0;
  color: var(--text-primary);
}

.heading,
.actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.eyebrow {
  margin: 0 0 0.6rem;
  color: var(--accent-color);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.08em;
}

h1 {
  margin: 0;
  font-size: clamp(1.5rem, 4vw, 2.2rem);
}

.panel {
  padding: 1.5rem;
  border: 1px solid var(--border-color);
  border-radius: 1rem;
  background: var(--surface-color);
  min-width: 0;
}

p {
  line-height: 1.7;
}

form {
  display: grid;
  gap: 0.75rem;
  max-width: 36rem;
  margin-top: 1.25rem;
}

label {
  font-weight: 700;
}

input {
  box-sizing: border-box;
  width: 100%;
  padding: 0.8rem;
  border: 1px solid var(--border-color);
  border-radius: 0.65rem;
  background: var(--page-background);
  color: var(--text-primary);
  font: inherit;
}

.hint {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.saved-email {
  overflow-wrap: anywhere;
}

.actions {
  justify-content: flex-start;
}

button {
  padding: 0.75rem 1rem;
  border: 0;
  border-radius: 0.65rem;
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

button.danger {
  color: #dc2626;
  background: rgb(220 38 38 / 10%);
}

button.danger:hover:not(:disabled) {
  color: white;
  background: #dc2626;
  box-shadow: 0 0.6rem 1rem rgb(220 38 38 / 20%);
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

@media (max-width: 540px) {
  .panel {
    padding: 1rem;
  }
}
</style>
