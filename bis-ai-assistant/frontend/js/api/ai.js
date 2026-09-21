/**
 * BIS Sahayak - AI Assistant API Service
 */

const aiApi = {
    async query(queryText, documentContext = null, documentFilename = null, history = []) {
        return apiClient.post("/ai/query", {
            query: queryText,
            document_context: documentContext,
            document_filename: documentFilename,
            history: history
        });
    }
};

if (typeof window !== "undefined") {
    window.aiApi = aiApi;
}
