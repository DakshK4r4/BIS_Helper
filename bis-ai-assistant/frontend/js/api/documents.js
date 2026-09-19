/**
 * BIS Sahayak - Document Intelligence API Service
 */

const documentsApi = {
    async upload(file) {
        return apiClient.upload("/documents/upload", file);
    },

    async getAll() {
        return apiClient.get("/documents");
    },

    async getById(id) {
        return apiClient.get(`/documents/${id}`);
    }
};

if (typeof window !== "undefined") {
    window.documentsApi = documentsApi;
}
