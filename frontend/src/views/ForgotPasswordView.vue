<script setup>
import { ref } from "vue";
import { RouterLink } from "vue-router";

import learningIllustration from "../assets/login-learning-illustration.png";

const email = ref("");
const isLoading = ref(false);
const isSubmitted = ref(false);
const errorMessage = ref("");

async function sendResetLink() {
  if (isLoading.value) {
    return;
  }

  errorMessage.value = "";

  const submittedEmail = email.value.trim();

  if (!submittedEmail) {
    errorMessage.value = "Enter your email address.";
    return;
  }

  isLoading.value = true;

  try {
    const response = await fetch(
      "http://127.0.0.1:5000/api/auth/forgot-password",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: submittedEmail,
        }),
      },
    );

    const data = await response.json();

    if (!response.ok) {
      const emailErrors = data.messages?.email;

      const validationMessage = Array.isArray(emailErrors)
        ? emailErrors.join(" ")
        : "";

      throw new Error(
        validationMessage ||
          data.error ||
          "Could not send a reset link. Please try again.",
      );
    }

    isSubmitted.value = true;
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : "Could not send a reset link. Please try again.";
  } finally {
    isLoading.value = false;
  }
}

function editEmail() {
  isSubmitted.value = false;
  errorMessage.value = "";
}
</script>

<template>
  <section class="recovery-page">
    <aside class="recovery-showcase">
      <RouterLink class="brand" to="/login">
        <span class="brand-mark">&lt;/&gt;</span>

        <span>
          <strong>ICT FOUNDATION COACH</strong>
          <small>Banglish learning companion</small>
        </span>
      </RouterLink>

      <div class="showcase-content">
        <p class="showcase-label">GET BACK TO LEARNING</p>
        <h1>Your learning journey continues.</h1>
        <p>
          Reset your password and return to your tutor, quizzes, and learning
          progress.
        </p>
      </div>

      <img
        :src="learningIllustration"
        class="learning-illustration"
        alt=""
        aria-hidden="true"
      />
    </aside>

    <div class="recovery-panel">
      <Transition name="recovery" mode="out-in">
        <div v-if="!isSubmitted" key="form" class="recovery-card">
          <div class="recovery-icon" aria-hidden="true">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.7"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <rect x="6" y="10" width="12" height="10" rx="2" />
              <path d="M8 10V7a4 4 0 0 1 8 0v3" />
              <path d="M12 14v2" />
            </svg>
          </div>

          <p class="eyebrow">ACCOUNT RECOVERY</p>
          <h2>Forgot your password?</h2>
          <p class="intro">
            Enter your account email to receive a password reset link.
          </p>

          <form :aria-busy="isLoading" @submit.prevent="sendResetLink">
            <label for="recovery-email">Email address</label>

            <input
              id="recovery-email"
              v-model="email"
              type="email"
              autocomplete="email"
              placeholder="you@example.com"
              :disabled="isLoading"
              required
            />

            <p v-if="errorMessage" class="error-message" role="alert">
              {{ errorMessage }}
            </p>

            <button class="submit-button" type="submit" :disabled="isLoading">
              {{ isLoading ? "Sending..." : "Send reset link" }}
            </button>
          </form>

          <RouterLink class="back-link" to="/login">
            <span aria-hidden="true">←</span>
            Back to login
          </RouterLink>
        </div>

        <div v-else key="success" class="recovery-card">
          <div class="recovery-icon" aria-hidden="true">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.7"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <rect x="3" y="5" width="18" height="14" rx="2" />
              <path d="m3 6 9 7 9-7" />
            </svg>
          </div>

          <div role="status">
            <p class="eyebrow">NEXT STEP</p>
            <h2>Check your email</h2>
            <p class="intro">
              If an account exists with this email, you’ll receive a password
              reset link.
            </p>
          </div>

          <div class="delivery-note">
            <p>The link expires in 30 minutes.</p>
            <p>
              Check your inbox and spam folder. Delivery may take a little time.
            </p>
          </div>

          <button type="button" class="secondary-button" @click="editEmail">
            Use a different email
          </button>

          <RouterLink class="back-link" to="/login">
            <span aria-hidden="true">←</span>
            Back to login
          </RouterLink>
        </div>
      </Transition>
    </div>
  </section>
</template>

<style scoped>
.recovery-page {
  display: grid;
  grid-template-columns: 55% minmax(0, 1fr);
  min-height: 620px;
  overflow: hidden;
  border: 1px solid var(--border-color);
  border-radius: 1.5rem;
  background: var(--surface-color);
  box-shadow: 0 20px 60px rgb(30 64 175 / 12%);
}

