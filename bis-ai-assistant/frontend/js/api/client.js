/**
 * BIS Sahayak - Centralized HTTP Client
 * Manages base URL, token authorization, error handling, JSON and multipart uploads.
 */

const API_BASE_URL =
    window.__API_BASE_URL__ || "http://localhost:5001/api";

class ApiClient {
    constructor(baseUrl = API_BASE_URL) {
        this.baseUrl = baseUrl.replace(/\/+$/, "");
    }

    getToken() {
        try {
            const user = JSON.parse(localStorage.getItem("bis_user") || "{}");
            return user.token || localStorage.getItem("bis_token") || "";
        } catch (_) {
            return "";
        }
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;
        const headers = options.headers ? { ...options.headers } : {};

        const token = this.getToken();
        if (token && !headers["Authorization"]) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        const isFormData = options.body instanceof FormData;
        if (!isFormData && !headers["Content-Type"]) {
            headers["Content-Type"] = "application/json";
        }

        const config = {
            ...options,
            headers
        };

        try {
            const response = await fetch(url, config);

            if (response.status === 204) {
                return { success: true };
            }

            let data;
            const contentType = response.headers.get("content-type") || "";
            if (contentType.includes("application/json")) {
                data = await response.json();
            } else {
                const text = await response.text();
                try {
                    data = JSON.parse(text);
                } catch (_) {
                    data = { message: text };
                }
            }

            if (!response.ok) {
                const errorMessage = data?.error || data?.message || `HTTP Error ${response.status}: ${response.statusText}`;
                const error = new Error(errorMessage);
                error.status = response.status;
                error.data = data;

                if (response.status === 401) {
                    window.dispatchEvent(new CustomEvent("bis:unauthorized", { detail: { error, endpoint } }));
                }

                throw error;
            }

            return data;
        } catch (error) {
            if (error.name === "TypeError" && error.message.includes("fetch")) {
                const netError = new Error("Unable to connect to BIS Sahayak backend server. Please ensure the backend is running.");
                netError.status = 0;
                netError.isNetworkError = true;
                window.dispatchEvent(new CustomEvent("bis:network-error", { detail: { error: netError, endpoint } }));
                throw netError;
            }
            throw error;
        }
    }

    get(endpoint, params = {}) {
        let query = "";
        const keys = Object.keys(params).filter(k => params[k] !== undefined && params[k] !== null && params[k] !== "");
        if (keys.length > 0) {
            const sp = new URLSearchParams();
            keys.forEach(k => sp.append(k, params[k]));
            query = (endpoint.includes("?") ? "&" : "?") + sp.toString();
        }
        return this.request(`${endpoint}${query}`, { method: "GET" });
    }

    post(endpoint, body = {}) {
        const isFormData = body instanceof FormData;
        return this.request(endpoint, {
            method: "POST",
            body: isFormData ? body : JSON.stringify(body)
        });
    }

    put(endpoint, body = {}) {
        return this.request(endpoint, {
            method: "PUT",
            body: JSON.stringify(body)
        });
    }

    delete(endpoint) {
        return this.request(endpoint, { method: "DELETE" });
    }

    upload(endpoint, fileOrFormData, additionalFields = {}) {
        let formData;
        if (fileOrFormData instanceof FormData) {
            formData = fileOrFormData;
        } else {
            formData = new FormData();
            formData.append("file", fileOrFormData);
        }

        Object.keys(additionalFields).forEach(key => {
            if (additionalFields[key] !== undefined && additionalFields[key] !== null) {
                formData.append(key, additionalFields[key]);
            }
        });

        return this.request(endpoint, {
            method: "POST",
            body: formData
        });
    }
}

const apiClient = new ApiClient();
if (typeof window !== "undefined") {
    window.apiClient = apiClient;
}
