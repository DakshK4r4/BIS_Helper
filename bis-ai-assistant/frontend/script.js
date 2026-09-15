const API_BASE = "http://localhost:5000/api";


// ==================================================
// GLOBAL HELPERS
// ==================================================

function showLoading(button, text = "Processing...") {

    if (!button) return;

    button.dataset.originalText = button.innerHTML;

    button.disabled = true;

    button.innerHTML = `
        <i class="fa-solid fa-spinner fa-spin"></i>
        ${text}
    `;
}


function restoreButton(button) {

    if (!button) return;

    button.disabled = false;

    if (button.dataset.originalText) {
        button.innerHTML = button.dataset.originalText;
    }
}


async function apiRequest(url, options = {}) {

    const response = await fetch(
        `${API_BASE}${url}`,
        options
    );

    let data = {};

    try {
        data = await response.json();
    } catch {
        data = {};
    }

    if (!response.ok) {
        throw new Error(
            data.error ||
            data.message ||
            "Server request failed."
        );
    }

    return data;
}

// ==================================================
// VIEW NAVIGATION
// ==================================================

function switchView(viewId, element) {

    document.querySelectorAll(".app-view")
        .forEach(view => {
            view.classList.remove("active-view");
        });

    const targetView =
        document.getElementById(viewId);

    if (targetView) {
        targetView.classList.add("active-view");
    }

    if (element) {

        document.querySelectorAll(
            ".nav-menu li"
        ).forEach(li => {
            li.classList.remove("active");
        });

        element.classList.add("active");
    }

    if (viewId === "dashboard") {
        loadDashboard();
    }

    if (viewId === "history") {
        loadHistory();
    }
}


// ==================================================
// AI ASSISTANT
// ==================================================

async function triggerAiChat() {

    const input =
        document.getElementById("aiQueryInput");

    const query =
        input?.value.trim();

    if (!query) {

        alert(
            "Please enter a question."
        );

        return;
    }

    const button =
        document.querySelector(
            ".submit-arrow"
        );

    showLoading(
        button,
        "Thinking..."
    );

    try {

        const data = await apiRequest(
            "/ai/query",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    query
                })
            }
        );

        renderAiResponse(data);

        switchView("ai-response");

    } catch (error) {

        console.error(error);

        alert(
            error.message ||
            "AI request failed."
        );

    } finally {

        restoreButton(button);
    }
}


function quickQuery(queryText) {

    const input =
        document.getElementById(
            "aiQueryInput"
        );

    if (input) {

        input.value = queryText;

        triggerAiChat();
    }
}


function renderAiResponse(data) {

    const queryBar =
        document.querySelector(
            ".query-echo-bar"
        );

    const title =
        document.querySelector(
            ".answer-card-box h2"
        );

    const subtitle =
        document.querySelector(
            ".std-subtitle"
        );

    const confidence =
        document.querySelector(
            ".confidence-badge"
        );

    const description =
        document.querySelector(
            ".std-desc-text"
        );

    if (queryBar) {
        queryBar.innerText =
            data.query || "";
    }

    if (!data.recommended_standard) {

        if (title) {
            title.innerText =
                "No matching standard found";
        }

        if (subtitle) {
            subtitle.innerText =
                "Try providing more product details.";
        }

        if (description) {
            description.innerText =
                data.answer || "";
        }

        return;
    }

    const standard =
        data.recommended_standard;

    if (title) {
        title.innerText =
            standard.is_number;
    }

    if (subtitle) {
        subtitle.innerText =
            standard.title;
    }

    if (confidence) {

        confidence.innerHTML = `
            <i class="fa-solid fa-gauge-high"></i>
            Confidence: ${data.confidence_score}
        `;
    }

    if (description) {

        description.innerText =
            data.answer ||
            standard.description ||
            "";
    }

    // Update metrics
    const metrics =
        document.querySelectorAll(
            ".sub-metrics-row strong"
        );

    if (metrics.length >= 4) {

        metrics[0].innerText =
            standard.certification ||
            "Guidance";

        metrics[1].innerText =
            standard.category ||
            "Not specified";

        metrics[2].innerText =
            standard.status ||
            "Unknown";

        metrics[3].innerText =
            data.source ||
            "BIS Knowledge Base";
    }
}


// ==================================================
// STANDARDS SEARCH
// ==================================================

