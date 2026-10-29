<script setup>
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useStore } from "vuex";

import learningIllustration from "../assets/login-learning-illustration.png";

const route = useRoute();
const router = useRouter();
const store = useStore();

const name = ref("");
const email = ref("");
const password = ref("");
const role = ref("student");
const academicLevel = ref("");
const isPasswordVisible = ref(false);
const errorMessage = ref("");
const isLoading = ref(false);
const verificationEmail = ref("");
const verificationMessage = ref("");
const verificationError = ref("");
const isResending = ref(false);

const isRegister = computed(() => route.name === "register");

// Same starter blocklist as the backend, for immediate feedback.
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

  // Count Unicode characters rather than UTF-16 code units.
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

watch(
  () => route.name,
  () => {
    errorMessage.value = "";
    password.value = "";
    isPasswordVisible.value = false;
  },
);

function togglePasswordVisibility() {
  isPasswordVisible.value = !isPasswordVisible.value;
}

function getErrorText(error, fallback) {
  return error instanceof Error ? error.message : fallback;
}

function getRegistrationError(data) {
  if (data.messages && typeof data.messages === "object") {
    const fieldMessages = Object.values(data.messages)
      .flat()
      .filter((message) => typeof message === "string");

    if (fieldMessages.length) {
      return fieldMessages.join(" ");
    }
  }

  return data.error || "Registration failed.";
}

async function login() {
  if (isLoading.value) {
    return;
  }

  errorMessage.value = "";

  if (!email.value.trim() || !password.value) {
    errorMessage.value = "Email and password are required.";
    return;
  }

  isLoading.value = true;

  try {
    await store.dispatch("auth/login", {
      email: email.value.trim(),
      password: password.value,
    });

    await router.push({
      name:
        store.state.auth.currentUser?.role === "teacher"
          ? "teacher-dashboard"
          : "student-dashboard",
    });
  } catch (error) {
    errorMessage.value = getErrorText(error, "Login failed.");
  } finally {
    isLoading.value = false;
  }
}

async function register() {
  if (isLoading.value || isResending.value) {
    return;
  }

  errorMessage.value = "";
  verificationError.value = "";

  if (!name.value.trim() || !email.value.trim() || !password.value) {
    errorMessage.value = "Name, email, and password are required.";
    return;
  }

  if (
    role.value === "student" &&
    !["ssc", "hsc"].includes(academicLevel.value)
  ) {
    errorMessage.value = "Select SSC or HSC.";
    return;
  }

  const registrationEmail = email.value.trim();

  const registrationData = {
    name: name.value.trim(),
    email: registrationEmail,
    password: password.value,
    role: role.value,
  };

  if (role.value === "student") {
    registrationData.academic_level = academicLevel.value;
  }

  isLoading.value = true;

  try {
    const response = await fetch("http://127.0.0.1:5000/api/auth/register", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(registrationData),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(getRegistrationError(data));
    }

    verificationEmail.value = registrationEmail;
    verificationMessage.value =
      "Account created. Check your email and open the verification link before logging in.";

    password.value = "";
    academicLevel.value = "";
    isPasswordVisible.value = false;

    await router.push("/login");
  } catch (error) {
    errorMessage.value = getErrorText(error, "Registration failed.");
  } finally {
    isLoading.value = false;
  }
}

