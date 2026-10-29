<script setup>
import StudentLearningAssignments from "../components/StudentLearningAssignments.vue";

defineProps({
  assignmentId: {
    type: String,
    default: "",
  },
});
</script>

<template>
  <main class="learning-page">
    <header>
      <h1>{{ assignmentId ? "Assignment Task" : "Learning Assignments" }}</h1>
      <p>
        {{
          assignmentId
            ? "Task-er instructions dekho, answer submit koro, ar teacher feedback dekho."
            : "Teacher-er written ar practical task dekho, answer submit koro, ar marks o feedback dekho."
        }}
      </p>
    </header>

    <StudentLearningAssignments
      :key="assignmentId || 'list'"
      :assignment-id="assignmentId"
    />
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
</style>
