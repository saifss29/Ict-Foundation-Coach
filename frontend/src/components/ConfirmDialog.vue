<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from "vue";
import {
  confirmationState,
  settleConfirmation,
  cancelAllConfirmations,
} from "../services/confirm_dialog";

const dialogElement = ref(null);
const cancelButton = ref(null);

watch(
  () => confirmationState.value?.id,
  async () => {
    await nextTick();

    const element = dialogElement.value;
    if (!element) return;

    if (confirmationState.value) {
      if (!element.open) element.showModal();
      cancelButton.value?.focus();
    } else if (element.open) {
      element.close();
    }
  },
  { flush: "post" },
);

function cancel() {
  settleConfirmation(false);
}

function handleBackdrop(event) {
  const element = dialogElement.value;
  if (!element || event.target !== element) return;

  const bounds = element.getBoundingClientRect();
  const outside =
    event.clientX < bounds.left ||
    event.clientX > bounds.right ||
    event.clientY < bounds.top ||
    event.clientY > bounds.bottom;

  if (outside) cancel();
}

onBeforeUnmount(cancelAllConfirmations);
</script>

<template>
  <dialog
    ref="dialogElement"
    class="confirm-dialog"
    aria-labelledby="confirmation-title"
    aria-describedby="confirmation-message"
    @cancel.prevent="cancel"
    @click="handleBackdrop"
  >
    <section
      v-if="confirmationState"
      :key="confirmationState.id"
      class="dialog-content"
      :class="confirmationState.variant"
    >
      <button
        class="close-button"
        type="button"
        aria-label="Cancel and close"
        @click="cancel"
      >
        ×
      </button>

      <div class="dialog-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none">
          <path
            v-if="confirmationState.variant === 'danger'"
            d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 10v7M14 10v7"
          />
          <path
            v-else-if="confirmationState.variant === 'warning'"
            d="M12 3 2 21h20L12 3ZM12 9v5M12 17v.5"
          />
          <path v-else d="M9 12l2 2 4-4M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z" />
        </svg>
      </div>

      <h2 id="confirmation-title">{{ confirmationState.title }}</h2>
      <p id="confirmation-message">{{ confirmationState.message }}</p>

      <div class="dialog-actions">
        <button
          ref="cancelButton"
          type="button"
          class="cancel-button"
          @click="cancel"
        >
          {{ confirmationState.cancelText }}
        </button>

        <button
          type="button"
          class="confirm-button"
          @click="settleConfirmation(true)"
        >
          {{ confirmationState.confirmText }}
        </button>
      </div>
    </section>
  </dialog>
</template>

<style scoped>
.confirm-dialog {
  --dialog-accent: #2450db;
  --dialog-hover: #1d3fb8;
  --dialog-tint: rgb(36 80 219 / 10%);
  width: min(28rem, calc(100vw - 2rem));
  max-height: calc(100dvh - 2rem);
  box-sizing: border-box;
  padding: 0;
  overflow-y: auto;
  border: 1px solid var(--border-color, #dbe1ee);
  border-radius: 1.2rem;
  background: var(--surface-color, #fff);
  color: var(--text-primary, #172544);
  box-shadow: 0 1.5rem 5rem rgb(0 0 0 / 25%);
}

.confirm-dialog::backdrop {
  background: rgb(10 20 40 / 45%);
  backdrop-filter: blur(4px);
}

.dialog-content {
  position: relative;
  padding: 2rem;
  text-align: center;
  animation: dialog-in 0.2s ease;
}

.danger {
  --dialog-accent: #dc2626;
  --dialog-hover: #b91c1c;
  --dialog-tint: rgb(220 38 38 / 10%);
}

.warning {
  --dialog-accent: #d97706;
  --dialog-hover: #b45309;
  --dialog-tint: rgb(217 119 6 / 10%);
}

.dialog-icon {
  display: grid;
  place-items: center;
  width: 4rem;
  height: 4rem;
  margin: 0 auto 1.2rem;
  border-radius: 50%;
  background: var(--dialog-tint);
  color: var(--dialog-accent);
}

svg {
  width: 2rem;
  height: 2rem;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

h2 {
  margin: 0;
  font-size: 1.35rem;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

p {
  margin: 0.8rem 0 1.5rem;
  color: var(--text-secondary, #64748b);
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.dialog-actions {
  display: flex;
  gap: 0.75rem;
}

button {
  padding: 0.8rem 1rem;
  border: 1px solid transparent;
  border-radius: 0.7rem;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.dialog-actions button {
  flex: 1;
}

.cancel-button {
  border-color: var(--border-color, #dbe1ee);
  background: var(--page-background, #f5f7ff);
  color: var(--text-primary, #172544);
}

.cancel-button:hover {
  background: var(--nav-hover, #e8edff);
  transform: translateY(-2px);
}

.confirm-button {
  background: var(--dialog-accent);
  color: #fff;
}

.confirm-button:hover {
  background: var(--dialog-hover);
  box-shadow: 0 0.6rem 1rem rgb(0 0 0 / 15%);
  transform: translateY(-2px);
}

.close-button {
  position: absolute;
  top: 0.6rem;
  right: 0.6rem;
  padding: 0.25rem 0.65rem;
  background: transparent;
  color: var(--text-secondary, #64748b);
  font-size: 1.5rem;
}

.close-button:hover {
  background: var(--nav-hover, #e8edff);
}

button:active {
  transform: scale(0.98);
}

button:focus-visible {
  outline: 2px solid var(--dialog-accent);
  outline-offset: 3px;
}

@keyframes dialog-in {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (max-width: 420px) {
  .dialog-content {
    padding: 1.5rem 1rem;
  }

  .dialog-actions {
    flex-direction: column;
  }
}

@media (prefers-reduced-motion: reduce) {
  .dialog-content {
    animation: none;
  }

  button {
    transition: none;
  }
}
</style>
