<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";

import learningIllustration from "../assets/login-learning-illustration.png";

const route = useRoute();

const status = ref("loading");
const message = ref("");
const email = ref("");
const resendMessage = ref("");
const resendError = ref("");
const isResending = ref(false);

const heading = computed(() => {
  if (status.value === "success") {
    return "Email verified";
  }

  if (status.value === "error") {
    return "Could not verify your email";
  }

  return "Verifying your email";
});

function getErrorText(error, fallback) {
  return error instanceof Error ? error.message : fallback;
}

function getResponseError(data, fallback) {
  if (data.messages && typeof data.messages === "object") {
    const messages = Object.values(data.messages)
      .flat()
      .filter((item) => typeof item === "string");

    if (messages.length) {
      return messages.join(" ");
    }
  }

  return typeof data.error === "string" ? data.error : fallback;
}

async function verifyEmail() {
  const token = route.query.token;

  if (typeof token !== "string" || !token.trim()) {
    status.value = "error";
    message.value =
      "This link is missing a verification token. Request a new email below.";
    return;
  }

  try {
    const response = await fetch(
      "http://127.0.0.1:5000/api/auth/verify-email",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ token }),
      },
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        getResponseError(data, "This verification link is invalid or expired."),
      );
    }

    status.value = "success";
    message.value =
      data.message || "Your email is verified. You can now log in.";
  } catch (error) {
    status.value = "error";
    message.value = getErrorText(
      error,
      "Could not verify your email. Please try again later.",
    );
  }
}

async function resendVerification() {
  if (isResending.value) {
    return;
  }

  resendMessage.value = "";
  resendError.value = "";

  const recipient = email.value.trim();

  if (!recipient) {
    resendError.value = "Enter your email address.";
    return;
  }

  isResending.value = true;

  try {
    const response = await fetch(
      "http://127.0.0.1:5000/api/auth/resend-verification",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email: recipient }),
      },
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        getResponseError(data, "Could not send a verification email."),
      );
    }

    resendMessage.value =
      data.message ||
      "If an unverified account exists, you will receive a verification link.";
  } catch (error) {
    resendError.value = getErrorText(
      error,
      "Could not send a verification email.",
    );
  } finally {
    isResending.value = false;
  }
}

onMounted(verifyEmail);
</script>

<template>
  <section class="verification-page">
    <div class="verification-showcase">
      <RouterLink class="brand" to="/login">
        <span class="brand-mark">&lt;/&gt;</span>
        <span>ICT FOUNDATION COACH</span>
      </RouterLink>

      <div class="showcase-copy">
        <p class="eyebrow">ONE MORE STEP</p>
        <h1>Your learning journey starts here.</h1>
        <p>
          Verify your email to access your account and continue with ICT
          Foundation Coach.
        </p>
      </div>

      <img
        :src="learningIllustration"
        class="learning-illustration"
        alt=""
        aria-hidden="true"
      />
    </div>

    <div class="verification-panel">
      <div class="verification-card">
        <div class="status-icon" :class="status" aria-hidden="true">
          {{ status === "success" ? "✓" : status === "error" ? "!" : "…" }}
        </div>

        <p class="eyebrow">EMAIL VERIFICATION</p>
        <h2>{{ heading }}</h2>

        <p
          class="status-message"
          :role="status === 'error' ? 'alert' : 'status'"
          aria-live="polite"
        >
          {{
            status === "loading"
              ? "Please wait while we check your verification link."
              : message
          }}
        </p>

        <form
          v-if="status === 'error'"
          class="resend-form"
          @submit.prevent="resendVerification"
        >
          <label for="verification-email">Email address</label>

          <input
            id="verification-email"
            v-model="email"
            type="email"
            autocomplete="email"
            placeholder="you@example.com"
            :disabled="isResending"
            required
          />

          <p v-if="resendMessage" class="notice-message" role="status">
            {{ resendMessage }}
          </p>

          <p v-if="resendError" class="error-message" role="alert">
            {{ resendError }}
          </p>

          <button type="submit" :disabled="isResending">
            {{ isResending ? "Sending..." : "Send a new verification link" }}
          </button>
        </form>

        <RouterLink v-if="status !== 'loading'" class="login-link" to="/login">
          {{ status === "success" ? "Continue to log in" : "Back to log in" }}
        </RouterLink>
      </div>
    </div>
  </section>
