/**
 * BIS Sahayak - User History API Service
 */

const historyApi = {
    async getAll(filter = "all") {
        return apiClient.get("/history", { filter });
    },

    async record(actionType, title, description, meta = {}, status = "SUCCESS") {
        return apiClient.post("/history", {
            action_type: actionType,
            title,
            description,
            meta,
            status
        });
    },

    async clear() {
        return apiClient.delete("/history");
    }
};

if (typeof window !== "undefined") {
    window.historyApi = historyApi;
}
