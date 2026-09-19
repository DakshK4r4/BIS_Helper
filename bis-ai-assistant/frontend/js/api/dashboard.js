/**
 * BIS Sahayak - Dashboard API Service
 */

const dashboardApi = {
    async getMetrics() {
        return apiClient.get("/dashboard");
    }
};

if (typeof window !== "undefined") {
    window.dashboardApi = dashboardApi;
}
