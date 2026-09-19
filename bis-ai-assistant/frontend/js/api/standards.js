/**
 * BIS Sahayak - Standards Library API Service
 */

const standardsApi = {
    async search(filters = {}) {
        return apiClient.get("/standards", filters);
    },

    async getDetail(isNumber) {
        return apiClient.get(`/standards/${encodeURIComponent(isNumber)}`);
    }
};

if (typeof window !== "undefined") {
    window.standardsApi = standardsApi;
}
