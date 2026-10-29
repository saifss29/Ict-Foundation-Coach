<script setup>
import { onBeforeUnmount, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useStore } from "vuex";
import { confirmAction } from "../services/confirm_dialog";
const props = defineProps({
  classroomId: {
    type: [String, Number],
    required: true,
  },
  studentId: {
    type: [String, Number],
    required: true,
  },
  studentName: {
    type: String,
    required: true,
  },
});

const router = useRouter();
const store = useStore();

const open = ref(false);
const email = ref("");
const busy = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

let controller = null;
let requestVersion = 0;

function resetForm() {
  requestVersion += 1;
  controller?.abort();
  open.value = false;
  email.value = "";
  busy.value = false;
  errorMessage.value = "";
  successMessage.value = "";
}

async function submitCorrection() {
  if (busy.value) return;

  const recipient = email.value.trim();

  const accepted = await confirmAction({
    title: "Change parent email?",
    message:
      `Change the parent email for ${props.studentName} to ${recipient}?\n\n` +
      "Reports will remain disabled until the new email owner verifies their email and confirms consent.",
    confirmText: "Change email",
    cancelText: "Cancel",
    variant: "warning",
  });

  if (!accepted) return;

  const accessToken = store.state.auth.accessToken;
  const version = ++requestVersion;

  controller = new AbortController();
  busy.value = true;
  errorMessage.value = "";
  successMessage.value = "";

  try {
    if (!accessToken) {
      await router.replace("/login");
      return;
    }

    const response = await fetch(
      `http://127.0.0.1:5000/api/parent-reports/classes/${encodeURIComponent(
        props.classroomId,
      )}/students/${encodeURIComponent(props.studentId)}/email`,
      {
        method: "POST",
        signal: controller.signal,
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ parent_email: recipient }),
      },
    );

    if (
      version !== requestVersion ||
      store.state.auth.accessToken !== accessToken
    ) {
      return;
    }

    if (response.status === 401) {
      store.commit("auth/CLEAR_AUTH");
      await router.replace("/login");
      return;
    }

    const data = await response.json();

    if (version !== requestVersion) return;

    if (!response.ok) {
      throw new Error(data.error || "Parent email correction hoyni.");
    }

    successMessage.value =
      "Notun email-e verification link pathano hoyeche. Parent consent confirm korar age reports off thakbe.";
    email.value = "";
  } catch (error) {
    if (version !== requestVersion || error?.name === "AbortError") return;

    errorMessage.value =
      error instanceof Error ? error.message : "Abar try koro.";
  } finally {
    if (version === requestVersion) busy.value = false;
  }
}

watch(() => [props.classroomId, props.studentId], resetForm);

onBeforeUnmount(resetForm);
</script>

<template>
  <section class="parent-correction">
    <button
      type="button"
      :disabled="busy"
      :aria-expanded="open"
      @click="open = !open"
    >
      {{ open ? "Close parent email form" : "Correct parent email" }}
    </button>

    <form v-if="open" @submit.prevent="submitCorrection">
      <p>
        {{ studentName }}-er parent/guardian-er sathe confirm kore notun email
        dao. Ei change shudhu parent report delivery-r jonno.
      </p>

      <label :for="`parent-correction-${studentId}`"> New parent email </label>

      <input
        :id="`parent-correction-${studentId}`"
        v-model="email"
        type="email"
        required
        maxlength="255"
        autocomplete="off"
        :disabled="busy"
        placeholder="parent@example.com"
      />

      <p v-if="errorMessage" class="error" role="alert">
        {{ errorMessage }}
      </p>

      <p v-if="successMessage" class="success" role="status">
        {{ successMessage }}
      </p>

      <button type="submit" :disabled="busy || !email.trim()">
        {{ busy ? "Sending…" : "Send new verification link" }}
      </button>
    </form>
  </section>
</template>

<style scoped>
.parent-correction {
  display: grid;
  justify-items: start;
  gap: 0.75rem;
  min-width: 0;
}

form {
  display: grid;
  gap: 0.75rem;
  width: 100%;
  max-width: 36rem;
}

p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
  overflow-wrap: anywhere;
}

label {
  color: var(--text-primary);
  font-weight: 700;
}

input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.8rem;
  border: 1px solid var(--border-color);
  border-radius: 0.65rem;
  background: var(--surface-color);
  color: var(--text-primary);
  font: inherit;
}

button {
  justify-self: start;
  padding: 0.75rem 1rem;
  border: 1px solid #2450db;
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
