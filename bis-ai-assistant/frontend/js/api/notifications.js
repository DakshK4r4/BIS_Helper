/**
 * BIS Sahayak - Notifications API Service
 */

const notificationsApi = {
    async getAll(category = "") {
        const params = {};
        if (category && category !== "all") {
            params.category = category;
        }
        return apiClient.get("/notifications", params);
    },

    async markRead(notifId) {
        return apiClient.post(`/notifications/${notifId}/read`);
    },

    async markAllRead() {
        return apiClient.post("/notifications/read-all");
    }
};

if (typeof window !== "undefined") {
    window.notificationsApi = notificationsApi;
}
