<script setup>
import { useRoute } from "vue-router";
import TeacherQuizzesView from "./TeacherQuizzesView.vue";

const route = useRoute();
</script>

<template>
  <TeacherQuizzesView
    :key="String(route.params.quizId)"
    :review-quiz-id="String(route.params.quizId)"
  />
</template>
