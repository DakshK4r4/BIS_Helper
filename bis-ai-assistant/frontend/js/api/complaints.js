/**
 * BIS Sahayak - Complaints & Violations API Service
 */

const complaintsApi = {
    async getAll(filters = {}) {
        return apiClient.get("/complaints", filters);
    },

    async submit(complaintData) {
        return apiClient.post("/complaints", complaintData);
    },

    async investigate(complaintId) {
        return apiClient.post(`/complaints/${encodeURIComponent(complaintId)}/investigate`);
    }
};

if (typeof window !== "undefined") {
    window.complaintsApi = complaintsApi;
}
