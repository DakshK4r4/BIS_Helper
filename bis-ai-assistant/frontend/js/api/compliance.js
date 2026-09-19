/**
 * BIS Sahayak - Compliance Analysis API Service
 */

const complianceApi = {
    async check(product, standard, documents = []) {
        return apiClient.post("/compliance/check", {
            product,
            standard,
            documents
        });
    }
};

if (typeof window !== "undefined") {
    window.complianceApi = complianceApi;
}
