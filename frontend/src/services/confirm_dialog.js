import { readonly, shallowRef } from "vue";

const currentDialog = shallowRef(null);
const queue = [];
let nextId = 1;

function showNext() {
  if (currentDialog.value || queue.length === 0) return;

  currentDialog.value = queue.shift();
}

export const confirmationState = readonly(currentDialog);

export function confirmAction({
  title = "Confirm korbe?",
  message = "",
  confirmText = "Confirm",
  cancelText = "Cancel",
  variant = "primary",
} = {}) {
  return new Promise((resolve) => {
    queue.push({
      id: nextId++,
      title,
      message,
      confirmText,
      cancelText,
      variant: ["primary", "danger", "warning"].includes(variant)
        ? variant
        : "primary",
      resolve,
    });

    showNext();
  });
}

export function settleConfirmation(accepted) {
  const dialog = currentDialog.value;
  if (!dialog) return;

  currentDialog.value = null;
  dialog.resolve(accepted === true);
  queueMicrotask(showNext);
}

export function cancelAllConfirmations() {
  const active = currentDialog.value;
  currentDialog.value = null;
  active?.resolve(false);

  for (const dialog of queue.splice(0)) {
    dialog.resolve(false);
  }
}