async function resendVerification() {
  if (isResending.value || isLoading.value) {
    return;
  }

  verificationError.value = "";

  const recipient = email.value.trim();

  if (!recipient) {
    verificationError.value = "Enter your email address first.";
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
        body: JSON.stringify({
          email: recipient,
        }),
      },
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        getRegistrationError(data) || "Could not resend verification email.",
      );
    }

    verificationEmail.value = recipient;
    verificationMessage.value =
      data.message ||
      "If an unverified account exists, you will receive a verification link.";
  } catch (error) {
    verificationError.value = getErrorText(
      error,
      "Could not resend verification email.",
    );
  } finally {
    isResending.value = false;
  }
}
</script>
<template>
  <section class="auth-page" :class="{ 'is-register': isRegister }">
    <div class="auth-shell">
      <section
        class="auth-showcase"
        aria-label="ICT Foundation Coach introduction"
      >
        <RouterLink class="brand" to="/">
          <span class="brand-mark">&lt;/&gt;</span>

          <span>
            <strong>ICT FOUNDATION COACH</strong>
            <small>Banglish learning companion</small>
          </span>
        </RouterLink>

        <div class="showcase-content">
          <p class="showcase-label">LEARN · PRACTICE · GROW</p>

          <h1>Build your ICT foundation with confidence.</h1>

          <p class="showcase-description">
            Simple Banglish explanations, mini quizzes, and guided practice for
            SSC and HSC students.
          </p>

          <ul class="feature-list">
            <li><span>✓</span> Ask your AI tutor when you are stuck</li>
            <li><span>✓</span> Practice topic-wise mini quizzes</li>
            <li><span>✓</span> Track your learning progress</li>
          </ul>
        </div>

        <img
          :src="learningIllustration"
          class="learning-illustration"
          alt="Laptop, code, books, chart, and learning tools"
        />
      </section>

      <section class="auth-panel">
        <div class="form-card">
          <Transition name="auth-form" mode="out-in">
            <div v-if="isRegister" key="register">
              <p class="eyebrow">START YOUR JOURNEY</p>
              <h2>Create your account</h2>
              <p class="intro">
                Tutor, mini quiz, ar progress tracking use korte first account
                create koro.
              </p>

              <form @submit.prevent="register">
                <fieldset class="role-selector" :disabled="isLoading">
                  <legend>I am joining as a</legend>

                  <div class="role-options">
                    <label
                      class="role-option"
                      :class="{ 'is-selected': role === 'student' }"
                    >
                      <input
                        v-model="role"
                        type="radio"
                        name="account-role"
                        value="student"
                      />

                      <span class="role-details">
                        <strong>Student</strong>
                        <small>Learn ICT and practice quizzes</small>
                      </span>
                    </label>

                    <label
                      class="role-option"
                      :class="{ 'is-selected': role === 'teacher' }"
                    >
                      <input
                        v-model="role"
                        type="radio"
                        name="account-role"
                        value="teacher"
                      />

                      <span class="role-details">
                        <strong>Teacher</strong>
                        <small>Monitor your class progress</small>
                      </span>
                    </label>
                  </div>
                </fieldset>

                <template v-if="role === 'student'">
                  <label for="academic-level">Study level</label>

                  <select
                    id="academic-level"
                    v-model="academicLevel"
                    class="study-level-select"
                    :disabled="isLoading"
                    required
                  >
                    <option value="" disabled>Select your study level</option>
                    <option value="ssc">SSC</option>
                    <option value="hsc">HSC</option>
                  </select>
                </template>

                <label for="name">Your name</label>
                <input
                  id="name"
                  v-model="name"
                  type="text"
                  autocomplete="name"
                  placeholder="Example: Saif Islam"
                  required
                />

                <label for="email">Email address</label>
                <input
                  id="email"
                  v-model="email"
                  type="email"
                  autocomplete="email"
                  placeholder="you@example.com"
                  required
                />

                <label for="password">Password</label>

                <div class="password-field">
                  <input
                    id="password"
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
                      isPasswordVisible ? 'Hide password' : 'Show password'
                    "
                    :aria-pressed="isPasswordVisible"
                    :disabled="isLoading"
                    @click="togglePasswordVisibility"
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
                      :class="{ filled: segment <= passwordStrength.segments }"
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

                <p v-if="errorMessage" class="error-message" role="alert">
                  {{ errorMessage }}
                </p>

                <button
                  type="submit"
                  class="submit-button"
                  :disabled="isLoading"
                >
                  {{
                    isLoading ? "Creating account..." : "Create your account"
                  }}
                </button>
              </form>

              <p class="switch-text">
                Already have an account?
                <RouterLink to="/login">Log in</RouterLink>
              </p>
            </div>

            <div v-else key="login">
              <div
                v-if="verificationMessage"
                class="verification-notice"
                role="status"
              >
                <strong>Check your email</strong>
                <p>{{ verificationMessage }}</p>
                <p v-if="verificationEmail" class="verification-address">
                  {{ verificationEmail }}
                </p>
              </div>
              <p class="eyebrow">WELCOME BACK</p>
              <h2>Log in to continue learning</h2>
              <p class="intro">
                Tomar tutor session, quiz, ar progress access korte log in koro.
              </p>

              <form @submit.prevent="login">
                <label for="email">Email address</label>
                <input
                  id="email"
                  v-model="email"
                  type="email"
                  autocomplete="email"
                  placeholder="you@example.com"
                  required
                />

                <label for="password">Password</label>

                <div class="password-field">
                  <input
                    id="password"
                    v-model="password"
                    :type="isPasswordVisible ? 'text' : 'password'"
                    autocomplete="current-password"
                    placeholder="Enter your password"
                    required
                  />

                  <button
                    type="button"
                    class="password-toggle"
                    :aria-label="
                      isPasswordVisible ? 'Hide password' : 'Show password'
                    "
                    :aria-pressed="isPasswordVisible"
                    @click="togglePasswordVisibility"
                  >
                    <span aria-hidden="true">
                      {{ isPasswordVisible ? "🔓" : "🔒" }}
                    </span>
                  </button>
                </div>

                <div class="forgot-password-row">
                  <RouterLink to="/forgot-password">
                    Forgot password?
                  </RouterLink>
                </div>
                <button
                  type="button"
                  class="verification-resend"
                  :disabled="isLoading || isResending"
                  @click="resendVerification"
                >
                  {{
                    isResending
                      ? "Sending verification email..."
                      : "Resend verification email"
                  }}
                </button>

                <p v-if="verificationError" class="error-message" role="alert">
                  {{ verificationError }}
                </p>

                <p v-if="errorMessage" class="error-message" role="alert">
                  {{ errorMessage }}
                </p>

                <button
                  type="submit"
                  class="submit-button"
                  :disabled="isLoading"
                >
                  {{ isLoading ? "Logging in..." : "Log in to your account" }}
                </button>
              </form>

              <p class="switch-text">
                New to ICT Foundation Coach?
                <RouterLink to="/register">Create an account</RouterLink>
              </p>
            </div>
          </Transition>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.auth-page {
  min-height: calc(100vh - 6rem);
  overflow: hidden;
  border: 1px solid var(--border-color);
  border-radius: 1.5rem;
  background: var(--surface-color);
  box-shadow: 0 20px 60px rgb(30 64 175 / 12%);
}

