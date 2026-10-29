<script setup>
import TeacherLearningAssignmentForm from "../components/TeacherLearningAssignmentForm.vue";
import TeacherLearningAssignmentReviews from "../components/TeacherLearningAssignmentReviews.vue";
</script>

<template>
  <main class="learning-page">
    <header>
      <h1>Learning Assignments</h1>
      <p>
        Written ar practical task create koro, student submission review kore
        marks ar feedback dao.
      </p>
    </header>

    <TeacherLearningAssignmentForm />
    <TeacherLearningAssignmentReviews />
  </main>
</template>

<style scoped>
.learning-page {
  width: 100%;
  max-width: 1100px;
  margin: 0 auto;
  padding: 1.5rem;
  box-sizing: border-box;
}

header {
  margin-bottom: 1.5rem;
}

h1 {
  margin-top: 0;
}

p {
  line-height: 1.6;
  opacity: 0.8;
}

@media (max-width: 640px) {
  .learning-page {
    padding: 1rem;
  }
}
.learning-page :deep(button) {
  border: 1px solid #2450db;
  border-radius: 0.65rem;
  padding: 0.75rem 1rem;
  background: #2450db;
  color: #fff;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.learning-page :deep(button:hover:not(:disabled)) {
  border-color: #1d3fb8;
  background: #1d3fb8;
  color: #fff;
  box-shadow: 0 0.6rem 1rem rgb(30 64 175 / 20%);
  transform: translateY(-2px);
}

.learning-page :deep(button:active:not(:disabled)) {
  transform: scale(0.98);
}

.learning-page :deep(button:focus-visible) {
  outline: 2px solid #2450db;
  outline-offset: 3px;
}

.learning-page :deep(button:disabled) {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
