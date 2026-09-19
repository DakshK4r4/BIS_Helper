/**
 * BIS Sahayak - AI Assistant API Service
 */

const aiApi = {
    async query(queryText, documentContext = null, documentFilename = null) {
        return apiClient.post("/ai/query", {
            query: queryText,
            document_context: documentContext,
            document_filename: documentFilename
        });
    }
};

if (typeof window !== "undefined") {
    window.aiApi = aiApi;
}
