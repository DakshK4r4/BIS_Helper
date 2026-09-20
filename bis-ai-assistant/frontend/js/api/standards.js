/**
 * BIS Sahayak - Standards Library & Watchlist API Service
 */

const standardsApi = {
    async search(filters = {}) {
        return apiClient.get("/standards", filters);
    },

    async getDetail(isNumber) {
        return apiClient.get(`/standards/${encodeURIComponent(isNumber)}`);
    },

    async getWatchlist() {
        return apiClient.get("/watchlist");
    },

    async toggleWatchlist(isNumber) {
        return apiClient.post("/watchlist", { is_number: isNumber });
    },

    async removeWatchlist(isNumber) {
        return apiClient.delete(`/watchlist/${encodeURIComponent(isNumber)}`);
    }
};

if (typeof window !== "undefined") {
    window.standardsApi = standardsApi;
}