.recovery-showcase {
  position: relative;
  min-width: 0;
  overflow: hidden;
  padding: 2rem;
  background:
    radial-gradient(circle at 85% 15%, rgb(255 218 107 / 28%), transparent 25%),
    radial-gradient(circle at 10% 85%, rgb(133 180 255 / 25%), transparent 28%),
    linear-gradient(145deg, #1d4ed8, #312e81);
  color: white;
}

.brand {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: fit-content;
  color: white;
  text-decoration: none;
}

.brand-mark {
  display: grid;
  flex: 0 0 auto;
  width: 2.5rem;
  height: 2.5rem;
  place-items: center;
  border-radius: 0.8rem;
  background: #fbbf24;
  color: #172554;
  font-weight: 800;
}

.brand strong,
.brand small {
  display: block;
}

.brand strong {
  font-size: 0.8rem;
  letter-spacing: 0.08em;
}

.brand small {
  margin-top: 0.2rem;
  color: rgb(255 255 255 / 75%);
  font-size: 0.75rem;
}

.showcase-content {
  position: relative;
  z-index: 1;
  max-width: 30rem;
  margin-top: 4.5rem;
}

.showcase-label,
.eyebrow {
  margin: 0;
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.showcase-label {
  color: #fde68a;
}

.showcase-content h1 {
  margin: 0.9rem 0;
  font-size: clamp(2rem, 4vw, 3.1rem);
  line-height: 1.12;
}

.showcase-content > p:last-child {
  max-width: 27rem;
  margin: 0;
  color: rgb(255 255 255 / 82%);
  line-height: 1.7;
}

.learning-illustration {
  display: block;
  width: min(85%, 26rem);
  height: 15rem;
  margin: 2rem 0 0 auto;
  object-fit: contain;
  object-position: bottom right;
}

.recovery-panel {
  display: grid;
  min-width: 0;
  align-items: center;
  padding: 2.5rem 2rem;
}

.recovery-card {
  width: 100%;
  max-width: 26rem;
  margin: 0 auto;
}

.recovery-icon {
  display: grid;
  width: 3.5rem;
  height: 3.5rem;
  margin-bottom: 1.5rem;
  place-items: center;
  border-radius: 1rem;
  background: var(--nav-hover);
  color: var(--accent-color);
}

.recovery-icon svg {
  width: 1.8rem;
  height: 1.8rem;
}

.eyebrow {
  color: var(--accent-color);
}

h2 {
  margin: 0.7rem 0;
  color: var(--text-primary);
  font-size: clamp(1.6rem, 3vw, 1.9rem);
  line-height: 1.2;
}

.intro {
  margin: 0 0 1.75rem;
  color: var(--text-secondary);
  line-height: 1.65;
}

form {
  display: grid;
  gap: 0.7rem;
}

label {
  color: var(--text-primary);
  font-size: 0.9rem;
  font-weight: 700;
}

input,
button {
  font: inherit;
}

input {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  border: 1px solid var(--border-color);
  border-radius: 0.7rem;
  padding: 0.85rem 0.9rem;
  background: var(--page-background);
  color: var(--text-primary);
}

input:focus {
  border-color: var(--accent-color);
  outline: none;
  box-shadow: 0 0 0 3px rgb(37 99 235 / 15%);
}

.submit-button,
.secondary-button {
  border-radius: 0.7rem;
  padding: 0.9rem 1rem;
  cursor: pointer;
  font-weight: 700;
  transition:
    background-color 0.2s ease,
    transform 0.2s ease;
}

.submit-button {
  margin-top: 0.6rem;
  border: 0;
  background: var(--accent-color);
  color: white;
}

.submit-button:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-1px);
}

.secondary-button {
  width: 100%;
  margin-top: 1.25rem;
  border: 1px solid var(--border-color);
  background: var(--surface-color);
  color: var(--accent-color);
}

.secondary-button:hover {
  background: var(--nav-hover);
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.error-message {
  margin: 0;
  border-radius: 0.55rem;
  padding: 0.75rem;
  background: rgb(220 38 38 / 12%);
  color: #dc2626;
  font-size: 0.9rem;
  line-height: 1.5;
}

.delivery-note {
  border: 1px solid var(--border-color);
  border-radius: 0.8rem;
  padding: 1rem;
  background: var(--page-background);
  color: var(--text-secondary);
  font-size: 0.9rem;
  line-height: 1.6;
}

.delivery-note p {
  margin: 0;
}

.delivery-note p + p {
  margin-top: 0.5rem;
}

.back-link {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  width: fit-content;
  margin: 1.5rem auto 0;
  border-radius: 0.25rem;
  color: var(--accent-color);
  font-size: 0.9rem;
  font-weight: 700;
  text-decoration: none;
}

.back-link:hover {
  text-decoration: underline;
}

button:focus-visible,
a:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 4px;
}

.recovery-enter-active,
.recovery-leave-active {
  transition:
    opacity 0.24s ease,
    transform 0.24s cubic-bezier(0.22, 1, 0.36, 1);
}

.recovery-enter-from {
  opacity: 0;
  transform: translateY(0.8rem);
}

.recovery-leave-to {
  opacity: 0;
  transform: translateY(-0.5rem);
}

@media (max-width: 850px) {
  .recovery-page {
    grid-template-columns: minmax(0, 1fr);
    min-height: auto;
  }

  .showcase-content {
    margin-top: 2rem;
  }

  .showcase-content h1 {
    font-size: 2rem;
  }

  .learning-illustration {
    height: 10rem;
    margin-top: 1rem;
  }
}

@media (max-width: 540px) {
  .recovery-page {
    border-radius: 1rem;
  }

  .recovery-showcase {
    padding: 1.5rem;
  }

  .learning-illustration {
    display: none;
  }

  .recovery-panel {
    padding: 2rem 1.25rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  .recovery-enter-active,
  .recovery-leave-active,
  .submit-button,
  .secondary-button {
    transition: none;
  }

  .recovery-enter-from,
  .recovery-leave-to {
    transform: none;
  }
}
</style>