async function searchStandards(keyword = "") {

    const container =
        document.querySelector(
            ".standard-list-container"
        );

    const meta =
        document.querySelector(
            ".results-meta-bar span"
        );

    if (!container) return;

    container.innerHTML = `
        <div class="loading-state">
            <i class="fa-solid fa-spinner fa-spin"></i>
            Searching BIS standards...
        </div>
    `;

    try {

        const params =
            new URLSearchParams();

        if (keyword) {
            params.set("q", keyword);
        }

        const category =
            document.querySelector(
                ".filter-dropdowns select:nth-child(1)"
            )?.value;

        const industry =
            document.querySelector(
                ".filter-dropdowns select:nth-child(2)"
            )?.value;

        const year =
            document.querySelector(
                ".filter-dropdowns select:nth-child(3)"
            )?.value;

        const status =
            document.querySelector(
                ".filter-dropdowns select:nth-child(4)"
            )?.value;


        if (
            category &&
            category !== "Product Category"
        ) {
            params.set(
                "category",
                category
            );
        }

        if (
            industry &&
            industry !== "Industry"
        ) {
            params.set(
                "industry",
                industry
            );
        }

        if (
            year &&
            year !== "Year"
        ) {
            params.set(
                "year",
                year
            );
        }

        if (
            status &&
            status !== "Status"
        ) {
            params.set(
                "status",
                status
            );
        }


        const data =
            await apiRequest(
                `/standards?${params.toString()}`
            );

        renderStandards(
            data.standards
        );

        if (meta) {

            meta.innerHTML =
                `Results <b>(${data.count} standards)</b>`;
        }

    } catch (error) {

        console.error(error);

        container.innerHTML = `
            <div class="error-state">
                <i class="fa-solid fa-triangle-exclamation"></i>
                ${escapeHtml(error.message)}
            </div>
        `;
    }
}


function renderStandards(standards) {

    const container =
        document.querySelector(
            ".standard-list-container"
        );

    if (!container) return;

    if (!standards.length) {

        container.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-magnifying-glass"></i>
                <h3>No standards found</h3>
                <p>Try another keyword or filter.</p>
            </div>
        `;

        return;
    }

    container.innerHTML =
        standards.map(
            standard => `
                <div
                    class="standard-row-card"
                    onclick='openStandard(${JSON.stringify(
                        standard
                    )})'
                >

                    <div class="std-info-left">

                        <h4>
                            ${escapeHtml(
                                standard.is_number
                            )}
                        </h4>

                        <p>
                            ${escapeHtml(
                                standard.title
                            )}
                        </p>

                        <div class="tags-row">

                            <span class="tag electrical">
                                ${escapeHtml(
                                    standard.category ||
                                    "General"
                                )}
                            </span>

                            <span class="tag active">
                                ${escapeHtml(
                                    standard.status ||
                                    "Active"
                                )}
                            </span>

                        </div>

                    </div>

                    <button
                        class="text-link-btn"
                        onclick="event.stopPropagation(); openStandard(${JSON.stringify(
                            standard
                        )})"
                    >
                        View Details
                        <i class="fa-solid fa-arrow-right"></i>
                    </button>

                </div>
            `
        ).join("");
}


function openStandard(standard) {

    const input =
        document.getElementById(
            "aiQueryInput"
        );

    if (input) {

        input.value =
            `Explain ${standard.is_number}`;
    }

    renderAiResponse({

        query:
            `Information about ${standard.is_number}`,

        confidence_score:
            "100%",

        source:
            "BIS Knowledge Base",

        recommended_standard:
            standard,

        answer:
            standard.description
    });

    switchView(
        "ai-response"
    );
}


// ==================================================
// DOCUMENT UPLOAD
// ==================================================

async function uploadDocument(file) {

    try {

        const formData = new FormData();

        formData.append("file", file);

        const data = await apiRequest(
            "/documents/upload",
            {
                method: "POST",
                body: formData
            }
        );

        console.log("Upload response:", data);

        showDocumentResult(data.document);

    } catch (error) {

        console.error("Document upload error:", error);

        alert(
            "Document upload failed.\n\n" +
            error.message
        );
    }
}

function showDocumentResult(documentData) {

    const container =
        document.querySelector(
            ".doc-upload-container"
        );

    if (!container) return;

    container.innerHTML = `

        <div class="document-success">

            <div class="success-icon">
                <i class="fa-solid fa-circle-check"></i>
            </div>

            <h2>Document Analyzed</h2>

            <p>
                ${escapeHtml(
                    documentData.filename
                )}
            </p>

            <div class="document-stat">
                <strong>
                    ${documentData.characters_extracted}
                </strong>

                <span>
                    Characters extracted
                </span>
            </div>

            <div class="document-summary">

                <h3>
                    AI Document Summary
                </h3>

                <pre>
