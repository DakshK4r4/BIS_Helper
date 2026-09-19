/**
 * BIS Sahayak - Authentication API Service
 */

const authApi = {
    async getMe() {
        return apiClient.get("/auth/me");
    },

    async loginDemo(role = "officer", email, name) {
        return apiClient.post("/auth/demo", { role, email, name });
    },

    async loginGoogle(credential) {
        return apiClient.post("/auth/google", { credential });
    },

    async logout() {
        return apiClient.post("/auth/logout");
    }
};

if (typeof window !== "undefined") {
    window.authApi = authApi;
}
