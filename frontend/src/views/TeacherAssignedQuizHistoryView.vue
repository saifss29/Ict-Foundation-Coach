<script setup>
import TeacherAssignedQuizzesView from "./TeacherAssignedQuizzesView.vue";
</script>

<template>
  <div class="history-page">
    <RouterLink class="back-link" :to="{ name: 'teacher-assigned-quizzes' }">
      ← Back to Assigned Quizzes
    </RouterLink>

    <TeacherAssignedQuizzesView :history-view="true" />
  </div>
</template>

<style scoped>
.history-page {
  display: grid;
  gap: 1.25rem;
  min-width: 0;
}

.back-link {
  justify-self: start;
  color: var(--accent-color);
  font-weight: 700;
  text-decoration: none;
}

.back-link:hover {
  text-decoration: underline;
}

.back-link:focus-visible {
  outline: 2px solid var(--accent-color);
  outline-offset: 4px;
}
</style>
