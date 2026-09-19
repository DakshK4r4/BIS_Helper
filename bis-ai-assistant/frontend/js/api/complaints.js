/**
 * BIS Sahayak - Complaints & Violations API Service
 */

const complaintsApi = {
    async getAll(filters = {}) {
        return apiClient.get("/complaints", filters);
    },

    async submit(complaintData) {
        return apiClient.post("/complaints", complaintData);
    }
};

if (typeof window !== "undefined") {
    window.complaintsApi = complaintsApi;
}
