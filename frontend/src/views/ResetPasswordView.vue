<script setup>
import { computed, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { useStore } from "vuex";

import learningIllustration from "../assets/login-learning-illustration.png";

const route = useRoute();
const store = useStore();

const password = ref("");
const confirmPassword = ref("");
const isPasswordVisible = ref(false);
const isLoading = ref(false);
const isSubmitted = ref(false);
const errorMessage = ref("");

const resetToken = computed(() => {
  const token = route.query.token;

  return typeof token === "string" ? token : "";
});

const commonPasswords = new Set([
  "password",
  "password1",
  "password123",
  "password123!",
  "12345678",
  "123456789",
  "1234567890",
  "qwerty123",
  "qwerty123!",
  "abcdefgh",
  "abcdefgh123",
  "letmein123",
  "welcome123",
  "welcome123!",
  "admin123",
  "admin1234",
  "iloveyou",
]);

const passwordStrength = computed(() => {
  const value = password.value;
  const comparison = value.trim().toLowerCase();
  const length = Array.from(value).length;
  const distinctCharacters = new Set(Array.from(comparison)).size;

  if (length > 128) {
    return {
      label: "Too long",
      tone: "weak",
      segments: 1,
      hint: "Use no more than 128 characters.",
    };
  }

  if (!comparison) {
    return {
      label: "Weak",
      tone: "weak",
      segments: 1,
      hint: "A password cannot contain only spaces.",
    };
  }

  if (commonPasswords.has(comparison) || distinctCharacters === 1) {
    return {
      label: "Weak",
      tone: "weak",
      segments: 1,
      hint: "Avoid common passwords and repeated characters.",
    };
  }

  if (length < 8) {
    return {
      label: "Weak",
      tone: "weak",
      segments: 1,
      hint: "Use at least 8 characters. A longer passphrase is better.",
    };
  }

  if (length < 12 || distinctCharacters < 5 || /^\d+$/.test(comparison)) {
    return {
      label: "Weak",
      tone: "weak",
      segments: 1,
      hint: "Try a longer, less predictable phrase.",
    };
  }

  if (length < 16 || distinctCharacters < 8) {
    return {
      label: "Medium",
      tone: "medium",
      segments: 2,
      hint: "Add more unrelated words to make it longer.",
    };
  }

  return {
    label: "Strong",
    tone: "strong",
    segments: 3,
    hint: "Keep it unique. Avoid names, birthdays, and familiar phrases.",
  };
});

async function resetPassword() {
  if (isLoading.value || isSubmitted.value) {
    return;
  }

  errorMessage.value = "";

  if (!resetToken.value) {
    errorMessage.value = "This reset link is missing its token.";
    return;
  }

  const passwordLength = Array.from(password.value).length;

  if (passwordLength < 8 || passwordLength > 128) {
    errorMessage.value = "Password must be between 8 and 128 characters.";
    return;
  }

  if (password.value !== confirmPassword.value) {
    errorMessage.value = "Passwords do not match.";
    return;
  }

  isLoading.value = true;

  try {
    const response = await fetch(
      "http://127.0.0.1:5000/api/auth/reset-password",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          token: resetToken.value,
          password: password.value,
        }),
      },
    );

    const data = await response.json();

    if (!response.ok) {
      const validationMessages =
        data.messages && typeof data.messages === "object"
          ? Object.values(data.messages)
              .flat()
              .filter((value) => typeof value === "string")
              .join(" ")
          : "";

      throw new Error(
        validationMessages ||
          data.error ||
          "Could not reset your password. Please try again.",
      );
    }

    store.commit("auth/CLEAR_AUTH");

    password.value = "";
    confirmPassword.value = "";
    isPasswordVisible.value = false;
    isSubmitted.value = true;
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : "Could not reset your password. Please try again.";
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <section class="reset-page">
    <aside class="reset-showcase">
      <RouterLink class="brand" to="/login">
        <span class="brand-mark">&lt;/&gt;</span>

        <span>
          <strong>ICT FOUNDATION COACH</strong>
          <small>Banglish learning companion</small>
        </span>
      </RouterLink>

      <div class="showcase-content">
        <p class="showcase-label">A FRESH START</p>
        <h1>Get back to your learning journey.</h1>
        <p>
          Choose a new password and continue learning with your tutor, quizzes,
          and saved progress.
        </p>
      </div>

      <img
        :src="learningIllustration"
        class="learning-illustration"
        alt=""
        aria-hidden="true"
      />
    </aside>

    <div class="reset-panel">
      <Transition name="reset-form" mode="out-in">
        <div v-if="isSubmitted" key="success" class="reset-card">
          <div class="reset-icon" aria-hidden="true">✓</div>

          <div role="status">
            <p class="eyebrow">PASSWORD UPDATED</p>
            <h2>You’re ready to log in</h2>
            <p class="intro">
              Your password has been reset. Log in with your new password to
              continue.
            </p>
          </div>

          <RouterLink class="primary-link" to="/login">
            Back to login
          </RouterLink>
        </div>

        <div v-else-if="!resetToken" key="missing-token" class="reset-card">
          <p class="eyebrow">ACCOUNT RECOVERY</p>
          <h2>Incomplete reset link</h2>
          <p class="intro">
            Open the complete link from your email, or request a new password
            reset link.
          </p>

          <RouterLink class="primary-link" to="/forgot-password">
            Request a new link
          </RouterLink>

          <RouterLink class="back-link" to="/login">
            ← Back to login
          </RouterLink>
        </div>

        <div v-else key="form" class="reset-card">
          <div class="reset-icon" aria-hidden="true">
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
          <h2>Set a new password</h2>
          <p class="intro">
            Choose a long, unique password you don’t use elsewhere.
          </p>

          <form :aria-busy="isLoading" @submit.prevent="resetPassword">
            <label for="new-password">New password</label>

            <div class="password-field">
              <input
                id="new-password"
                v-model="password"
                :type="isPasswordVisible ? 'text' : 'password'"
                autocomplete="new-password"
                placeholder="Minimum 8 characters"
                aria-describedby="password-guidance"
                :disabled="isLoading"
                required
              />

              <button
                type="button"
                class="password-toggle"
                :aria-label="
                  isPasswordVisible ? 'Hide passwords' : 'Show passwords'
                "
                :aria-pressed="isPasswordVisible"
                :disabled="isLoading"
                @click="isPasswordVisible = !isPasswordVisible"
              >
                <span aria-hidden="true">
                  {{ isPasswordVisible ? "🔓" : "🔒" }}
                </span>
              </button>
            </div>

            <div
              v-if="password.length"
              class="password-strength"
              :class="passwordStrength.tone"
            >
              <div class="strength-heading">
                <span>Password strength estimate</span>
                <strong>{{ passwordStrength.label }}</strong>
              </div>

              <div class="strength-bars" aria-hidden="true">
                <span
                  v-for="segment in 3"
                  :key="segment"
                  :class="{
                    filled: segment <= passwordStrength.segments,
                  }"
                ></span>
              </div>
            </div>

            <p id="password-guidance" class="password-guidance">
              {{
                password.length
                  ? passwordStrength.hint
                  : "Use a long, unique passphrase. Minimum 8 characters."
              }}
            </p>

            <label for="confirm-password">Confirm new password</label>

            <input
              id="confirm-password"
              v-model="confirmPassword"
              :type="isPasswordVisible ? 'text' : 'password'"
              autocomplete="new-password"
              placeholder="Enter your new password again"
              :disabled="isLoading"
              required
            />

            <p v-if="errorMessage" class="error-message" role="alert">
              {{ errorMessage }}
            </p>

            <button type="submit" class="submit-button" :disabled="isLoading">
              {{ isLoading ? "Updating..." : "Reset password" }}
            </button>
          </form>

          <RouterLink class="back-link" to="/forgot-password">
            Request a new reset link
          </RouterLink>

          <RouterLink class="back-link" to="/login">
            ← Back to login
          </RouterLink>
        </div>
      </Transition>
    </div>
  </section>
