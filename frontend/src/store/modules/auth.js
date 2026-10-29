function getStoredUser() {
  const storedUser = sessionStorage.getItem("current_user");

  if (!storedUser) {
    return null;
  }

  try {
    return JSON.parse(storedUser);
  } catch {
    return null;
  }
}

export default {
  namespaced: true,

  state() {
    return {
      accessToken: sessionStorage.getItem("access_token"),
      currentUser: getStoredUser(),
    };
  },

  getters: {
    isAuthenticated(state) {
      return Boolean(state.accessToken);
    },

    isTeacher(state) {
      return (
        Boolean(state.accessToken) && state.currentUser?.role === "teacher"
      );
    },

    isStudent(state) {
      return (
        Boolean(state.accessToken) && state.currentUser?.role === "student"
      );
    },
  },

  mutations: {
    SET_AUTH(state, { token, user }) {
      state.accessToken = token;
      state.currentUser = user;

      sessionStorage.setItem("access_token", token);
      sessionStorage.setItem("current_user", JSON.stringify(user));
    },

    CLEAR_AUTH(state) {
      state.accessToken = null;
      state.currentUser = null;

      sessionStorage.removeItem("access_token");
      sessionStorage.removeItem("current_user");
    },
  },

  actions: {
    async login({ commit }, credentials) {
      const response = await fetch("http://127.0.0.1:5000/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(credentials),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Login failed.");
      }

      commit("SET_AUTH", {
        token: data.access_token,
        user: data.user,
      });

      return data;
    },

    async logout({ state, commit }) {
      if (!state.accessToken) {
        return;
      }

      const response = await fetch("http://127.0.0.1:5000/api/auth/logout", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${state.accessToken}`,
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || data.msg || "Logout failed.");
      }

      commit("CLEAR_AUTH");
    },
  },
};
