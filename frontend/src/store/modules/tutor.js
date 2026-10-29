export default {
  namespaced: true,

  state() {
    return {
      ownerId: null,
      messages: [],
      selectedTopic: "",
      sessionId: null,
      draftMessage: "",
      learningMode: "personal_growth",
    };
  },

  mutations: {
    SET_MESSAGES(state, messages) {
      state.messages = messages;
    },

    ADD_MESSAGE(state, message) {
      state.messages.push(message);
    },

    SET_SELECTED_TOPIC(state, topic) {
      state.selectedTopic = topic;
    },

    SET_SESSION_ID(state, sessionId) {
      state.sessionId = sessionId;
    },

    SET_DRAFT_MESSAGE(state, message) {
      state.draftMessage = message;
    },

    SET_LEARNING_MODE(state, learningMode) {
      if (!["exam_preparation", "personal_growth"].includes(learningMode)) {
        return;
      }

      state.learningMode = learningMode;
    },

    RESET_STATE(state, ownerId = null) {
      state.ownerId = ownerId;
      state.messages = [];
      state.selectedTopic = "";
      state.sessionId = null;
      state.draftMessage = "";
      state.learningMode = "personal_growth";
    },
  },
};
