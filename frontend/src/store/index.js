import { createStore } from "vuex";

import auth from "./modules/auth";
import tutor from "./modules/tutor";

const store = createStore({
  modules: {
    auth,
    tutor,
  },
});

store.subscribe((mutation, state) => {
  if (mutation.type === "auth/CLEAR_AUTH") {
    store.commit("tutor/RESET_STATE");
    return;
  }

  if (mutation.type === "auth/SET_AUTH") {
    const userId = state.auth.currentUser?.id ?? null;

    if (state.tutor.ownerId !== userId) {
      store.commit("tutor/RESET_STATE", userId);
    }
  }
});

export default store;