${escapeHtml(
    documentData.summary
)}
                </pre>

            </div>

            <button
                class="primary-btn"
                onclick="switchView('compliance')"
            >
                Continue to Compliance
                <i class="fa-solid fa-arrow-right"></i>
            </button>

        </div>
    `;
}


// ==================================================
// BIS VERIFICATION
// ==================================================

async function verifyLicenseNumber(
    licenseNo
) {

    if (!licenseNo) {

        alert(
            "Enter a BIS license number."
        );

        return;
    }

    const resultBox =
        document.querySelector(
            ".verified-success-box"
        );

    if (resultBox) {

        resultBox.innerHTML = `
            <i class="fa-solid fa-spinner fa-spin"></i>
            <div>
                <h4>Verifying...</h4>
                <p>
                    Checking the BIS verification database.
                </p>
            </div>
        `;
    }

    try {

        const data =
            await apiRequest(
                `/verify/${encodeURIComponent(
                    licenseNo
                )}`
            );

        renderVerification(
            data.details
        );

    } catch (error) {

        if (resultBox) {

            resultBox.className =
                "verified-success-box verification-failed";

            resultBox.innerHTML = `
                <i class="fa-solid fa-circle-xmark"></i>

                <div>
                    <h4>Not Verified</h4>

                    <p>
                        ${escapeHtml(
                            error.message
                        )}
                    </p>
                </div>
            `;
        }
    }
}


function renderVerification(details) {

    const resultBox =
        document.querySelector(
            ".verified-success-box"
        );

    if (!resultBox) return;

    resultBox.className =
        "verified-success-box";

    resultBox.innerHTML = `

        <i class="fa-solid fa-circle-check"></i>

        <div>

            <h4>Verified</h4>

            <p>
                This license is active in the
                verification database.
            </p>

            <div class="ver-details-grid">

                <span>
                    License:
                    <b>
                        ${escapeHtml(
                            details.license_number
                        )}
                    </b>
                </span>

                <span>
                    Product:
                    <b>
                        ${escapeHtml(
                            details.product
                        )}
                    </b>
                </span>

                <span>
                    Manufacturer:
                    <b>
                        ${escapeHtml(
                            details.manufacturer
                        )}
                    </b>
                </span>

                <span>
                    Validity:
                    <b>
                        ${escapeHtml(
                            details.validity_from
                        )}
                        –
                        ${escapeHtml(
                            details.validity_to
                        )}
                    </b>
                </span>

                <span>
                    Standard:
                    <b>
                        ${escapeHtml(
                            details.standard
                        )}
                    </b>
                </span>

                <span>
                    Status:
                    <b>
                        ${escapeHtml(
                            details.status
                        )}
                    </b>
                </span>

            </div>

        </div>
    `;
}


// ==================================================
// COMPLIANCE CHECKER
// ==================================================

async function runComplianceCheck() {

    const product =
        document.getElementById(
            "complianceProduct"
        )?.value.trim();

    const standard =
        document.getElementById(
            "complianceStandard"
        )?.value.trim();

    const documents =
        window.uploadedDocuments ||
        [];

    try {

        const result =
            await apiRequest(
                "/compliance/check",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        product,
                        standard,
                        documents
                    })
                }
            );

        renderComplianceResult(
            result
        );

    } catch (error) {

        alert(
            error.message ||
            "Compliance analysis failed."
        );
    }
}


function renderComplianceResult(result) {

    const body =
        document.querySelector(
            ".stepper-card-body"
        );

    if (!body) return;

    body.innerHTML = `

        <div class="compliance-result">

            <div class="score-circle">
                ${result.score}%
            </div>

            <h2>
                ${escapeHtml(
                    result.result
                )}
            </h2>

            <span class="risk-badge">
                Risk: ${escapeHtml(
                    result.risk
                )}
            </span>

            <div class="compliance-checks">

                ${result.checks.map(
                    check => `

                        <div class="check-row">

                            <div>

                                <strong>
                                    ${escapeHtml(
                                        check.name
                                    )}
                                </strong>

                                <p>
                                    ${escapeHtml(
                                        check.message
                                    )}
                                </p>

                            </div>

                            <span
                                class="check-status ${check.status.toLowerCase()}"
                            >
                                ${escapeHtml(
                                    check.status
                                )}
                            </span>

                        </div>
                    `
                ).join("")}

            </div>

            <div class="recommendations">

                <h3>
                    AI Recommendations
                </h3>

                <ul>

                    ${result.recommendations.map(
                        recommendation =>
                            `<li>${escapeHtml(
                                recommendation
                            )}</li>`
                    ).join("")}

                </ul>

            </div>

        </div>
    `;
}


// ==================================================
// DASHBOARD
// ==================================================

async function loadDashboard() {

    try {

        const data =
            await apiRequest(
                "/dashboard"
            );

        const metrics =
            data.metrics;

        const cards =
            document.querySelectorAll(
                ".dash-card h3"
            );

        if (cards.length >= 4) {

            cards[0].innerText =
                metrics.products;

            cards[1].innerText =
                metrics.certificates;

            cards[2].innerText =
                `${metrics.compliance}%`;

            cards[3].innerText =
                metrics.reports;
        }

        renderRecentActivity(
            data.recent_activity
        );

    } catch (error) {

        console.error(
            "Dashboard error:",
            error
        );
    }
}


function renderRecentActivity(
    activities
) {

    const existing =
        document.querySelector(
            ".recent-activity"
        );

    if (!existing) return;

    if (!activities.length) {

        existing.innerHTML =
            "<p>No recent activity.</p>";

        return;
    }

    existing.innerHTML = `

        <h3>Recent Activity</h3>

        ${activities.map(
            activity => `

                <div class="activity-row">

                    <i class="fa-solid fa-clock"></i>

                    <span>
                        ${escapeHtml(
                            activity.query
                        )}
                    </span>

                </div>

            `
        ).join("")}

    `;
}


// ==================================================
// HISTORY
// ==================================================

async function loadHistory() {

    try {

        const data =
            await apiRequest(
                "/history"
            );

        const container =
            document.querySelector(
                ".about-card-container"
            );

        if (!container) return;

        container.innerHTML = `

            <h2>
                Activity History
            </h2>

            <p>
                Your recent BIS AI Assistant activity.
            </p>

            <div class="history-list">

                ${
                    data.history.length
                    ?
                    data.history.map(
                        item => `

                            <div class="history-item">

                                <i class="fa-solid fa-message"></i>

                                <div>

                                    <strong>
                                        ${escapeHtml(
                                            item.query
                                        )}
                                    </strong>

                                    <small>
                                        ${escapeHtml(
                                            item.created_at
                                        )}
                                    </small>

                                </div>

                            </div>
                        `
                    ).join("")
                    :
                    "<p>No history yet.</p>"
                }

            </div>
        `;

    } catch (error) {

        console.error(
            "History error:",
            error
        );
    }
}


// ==================================================
// HEADER SEARCH
// ==================================================

function setupHeaderSearch() {

    const input =
        document.querySelector(
            ".header-search input"
        );

    if (!input) return;

    input.addEventListener(
        "keydown",
        event => {

            if (
                event.key === "Enter"
            ) {

                event.preventDefault();

                const query =
                    input.value.trim();

                if (!query) return;

                switchView(
                    "standards"
                );

                const searchInput =
                    document.querySelector(
                        ".main-search-input-wrap input"
                    );

                if (searchInput) {
                    searchInput.value =
                        query;
                }

                searchStandards(
                    query
                );
            }
        }
    );
}


// ==================================================
// ENTER KEY FOR AI
// ==================================================

function setupAiEnter() {

    const input =
        document.getElementById(
            "aiQueryInput"
        );

    if (!input) return;

    input.addEventListener(
        "keydown",
        event => {

            if (
                event.key === "Enter"
            ) {

                event.preventDefault();

                triggerAiChat();
            }
        }
    );
}


// ==================================================
// DOCUMENT DROPZONE
// ==================================================

function setupDocumentUpload() {

    const dropzone = document.querySelector("#documentDropzone");

    if (!dropzone) return;

    // Prevent browser/form default behavior
    dropzone.addEventListener("click", function(event) {
        event.preventDefault();
        event.stopPropagation();
    });

    // Create hidden file input
    const input = document.createElement("input");

    input.type = "file";
    input.accept = ".pdf,.docx";
    input.style.display = "none";

    document.body.appendChild(input);

    // Open file browser
    dropzone.addEventListener("click", function(event) {

        event.preventDefault();
        event.stopPropagation();

        input.click();
    });

    // File selected
    input.addEventListener("change", function(event) {

        event.preventDefault();
        event.stopPropagation();

        if (input.files && input.files.length > 0) {

            const file = input.files[0];

            console.log("Selected file:", file.name);

            uploadDocument(file);
        }
    });

    // Drag over
    dropzone.addEventListener("dragover", function(event) {

        event.preventDefault();
        event.stopPropagation();

        dropzone.classList.add("dragover");
    });

    // Drag leave
    dropzone.addEventListener("dragleave", function(event) {

        event.preventDefault();
        event.stopPropagation();

        dropzone.classList.remove("dragover");
    });

    // Drop
    dropzone.addEventListener("drop", function(event) {

        event.preventDefault();
        event.stopPropagation();

        dropzone.classList.remove("dragover");

        const files = event.dataTransfer.files;

        if (files && files.length > 0) {

            const file = files[0];

            console.log("Dropped file:", file.name);

            uploadDocument(file);
        }
    });
}


// ==================================================
// SEARCH BUTTON
// ==================================================

function setupDocumentUpload() {

    const dropzone = document.querySelector(".dropzone-box");

    if (!dropzone) return;

    // Create hidden file input
    const input = document.createElement("input");

    input.type = "file";
    input.accept = ".pdf,.docx";
    input.style.display = "none";

    document.body.appendChild(input);


    // ==================================================
    // CLICK TO SELECT FILE
    // ==================================================

    dropzone.addEventListener("click", function(event) {

        event.preventDefault();
        event.stopPropagation();

        input.click();

    });


    // ==================================================
    // FILE SELECTED
    // ==================================================

    input.addEventListener("change", function(event) {

        event.preventDefault();
        event.stopPropagation();

        if (input.files && input.files.length > 0) {

            const file = input.files[0];

            console.log("Selected file:", file.name);

            uploadDocument(file);
        }

    });


    // ==================================================
    // DRAG OVER
    // ==================================================

    dropzone.addEventListener("dragover", function(event) {

        event.preventDefault();
        event.stopPropagation();

        dropzone.classList.add("dragover");

    });


    // ==================================================
    // DRAG LEAVE
    // ==================================================

    dropzone.addEventListener("dragleave", function(event) {

        event.preventDefault();
        event.stopPropagation();

        dropzone.classList.remove("dragover");

    });


    // ==================================================
    // DROP FILE
    // ==================================================

    dropzone.addEventListener("drop", function(event) {

        event.preventDefault();
        event.stopPropagation();

        dropzone.classList.remove("dragover");

        const files = event.dataTransfer.files;

        if (files && files.length > 0) {

            const file = files[0];

            console.log("Dropped file:", file.name);

            uploadDocument(file);
        }

    });

}


// ==================================================
// VERIFICATION BUTTON
// ==================================================

function setupVerification() {

    const input =
        document.querySelector(
            ".ver-input-row input"
        );

    const button =
        document.querySelector(
            ".ver-input-row button"
        );

    if (!input || !button)
        return;

    button.addEventListener(
        "click",
        () => {

            verifyLicenseNumber(
                input.value.trim()
            );
        }
    );
}


// ==================================================
// ESCAPE HTML
// ==================================================

function escapeHtml(value) {

    const div =
        document.createElement(
            "div"
        );

    div.innerText =
        value ?? "";

    return div.innerHTML;
}


// ==================================================
// INITIALIZATION
// ==================================================

document.addEventListener(
    "DOMContentLoaded",
    () => {

        setupHeaderSearch();

        setupAiEnter();

        setupDocumentUpload();

        setupStandardsSearch();

        setupVerification();

        loadDashboard();
    }
);
// --------------------------------------------------
// DOCUMENT INTELLIGENCE - SUMMARIZE
// --------------------------------------------------

async function summarizeDocument() {

    try {

        // Get uploaded documents from Flask backend
        const data = await apiRequest("/documents");

        // Check if any document exists
        if (!data.documents || data.documents.length === 0) {
            alert("Please upload a document first.");
            return;
        }

        // Get the most recently uploaded document
        const document = data.documents[0];

        // Display the document summary
        const message =
            "Document: " + document.filename +
            "\n\n" +
            "Summary:\n" +
            (document.summary || "No summary available.");

        alert(message);

    } catch (error) {

        console.error("Document summary error:", error);

        alert(
            "Unable to summarize document.\n\n" +
            error.message
        );
    }
}