</template>

<style scoped>
.reset-page {
  display: grid;
  grid-template-columns: 55% minmax(0, 1fr);
  min-height: 620px;
  overflow: hidden;
  border: 1px solid var(--border-color);
  border-radius: 1.5rem;
  background: var(--surface-color);
  box-shadow: 0 20px 60px rgb(30 64 175 / 12%);
}

.reset-showcase {
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

.reset-panel {
  display: grid;
  min-width: 0;
  align-items: center;
  padding: 2.5rem 2rem;
}

.reset-card {
  width: 100%;
  max-width: 26rem;
  margin: 0 auto;
}

.reset-icon {
  display: grid;
  width: 3.5rem;
  height: 3.5rem;
  margin-bottom: 1.5rem;
  place-items: center;
  border-radius: 1rem;
  background: var(--nav-hover);
  color: var(--accent-color);
  font-size: 1.8rem;
}

.reset-icon svg {
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

.password-field {
  position: relative;
}

.password-field input {
  padding-right: 3.4rem;
}

.password-toggle {
  position: absolute;
  top: 50%;
  right: 0.45rem;
  display: grid;
  width: 2.4rem;
  height: 2.4rem;
  place-items: center;
  border: 0;
  border-radius: 0.55rem;
  padding: 0;
  transform: translateY(-50%);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}

.password-toggle:hover:not(:disabled) {
  background: var(--nav-hover);
}

.password-strength {
  display: grid;
  gap: 0.5rem;
  margin-top: 0.1rem;
}

.strength-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.4rem;
  font-size: 0.76rem;
}

.strength-heading span {
  color: var(--text-secondary);
}

.strength-heading strong {
  color: var(--text-primary);
  font-weight: 800;
}

.strength-bars {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.4rem;
}

.strength-bars span {
  height: 0.35rem;
  border-radius: 1rem;
  background: var(--border-color);
  transition: background-color 0.2s ease;
}

.password-strength.weak .filled {
  background: #dc2626;
}

.password-strength.medium .filled {
  background: #d97706;
}

.password-strength.strong .filled {
  background: #16a34a;
}

.password-guidance {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.76rem;
  line-height: 1.5;
}

.submit-button,
.primary-link {
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  width: 100%;
  margin-top: 0.75rem;
  border: 0;
  border-radius: 0.7rem;
  padding: 0.9rem 1rem;
  background: var(--accent-color);
  color: white;
  cursor: pointer;
  font-weight: 700;
  text-decoration: none;
  transition:
    background-color 0.2s ease,
    transform 0.2s ease;
}

.submit-button:hover:not(:disabled),
.primary-link:hover {
  background: var(--accent-hover);
  transform: translateY(-1px);
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

.back-link {
  display: block;
  width: fit-content;
  margin: 1.25rem auto 0;
  border-radius: 0.25rem;
  color: var(--accent-color);
  font-size: 0.9rem;
  font-weight: 700;
  text-align: center;
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

.reset-form-enter-active,
.reset-form-leave-active {
  transition:
    opacity 0.24s ease,
    transform 0.24s cubic-bezier(0.22, 1, 0.36, 1);
}

.reset-form-enter-from {
  opacity: 0;
  transform: translateY(0.8rem);
}

.reset-form-leave-to {
  opacity: 0;
  transform: translateY(-0.5rem);
}

@media (max-width: 850px) {
  .reset-page {
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
  .reset-page {
    border-radius: 1rem;
  }

  .reset-showcase {
    padding: 1.5rem;
  }

  .learning-illustration {
    display: none;
  }

  .reset-panel {
    padding: 2rem 1.25rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  .reset-form-enter-active,
  .reset-form-leave-active,
  .submit-button,
  .primary-link,
  .strength-bars span {
    transition: none;
  }

  .reset-form-enter-from,
  .reset-form-leave-to {
    transform: none;
  }
}
</style>
