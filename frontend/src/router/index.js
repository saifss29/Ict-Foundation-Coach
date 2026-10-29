import { createRouter, createWebHistory } from "vue-router";

import store from "../store";
import AuthView from "../views/AuthView.vue";
import HomeView from "../views/HomeView.vue";
import ProgressView from "../views/ProgressView.vue";
import QuizView from "../views/QuizView.vue";
import TeacherClassAnalyticsView from "../views/TeacherClassAnalyticsView.vue";
import TeacherDashboardView from "../views/TeacherDashboardView.vue";
import TeacherStudentAttemptHistoryView from "../views/TeacherStudentAttemptHistoryView.vue";
import ForgotPasswordView from "../views/ForgotPasswordView.vue";
import ResetPasswordView from "../views/ResetPasswordView.vue";
import VerifyEmailView from "../views/VerifyEmailView.vue";
import StudentFeedbackView from "../views/StudentFeedbackView.vue";
import StudentClassesView from "../views/StudentClassesView.vue";

const router = createRouter({
  history: createWebHistory(),

  routes: [
    {
      path: "/dashboard",
      name: "student-dashboard",
      component: () => import("../views/StudentDashboardView.vue"),
      meta: {
        requiresAuth: true,
        role: "student",
      },
    },
    {
      path: "/",
      name: "home",
      component: HomeView,
      meta: {
        requiresAuth: true,
        role: "student",
      },
    },
    {
      path: "/login",
      name: "login",
      component: AuthView,
    },
    {
      path: "/practice",
      name: "quiz-practice",
      component: () => import("../views/QuizPracticeView.vue"),
      meta: {
        requiresAuth: true,
        role: "student",
      },
    },
    {
      path: "/register",
      name: "register",
      component: AuthView,
    },
    {
      path: "/forgot-password",
      name: "forgot-password",
      component: ForgotPasswordView,
    },
    {
      path: "/reset-password",
      name: "reset-password",
      component: ResetPasswordView,
    },
    {
      path: "/verify-email",
      name: "verify-email",
      component: VerifyEmailView,
    },
    {
      path: "/teacher",
      name: "teacher-dashboard",
      component: TeacherDashboardView,
      meta: {
        requiresAuth: true,
        role: "teacher",
      },
    },
    {
      path: "/teacher/quizzes",
      name: "teacher-quizzes",
      component: () => import("../views/TeacherQuizzesView.vue"),
      meta: {
        requiresAuth: true,
        role: "teacher",
      },
    },
    {
      path: "/teacher/quizzes/:quizId/review",
      name: "teacher-quiz-review",
      component: () => import("../views/TeacherQuizReviewView.vue"),
      meta: {
        requiresAuth: true,
        role: "teacher",
      },
    },
    {
      path: "/teacher/classes/:classroomId",
      name: "teacher-class-analytics",
      component: TeacherClassAnalyticsView,
      meta: {
        requiresAuth: true,
        role: "teacher",
      },
    },
    {
      path: "/teacher/classes/:classroomId/students/:studentId/attempts",
      name: "teacher-student-attempt-history",
      component: TeacherStudentAttemptHistoryView,
      meta: {
        requiresAuth: true,
        role: "teacher",
      },
    },
    {
      path: "/messages/:conversationId?",
      name: "messages",
      component: () => import("../views/MessagesView.vue"),
      meta: {
        requiresAuth: true,
      },
    },
    {
      path: "/quiz/:slug",
      name: "quiz",
      component: QuizView,
      meta: {
        requiresAuth: true,
        role: "student",
      },
    },
    {
      path: "/progress",
      name: "progress",
      component: ProgressView,
      meta: {
        requiresAuth: true,
        role: "student",
      },
    },
    {
      path: "/feedback",
      name: "student-feedback",
      component: StudentFeedbackView,
      meta: {
        requiresAuth: true,
        role: "student",
      },
    },
    {
      path: "/classes",
      name: "student-classes",
      component: StudentClassesView,
      meta: {
        requiresAuth: true,
        role: "student",
      },
    },
    {
      path: "/assignments",
      name: "student-assignments",
      component: () => import("../views/StudentAssignmentsView.vue"),
      meta: {
        requiresAuth: true,
        role: "student",
      },
    },
    {
      path: "/calendar",
      name: "calendar",
      component: () => import("../views/CalendarView.vue"),
      meta: {
        requiresAuth: true,
      },
    },
    {
      path: "/exam-results",
      name: "student-exam-results",
      component: () => import("../views/StudentExamResultsView.vue"),
      meta: {
        requiresAuth: true,
        role: "student",
      },
    },
    {
      path: "/teacher/learning-assignments",
      name: "teacher-learning-assignments",
      component: () => import("../views/TeacherLearningAssignmentsView.vue"),
      meta: {
        requiresAuth: true,
        role: "teacher",
      },
    },
    {
      path: "/learning-assignments",
      name: "student-learning-assignments",
      component: () => import("../views/StudentLearningAssignmentsView.vue"),
      meta: {
        requiresAuth: true,
        role: "student",
      },
    },
    {
      path: "/learning-assignments/:assignmentId",
      name: "student-learning-assignment-task",
      component: () => import("../views/StudentLearningAssignmentsView.vue"),
      props: (route) => ({
        assignmentId: String(route.params.assignmentId),
      }),
      meta: {
        requiresAuth: true,
        role: "student",
      },
    },
    {
      path: "/teacher/assigned-quizzes",
      name: "teacher-assigned-quizzes",
      component: () => import("../views/TeacherAssignedQuizzesView.vue"),
      meta: {
        requiresAuth: true,
        role: "teacher",
      },
    },
    {
      path: "/teacher/quizzes/history",
      name: "teacher-quiz-history",
      component: () => import("../views/TeacherQuizHistoryView.vue"),
      meta: {
        requiresAuth: true,
        role: "teacher",
      },
    },
    {
      path: "/assignments/history",
      name: "student-assignment-history",
      component: () => import("../views/StudentAssignmentHistoryView.vue"),
      meta: {
        requiresAuth: true,
        role: "student",
      },
    },
    {
      path: "/assignments/:assignmentId/play",
      name: "student-assignment-play",
      component: () => import("../views/StudentAssignmentsView.vue"),
      props: (route) => ({
        screen: "play",
        assignmentId: String(route.params.assignmentId),
        quizTitle:
          typeof route.query.title === "string" ? route.query.title : "",
        historyView: route.query.from === "history",
      }),
      meta: {
        requiresAuth: true,
        role: "student",
      },
    },
    {
      path: "/assignments/:assignmentId/attempts",
      name: "student-assignment-attempts",
      component: () => import("../views/StudentAssignmentsView.vue"),
      props: (route) => ({
        screen: "attempts",
        assignmentId: String(route.params.assignmentId),
        quizTitle:
          typeof route.query.title === "string" ? route.query.title : "",
        historyView: route.query.from === "history",
      }),
      meta: {
        requiresAuth: true,
        role: "student",
      },
    },
    {
      path: "/parent-reports/verify",
      name: "parent-report-verify",
      component: () => import("../views/ParentReportVerifyView.vue"),
    },
    {
      path: "/parent-reports",
      name: "parent-report-settings",
      component: () => import("../views/ParentReportSettingsView.vue"),
      meta: {
        requiresAuth: true,
        role: "student",
      },
    },
    {
      path: "/parent-reports/unsubscribe",
      name: "parent-report-unsubscribe",
      component: () => import("../views/ParentReportUnsubscribeView.vue"),
    },
  ],
});

router.beforeEach((to) => {
  const isAuthenticated = store.getters["auth/isAuthenticated"];
  const role = store.state.auth.currentUser?.role;

  if (!isAuthenticated) {
    if (to.meta.requiresAuth) {
      return { name: "login" };
    }

    return true;
  }

  if (!["student", "teacher"].includes(role)) {
    store.commit("auth/CLEAR_AUTH");

    if (to.name !== "login") {
      return { name: "login" };
    }

    return true;
  }

  const dashboardName =
    role === "teacher" ? "teacher-dashboard" : "student-dashboard";
  if (["login", "register"].includes(to.name)) {
    return { name: dashboardName };
  }

  if (to.meta.role && to.meta.role !== role) {
    return { name: dashboardName };
  }

  return true;
});

export default router;
