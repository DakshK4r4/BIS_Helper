/**
 * BIS Sahayak - Notifications API Service
 */

const notificationsApi = {
    async getAll() {
        return apiClient.get("/notifications");
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