.auth-shell {
  position: relative;
  min-height: 620px;
}

.auth-showcase,
.auth-panel {
  position: absolute;
  top: 0;
  min-height: 100%;
  transition:
    left 0.7s cubic-bezier(0.22, 1, 0.36, 1),
    right 0.7s cubic-bezier(0.22, 1, 0.36, 1),
    width 0.7s cubic-bezier(0.22, 1, 0.36, 1);
}

.auth-showcase {
  left: 0;
  width: 55%;
  overflow: hidden;
  padding: 2rem;
  box-sizing: border-box;
  background:
    radial-gradient(circle at 85% 15%, rgb(255 218 107 / 28%), transparent 25%),
    radial-gradient(circle at 10% 85%, rgb(133 180 255 / 25%), transparent 28%),
    linear-gradient(145deg, #1d4ed8, #312e81);
  color: white;
}

.auth-showcase::after {
  position: absolute;
  right: -4rem;
  bottom: -5rem;
  width: 18rem;
  height: 18rem;
  border: 1.5rem solid rgb(255 255 255 / 10%);
  border-radius: 50%;
  content: "";
}

.auth-panel {
  right: 0;
  display: grid;
  width: 45%;
  place-items: center;
  padding: 2rem;
  box-sizing: border-box;
  background: var(--surface-color);
}

.is-register .auth-showcase {
  left: 45%;
}

.is-register .auth-panel {
  right: 55%;
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
  max-width: 32rem;
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
  font-size: clamp(2rem, 4vw, 3.3rem);
  line-height: 1.08;
}

.showcase-description {
  max-width: 30rem;
  margin: 0;
  color: rgb(255 255 255 / 82%);
  font-size: 1.02rem;
  line-height: 1.7;
}

.feature-list {
  display: grid;
  gap: 0.75rem;
  padding: 0;
  margin: 2rem 0 0;
  list-style: none;
}

.feature-list li {
  display: flex;
  gap: 0.65rem;
  align-items: center;
  color: rgb(255 255 255 / 92%);
  font-size: 0.92rem;
}

.feature-list span {
  display: grid;
  width: 1.35rem;
  height: 1.35rem;
  place-items: center;
  border-radius: 50%;
  background: rgb(255 255 255 / 16%);
  color: #fde68a;
  font-weight: 800;
}

.learning-illustration {
  position: absolute;
  z-index: 1;
  right: 1.5rem;
  bottom: 1rem;
  width: min(78%, 28rem);
  max-height: 18rem;
  object-fit: contain;
  object-position: bottom right;
}

.form-card {
  position: relative;
  width: min(100%, 26rem);
}

.eyebrow {
  color: var(--accent-color);
}

h2 {
  margin: 0.7rem 0;
  color: var(--text-primary);
  font-size: 1.9rem;
  line-height: 1.2;
}

.intro {
  margin: 0 0 2rem;
  color: var(--text-secondary);
  line-height: 1.6;
}

form {
  display: grid;
  gap: 0.7rem;
}

label {
  margin-top: 0.45rem;
  color: var(--text-primary);
  font-size: 0.9rem;
  font-weight: 700;
}

input,
button {
  font: inherit;
}

input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border-color);
  border-radius: 0.7rem;
  outline: none;
  padding: 0.85rem 0.9rem;
  background: var(--page-background);
  color: var(--text-primary);
}

