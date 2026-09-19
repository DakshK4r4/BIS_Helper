/**
 * BIS Sahayak - BIS Services API Service
 */

const servicesApi = {
    async getAll() {
        return apiClient.get("/services");
    }
};

if (typeof window !== "undefined") {
    window.servicesApi = servicesApi;
}
