<script setup>
import StudentFeedback from "../components/StudentFeedback.vue";
</script>

<template>
  <section class="feedback-page">
    <header class="page-header">
      <p class="eyebrow">YOUR LEARNING SUPPORT</p>
      <h1>Teacher feedback</h1>
      <p class="intro">
        Tomar teacher-er advice ar quiz feedback ekhane dekhte parbe. Feedback
        onujayi practice kore learning improve koro.
      </p>
    </header>

    <StudentFeedback />
  </section>
</template>

<style scoped>
.feedback-page {
  display: grid;
  gap: 1.5rem;
  min-width: 0;
}

.eyebrow {
  margin: 0 0 0.65rem;
  color: var(--accent-color);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.1em;
}

h1 {
  margin: 0;
  color: var(--text-primary);
  font-size: clamp(1.75rem, 4vw, 2.5rem);
  line-height: 1.2;
  overflow-wrap: anywhere;
}

.intro {
  max-width: 42rem;
  margin: 0.85rem 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}
</style>