input:focus {
  border-color: var(--accent-color);
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
  transition:
    background-color 0.2s ease,
    color 0.2s ease,
    transform 0.2s ease;
}

.password-toggle:hover {
  background: var(--nav-hover);
  color: var(--accent-color);
  transform: translateY(-50%) scale(1.08);
}

.password-toggle:active {
  transform: translateY(-50%) scale(0.94);
}

.submit-button {
  margin-top: 1rem;
  border: 0;
  border-radius: 0.7rem;
  padding: 0.9rem 1rem;
  background: var(--accent-color);
  color: white;
  cursor: pointer;
  font-weight: 700;
  transition:
    background-color 0.2s ease,
    transform 0.2s ease;
}

.submit-button:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: translateY(-1px);
}

.submit-button:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.error-message {
  margin: 0.5rem 0 0;
  border-radius: 0.55rem;
  padding: 0.7rem;
  background: rgb(220 38 38 / 12%);
  color: #dc2626;
  font-size: 0.9rem;
}

.switch-text {
  margin: 1.5rem 0 0;
  color: var(--text-secondary);
  font-size: 0.9rem;
  text-align: center;
}

.switch-text a {
  color: var(--accent-color);
  font-weight: 800;
  text-decoration: none;
}

.switch-text a:hover {
  text-decoration: underline;
}

.auth-form-enter-active,
.auth-form-leave-active {
  transition:
    opacity 0.24s ease,
    transform 0.24s cubic-bezier(0.22, 1, 0.36, 1);
}

.auth-form-enter-from {
  opacity: 0;
  transform: translateY(0.8rem);
}

.auth-form-leave-to {
  opacity: 0;
  transform: translateY(-0.5rem);
}

@media (max-width: 850px) {
  .auth-shell {
    display: grid;
    min-height: auto;
  }

  .auth-showcase,
  .auth-panel {
    position: relative;
    inset: auto;
    width: 100%;
    transition: none;
  }

  .auth-showcase {
    min-height: 330px;
  }

  .auth-panel {
    padding: 2.5rem 1.5rem;
  }

  .showcase-content {
    max-width: 65%;
    margin-top: 2.5rem;
  }

  .showcase-content h1 {
    font-size: 2rem;
  }

  .feature-list {
    display: none;
  }

  .learning-illustration {
    width: min(42%, 15rem);
  }
}

@media (max-width: 540px) {
  .auth-page {
    border-radius: 1rem;
  }

  .auth-showcase {
    min-height: 265px;
    padding: 1.5rem;
  }

  .showcase-content {
    max-width: 72%;
    margin-top: 2rem;
  }

  .showcase-description {
    display: none;
  }

  .learning-illustration {
    right: 0.5rem;
    width: 42%;
    max-height: 10rem;
  }

  .auth-panel {
    padding: 2rem 1.25rem;
  }
}
.role-selector {
  min-width: 0;
  margin: 0 0 0.5rem;
  border: 0;
  padding: 0;
}

.role-selector legend {
  margin-bottom: 0.7rem;
  padding: 0;
  color: var(--text-primary);
  font-size: 0.9rem;
  font-weight: 700;
}