</template>

<style scoped>
.verification-page {
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: calc(100vh - 6rem);
  overflow: hidden;
  border: 1px solid var(--border-color);
  border-radius: 1.5rem;
  background: var(--surface-color);
}

.verification-showcase {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 600px;
  box-sizing: border-box;
  padding: 2rem;
  background: #1428bd;
  color: white;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: white;
  font-size: 0.8rem;
  font-weight: 800;
  text-decoration: none;
}

.brand-mark {
  display: grid;
  flex: 0 0 auto;
  width: 2.5rem;
  height: 2.5rem;
  place-items: center;
  border-radius: 0.8rem;
  background: #facc15;
  color: #172554;
}

.showcase-copy {
  position: relative;
  z-index: 1;
  margin-top: 4rem;
}

.eyebrow {
  margin: 0;
  color: var(--accent-color);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.1em;
}

.showcase-copy .eyebrow {
  color: #fde68a;
}

h1 {
  margin: 0.9rem 0;
  font-size: clamp(2rem, 4vw, 3rem);
  line-height: 1.15;
}

.showcase-copy > p:last-child {
  max-width: 27rem;
  color: rgb(255 255 255 / 82%);
  line-height: 1.7;
}

.learning-illustration {
  align-self: center;
  width: min(100%, 24rem);
  max-height: 16rem;
  margin-top: auto;
  padding-top: 2rem;
  object-fit: contain;
}

.verification-panel {
  display: grid;
  min-width: 0;
  place-items: center;
  padding: 2.5rem;
}

.verification-card {
  width: min(100%, 26rem);
}

.status-icon {
  display: grid;
  width: 3.5rem;
  height: 3.5rem;
  margin-bottom: 1.5rem;
  place-items: center;
  border-radius: 1rem;
  background: var(--nav-hover);
  color: var(--accent-color);
  font-size: 1.8rem;
  font-weight: 800;
}

.status-icon.success {
  background: rgb(22 163 74 / 12%);
  color: #16a34a;
}

.status-icon.error {
  background: rgb(220 38 38 / 12%);
  color: #dc2626;
}

h2 {
  margin: 0.75rem 0;
  color: var(--text-primary);
  font-size: 1.9rem;
  line-height: 1.2;
}

.status-message {
  color: var(--text-secondary);
  line-height: 1.7;
}

.resend-form {
  display: grid;
  gap: 0.8rem;
  margin-top: 1.5rem;
}

label {
  color: var(--text-primary);
  font-size: 0.9rem;
  font-weight: 700;
}

input,
button {
  box-sizing: border-box;
  width: 100%;
  border-radius: 0.7rem;
  padding: 0.9rem;
  font: inherit;
}

input {
  border: 1px solid var(--border-color);
  background: var(--page-background);
  color: var(--text-primary);
}

input:focus {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
}

button {
  border: 0;
  background: var(--accent-color);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

button:hover:not(:disabled) {
  background: var(--accent-hover);
}

button:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.notice-message,
.error-message {
  margin: 0;
  border-radius: 0.6rem;
  padding: 0.8rem;
  font-size: 0.9rem;
  line-height: 1.6;
}

.notice-message {
  background: var(--nav-hover);
  color: var(--text-primary);
}

.error-message {
  background: rgb(220 38 38 / 12%);
  color: #dc2626;
}

.login-link {
  display: inline-block;
  margin-top: 1.5rem;
  color: var(--accent-color);
  font-weight: 700;
  text-decoration: none;
}

.login-link:hover {
  text-decoration: underline;
}

button:focus-visible,
.login-link:focus-visible,
.brand:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 4px;
}

@media (max-width: 800px) {
  .verification-page {
    grid-template-columns: 1fr;
  }

  .verification-showcase {
    min-height: auto;
  }

  .showcase-copy {
    margin-top: 2rem;
  }

  .learning-illustration {
    display: none;
  }

  .verification-panel {
    padding: 2rem 1.5rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  button {
    transition: none;
  }
}
</style>
