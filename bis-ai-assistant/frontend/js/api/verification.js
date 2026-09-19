/**
 * BIS Sahayak - License & Hallmark Verification API Service
 */

const verificationApi = {
    async verifyLicense(licenseNo) {
        return apiClient.get(`/verify/${encodeURIComponent(licenseNo)}`);
    },

    async verifyHallmark(huid) {
        return apiClient.get(`/verify/hallmark/${encodeURIComponent(huid)}`);
    }
};

if (typeof window !== "undefined") {
    window.verificationApi = verificationApi;
}