.role-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.65rem;
}

.role-option {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  min-width: 0;
  margin: 0;
  border: 1px solid var(--border-color);
  border-radius: 0.75rem;
  padding: 0.8rem;
  background: var(--page-background);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    box-shadow 0.2s ease;
}

.role-option:hover,
.role-option.is-selected {
  border-color: var(--accent-color);
  background: var(--nav-hover);
}

.role-option:focus-within {
  box-shadow: 0 0 0 3px rgb(37 99 235 / 15%);
}

.role-option input {
  flex: 0 0 auto;
  width: 1rem;
  height: 1rem;
  margin: 0.15rem 0 0;
  padding: 0;
  accent-color: var(--accent-color);
  cursor: pointer;
}

.role-details {
  display: grid;
  gap: 0.3rem;
  min-width: 0;
}

.role-details strong {
  color: var(--text-primary);
  font-size: 0.9rem;
}

.role-details small {
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 400;
  line-height: 1.45;
}

.role-selector:disabled .role-option {
  cursor: not-allowed;
  opacity: 0.65;
}

/* Make room for the additional registration fields. */
.auth-page.is-register .auth-shell {
  min-height: 780px;
}

@media (max-width: 850px) {
  .auth-page.is-register .auth-shell {
    min-height: auto;
  }

  .auth-page.is-register .auth-showcase,
  .auth-page.is-register .auth-panel {
    inset: auto;
  }
}

@media (max-width: 380px) {
  .role-options {
    grid-template-columns: 1fr;
  }
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

.password-toggle:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.password-toggle:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
}

/* Extra room for the registration password feedback. */
.auth-page.is-register .auth-shell {
  min-height: 900px;
}

@media (max-width: 850px) {
  .auth-page.is-register .auth-shell {
    min-height: auto;
  }
}

@media (prefers-reduced-motion: reduce) {
  .strength-bars span {
    transition: none;
  }
}
.forgot-password-row {
  display: flex;
  justify-content: flex-end;
}

.forgot-password-row a {
  border-radius: 0.25rem;
  color: var(--accent-color);
  font-size: 0.85rem;
  font-weight: 700;
  text-decoration: none;
}

.forgot-password-row a:hover {
  text-decoration: underline;
}

.forgot-password-row a:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 4px;
}
.verification-notice {
  margin-bottom: 1.5rem;
  border: 1px solid var(--accent-color);
  border-radius: 0.8rem;
  padding: 1rem;
  background: var(--nav-hover);
  color: var(--text-primary);
}

.verification-notice strong {
  display: block;
  color: var(--accent-color);
}

.verification-notice p {
  margin: 0.5rem 0 0;
  font-size: 0.9rem;
  line-height: 1.6;
}

.verification-address {
  font-weight: 700;
  overflow-wrap: anywhere;
}

.verification-resend {
  justify-self: start;
  border: 0;
  border-radius: 0.3rem;
  padding: 0.25rem 0;
  background: transparent;
  color: var(--accent-color);
  font-size: 0.85rem;
  font-weight: 700;
  text-align: left;
  cursor: pointer;
}

.verification-resend:hover:not(:disabled) {
  text-decoration: underline;
}

.verification-resend:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.verification-resend:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 4px;
}
.study-level-select {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid var(--border-color);
  border-radius: 0.7rem;
  padding: 0.85rem 0.9rem;
  background: var(--page-background);
  color: var(--text-primary);
  font: inherit;
}

.study-level-select:focus {
  outline: 2px solid var(--accent-color);
  outline-offset: 2px;
}

.study-level-select:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}
/* Let the form determine the card height. */
.auth-panel {
  position: relative;
  top: auto;
  right: auto;
  margin-left: 55%;
  min-height: inherit;
  transition: margin-left 0.7s cubic-bezier(0.22, 1, 0.36, 1);
}

.is-register .auth-panel {
  right: auto;
  margin-left: 0;
}

.auth-showcase {
  bottom: 0;
}

@media (max-width: 850px) {
  .auth-panel,
  .is-register .auth-panel {
    margin-left: 0;
    min-height: auto;
    transition: none;
  }

  .auth-showcase {
    bottom: auto;
  }
}

@media (prefers-reduced-motion: reduce) {
  .auth-panel {
    transition: none;
  }
}
</style>
