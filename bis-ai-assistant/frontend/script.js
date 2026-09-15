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

    // Update active state on nav-menu
    document.querySelectorAll(".nav-menu li")
        .forEach(li => {
            li.classList.remove("active");
        });

    if (element) {
        element.classList.add("active");
    } else {
        const matchingLi = document.querySelector(`.nav-menu li[onclick*="'${viewId}'"]`);
        if (matchingLi) {
            matchingLi.classList.add("active");
        }
    }

    // Synchronize URL hash so browser reload stays on the current view
    if (window.location.hash !== `#${viewId}`) {
        try {
            history.replaceState(null, "", `#${viewId}`);
        } catch (_) {}
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

async function triggerAiChat(event) {

    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    const input =
        document.getElementById("aiQueryInput");

    const query =
        input?.value.trim();

    if (!query) {
        alert("Please enter a question.");
        return;
    }

    const button =
        document.querySelector(".submit-arrow");

    showLoading(
        button,
        "Thinking..."
    );

    const inlineResults = document.getElementById("aiChatResults");
    const inlineLoading = document.getElementById("aiChatLoading");
    const inlineContent = document.getElementById("aiChatResultContent");

    if (inlineResults && inlineLoading && inlineContent) {
        inlineResults.style.display = "block";
        inlineLoading.style.display = "flex";
        inlineContent.style.display = "none";
        inlineResults.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    try {

        const data = await apiRequest(
            "/ai/query",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    query
                })
            }
        );

        // 1. Render response directly on the AI Assistant page (#ai-chat)
        renderInlineAiResponse(data);

        // 2. Also keep separate #ai-response view populated for compatibility
        renderAiResponse(data);

    } catch (error) {

        console.error("AI Assistant query error:", error);

        alert(
            error.message ||
            "AI request failed."
        );

        if (inlineResults) {
            inlineResults.style.display = "none";
        }

    } finally {

        restoreButton(button);

        if (inlineLoading) {
            inlineLoading.style.display = "none";
        }
    }
}


function quickQuery(queryText) {

    const input =
        document.getElementById("aiQueryInput");

    if (input) {
        input.value = queryText;
        triggerAiChat();
    }
}


function renderInlineAiResponse(data) {

    const inlineResults = document.getElementById("aiChatResults");
    const inlineLoading = document.getElementById("aiChatLoading");
    const inlineContent = document.getElementById("aiChatResultContent");

    if (!inlineResults || !inlineContent) return;

    inlineResults.style.display = "block";
    if (inlineLoading) inlineLoading.style.display = "none";
    inlineContent.style.display = "block";

    const queryEcho = document.getElementById("aiQueryEcho");
    const numEl = document.getElementById("aiStandardNumber");
    const titleEl = document.getElementById("aiStandardTitle");
    const descEl = document.getElementById("aiStandardDesc");
    const confBadge = document.getElementById("aiConfidenceBadge");
    const certEl = document.getElementById("aiMetricCert");
    const catEl = document.getElementById("aiMetricCat");
    const statusEl = document.getElementById("aiMetricStatus");
    const srcEl = document.getElementById("aiMetricSource");

    if (queryEcho) queryEcho.innerText = data.query || "";

    if (!data.recommended_standard) {
        if (numEl) numEl.innerText = "No Matching Standard Found";
        if (titleEl) titleEl.innerText = "BIS Knowledge Guidance";
        if (descEl) descEl.innerText = data.answer || "Try searching with other keywords, product name or technical specifications.";
        if (confBadge) {
            confBadge.innerHTML = `<i class="fa-solid fa-circle-info"></i> Guidance`;
        }
        return;
    }

    const std = data.recommended_standard;
    if (numEl) numEl.innerText = std.is_number;
    if (titleEl) titleEl.innerText = std.title;
    if (descEl) descEl.innerText = data.answer || std.description || "";
    if (confBadge) {
        confBadge.innerHTML = `<i class="fa-solid fa-gauge-high"></i> Confidence: ${data.confidence_score}`;
    }
    if (certEl) certEl.innerText = std.certification || "Product Certification";
    if (catEl) catEl.innerText = std.category || "General";
    if (statusEl) statusEl.innerText = std.status || "Active";
    if (srcEl) srcEl.innerText = data.source || "BIS Knowledge Base";

    // Scroll gently into view
    inlineResults.scrollIntoView({ behavior: "smooth", block: "nearest" });
}


function clearAiChatResult() {
    const inlineResults = document.getElementById("aiChatResults");
    if (inlineResults) inlineResults.style.display = "none";
    const input = document.getElementById("aiQueryInput");
    if (input) {
        input.value = "";
        input.focus();
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
// DOCUMENT UPLOAD & ANALYSIS
// ==================================================

async function uploadDocument(file) {

    if (!file) return;

    const idleState = document.getElementById("dropzoneIdleState");
    const loadingState = document.getElementById("dropzoneLoadingState");
    const loadingTitle = document.getElementById("dropzoneLoadingTitle");
    const loadingSubtitle = document.getElementById("dropzoneLoadingSubtitle");
    const analyzeBtn = document.getElementById("docAnalyzeBtn");
    const currentTag = document.getElementById("docCurrentFileName");
    const currentIcon = document.getElementById("docCurrentFileIcon");

    // Show loading indicator on dropzone
    if (idleState && loadingState) {
        idleState.style.display = "none";
        loadingState.style.display = "block";
        if (loadingTitle) loadingTitle.innerText = `Analyzing ${file.name}...`;
        if (loadingSubtitle) loadingSubtitle.innerText = "Extracting text, requirements & computing compliance";
    }

    if (analyzeBtn) {
        showLoading(analyzeBtn, "Analyzing...");
    }

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

        if (!data.success) {
            alert(data.error || "Document processing failed.");
            return;
        }

        const doc = data.document;
        window.latestUploadedDocument = doc;

        if (currentTag) {
            currentTag.innerText = doc.filename;
        }
        if (currentIcon) {
            currentIcon.className = doc.file_type === "pdf" ? "fa-regular fa-file-pdf" : "fa-regular fa-file-word";
        }

        renderDocumentAnalysis(doc);

    } catch (error) {

        console.error("Document upload error:", error);

        alert(
            "Document upload failed.\n\n" +
            error.message
        );

    } finally {

        // Restore dropzone state
        if (idleState && loadingState) {
            idleState.style.display = "block";
            loadingState.style.display = "none";
        }

        if (analyzeBtn) {
            restoreButton(analyzeBtn);
        }
    }
}


function renderDocumentAnalysis(doc) {

    const resultsContainer = document.getElementById("documentAnalysisResults");
    if (!resultsContainer) return;

    resultsContainer.style.display = "block";

    // 1. Overview & Meta
    const meta = doc.metadata || {};
    const prodEl = document.getElementById("docMetaProduct");
    const stdEl = document.getElementById("docMetaStandard");
    const mfgEl = document.getElementById("docMetaManufacturer");
    const modelEl = document.getElementById("docMetaModel");
    const statusBadge = document.getElementById("docStatusBadge");
    const summaryText = document.getElementById("docSummaryText");

    if (prodEl) prodEl.innerText = meta.product || "Declared Product";
    if (stdEl) stdEl.innerText = meta.standard || "Applicable Standard";
    if (mfgEl) mfgEl.innerText = meta.manufacturer || "Declared Manufacturer";
    if (modelEl) modelEl.innerText = meta.model || "Declared Model";
    if (statusBadge) statusBadge.innerText = doc.status || "PROCESSED";
    if (summaryText) summaryText.innerText = doc.summary || "Summary generated from document extraction.";

    // 2. Compliance Score & Risk
    const comp = doc.compliance || {};
    const scoreNum = document.getElementById("docScoreNum");
    const verdictText = document.getElementById("docVerdictText");
    const riskBadge = document.getElementById("docRiskBadge");
    const totalReqs = document.getElementById("docTotalReqsCount");
    const passedReqs = document.getElementById("docPassedReqsCount");
    const failedReqs = document.getElementById("docFailedReqsCount");
    const scoreCircle = document.getElementById("docScoreCircle");

    const score = comp.score !== undefined ? comp.score : 0;
    if (scoreNum) scoreNum.innerText = score;
    if (verdictText) verdictText.innerText = comp.result || (score >= 80 ? "Likely Compliant" : "Further Review Required");
    
    if (riskBadge) {
        const risk = comp.risk || (score >= 80 ? "LOW" : (score >= 50 ? "MEDIUM" : "HIGH"));
        riskBadge.innerText = `RISK: ${risk}`;
        riskBadge.className = `risk-badge risk-${risk.toLowerCase()}`;
    }

    if (scoreCircle) {
        scoreCircle.className = `score-circle-large score-${score >= 80 ? 'high' : (score >= 50 ? 'med' : 'low')}`;
    }

    if (totalReqs) totalReqs.innerText = comp.total !== undefined ? comp.total : (doc.requirements ? doc.requirements.length : 0);
    if (passedReqs) passedReqs.innerText = comp.passed !== undefined ? comp.passed : 0;
    if (failedReqs) failedReqs.innerText = comp.failed !== undefined ? comp.failed : 0;

    // 3. Violations & Gaps
    const violationsList = document.getElementById("docViolationsList");
    const violationsBadge = document.getElementById("docViolationsCountBadge");
    const violations = doc.violations || [];

    if (violationsBadge) {
        violationsBadge.innerText = `${violations.length} Issue${violations.length === 1 ? '' : 's'} Identified`;
        violationsBadge.className = violations.length > 0 ? "badge-tag warning" : "badge-tag success";
    }

    if (violationsList) {
        if (violations.length === 0) {
            violationsList.innerHTML = `
                <div class="violation-item resolved">
                    <i class="fa-solid fa-circle-check"></i>
                    <div>
                        <h4>No Non-Compliance Violations Detected</h4>
                        <p>All extracted requirements in this document meet standard compliance parameters.</p>
                    </div>
                </div>
            `;
        } else {
            violationsList.innerHTML = violations.map(v => `
                <div class="violation-item severity-${(v.severity || 'medium').toLowerCase()}">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    <div>
                        <div class="violation-title-row">
                            <h4>${escapeHtml(v.title || v.id)}</h4>
                            <span class="severity-badge">${escapeHtml(v.severity || 'HIGH')}</span>
                        </div>
                        <p>${escapeHtml(v.description)}</p>
                    </div>
                </div>
            `).join("");
        }
    }

    // 4. Recommendations
    const recsList = document.getElementById("docRecommendationsList");
    const recommendations = doc.recommendations || [];

    if (recsList) {
        if (recommendations.length === 0) {
            recsList.innerHTML = `<p class="no-data-msg">No specific corrective actions required.</p>`;
        } else {
            recsList.innerHTML = recommendations.map((rec, idx) => `
                <div class="recommendation-row">
                    <div class="rec-num-badge">${idx + 1}</div>
                    <div class="rec-text">${escapeHtml(rec)}</div>
                </div>
            `).join("");
        }
    }

    // 5. Requirements Table
    const tbody = document.getElementById("docRequirementsTbody");
    const reqBadge = document.getElementById("docReqCountBadge");
    const requirements = doc.requirements || [];

    if (reqBadge) {
        reqBadge.innerText = `${requirements.length} Requirements`;
    }

    if (tbody) {
        if (requirements.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No requirement statements extracted.</td></tr>`;
        } else {
            tbody.innerHTML = requirements.map(r => {
                const st = (r.status || 'PASS').toUpperCase();
                const stClass = st === 'PASS' ? 'pass' : (st === 'FAIL' ? 'fail' : 'warning');
                return `
                    <tr>
                        <td><span class="req-id-pill">${escapeHtml(r.id)}</span></td>
                        <td class="req-desc-cell">${escapeHtml(r.text)}</td>
                        <td><span class="status-pill ${stClass}">${escapeHtml(st)}</span></td>
                        <td class="req-ev-cell">${escapeHtml(r.evidence || '-')}</td>
                    </tr>
                `;
            }).join("");
        }
    }

    // 6. Extracted Text
    const charCountLabel = document.getElementById("docCharCountLabel");
    const textPre = document.getElementById("docExtractedTextPre");

    if (charCountLabel) {
        const count = doc.characters_extracted || (doc.extracted_text ? doc.extracted_text.length : 0);
        charCountLabel.innerText = `${count.toLocaleString()} characters extracted`;
    }

    if (textPre) {
        textPre.innerText = doc.extracted_text || doc.preview || "";
    }

    // Smooth scroll to results
    resultsContainer.scrollIntoView({ behavior: "smooth", block: "start" });
}


function toggleExtractedTextView() {
    const container = document.getElementById("docExtractedTextContainer");
    const btnSpan = document.querySelector("#toggleTextBtn span");
    const icon = document.getElementById("toggleTextIcon");

    if (!container) return;

    if (container.style.display === "none") {
        container.style.display = "block";
        if (btnSpan) btnSpan.innerText = "Hide Text";
        if (icon) icon.className = "fa-solid fa-chevron-up";
    } else {
        container.style.display = "none";
        if (btnSpan) btnSpan.innerText = "Show Text";
        if (icon) icon.className = "fa-solid fa-chevron-down";
    }
}


function copyExtractedText() {
    const textPre = document.getElementById("docExtractedTextPre");
    if (!textPre || !textPre.innerText) return;

    navigator.clipboard.writeText(textPre.innerText)
        .then(() => {
            alert("Extracted document text copied to clipboard!");
        })
        .catch(() => {
            alert("Failed to copy to clipboard.");
        });
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
// DOCUMENT DROPZONE SETUP
// ==================================================

function setupDocumentUpload() {

    const dropzone = document.querySelector("#documentDropzone") || document.querySelector(".dropzone-box");
    if (!dropzone) return;

    // Prevent duplicate input creation if already present
    let input = document.getElementById("hiddenDocFileInput");
    if (!input) {
        input = document.createElement("input");
        input.id = "hiddenDocFileInput";
        input.type = "file";
        input.accept = ".pdf,.docx";
        input.style.display = "none";
        document.body.appendChild(input);

        input.addEventListener("change", function(event) {
            event.preventDefault();
            event.stopPropagation();
            if (input.files && input.files.length > 0) {
                const file = input.files[0];
                uploadDocument(file);
                input.value = ""; // Reset so same file can be re-selected if needed
            }
        });
    }

    // Open file browser on dropzone click
    dropzone.addEventListener("click", function(event) {
        event.preventDefault();
        event.stopPropagation();
        input.click();
    });

    // Drag and drop events on dropzone
    dropzone.addEventListener("dragover", function(event) {
        event.preventDefault();
        event.stopPropagation();
        dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", function(event) {
        event.preventDefault();
        event.stopPropagation();
        dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", function(event) {
        event.preventDefault();
        event.stopPropagation();
        dropzone.classList.remove("dragover");

        const files = event.dataTransfer.files;
        if (files && files.length > 0) {
            uploadDocument(files[0]);
        }
    });

    // Prevent default browser behavior of opening files when dropped outside dropzone
    window.addEventListener("dragover", function(event) {
        event.preventDefault();
    }, false);

    window.addEventListener("drop", function(event) {
        event.preventDefault();
    }, false);
}


// ==================================================
// STANDARDS SEARCH SETUP
// ==================================================

function setupStandardsSearch() {

    const button = document.querySelector(".search-submit-btn");
    const input = document.querySelector(".main-search-input-wrap input");
    const dropdowns = document.querySelectorAll(".filter-dropdowns select");

    if (button) {
        button.addEventListener("click", function(event) {
            event.preventDefault();
            const query = input ? input.value.trim() : "";
            searchStandards(query);
        });
    }

    if (input) {
        input.addEventListener("keydown", function(event) {
            if (event.key === "Enter") {
                event.preventDefault();
                searchStandards(input.value.trim());
            }
        });
    }

    dropdowns.forEach(select => {
        select.addEventListener("change", function() {
            const query = input ? input.value.trim() : "";
            searchStandards(query);
        });
    });
}


// ==================================================
// DOCUMENT INTELLIGENCE - SUMMARIZE / ANALYZE
// ==================================================

async function summarizeDocument(event) {

    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    // 1. If we already analyzed a document in this session, show it
    if (window.latestUploadedDocument) {
        renderDocumentAnalysis(window.latestUploadedDocument);
        return;
    }

    // 2. Fetch the most recently uploaded document from the backend
    const analyzeBtn = document.getElementById("docAnalyzeBtn");
    if (analyzeBtn) showLoading(analyzeBtn, "Analyzing...");

    try {

        const data = await apiRequest("/documents");

        if (!data.documents || data.documents.length === 0) {
            alert("Please upload a BIS PDF or DOCX document first.");
            return;
        }

        const latest = data.documents[0];
        const detailData = await apiRequest(`/documents/${latest.id}`);

        if (detailData.success && detailData.document) {
            window.latestUploadedDocument = detailData.document;
            const currentTag = document.getElementById("docCurrentFileName");
            if (currentTag) currentTag.innerText = detailData.document.filename;
            renderDocumentAnalysis(detailData.document);
        } else {
            alert("Could not load document analysis.");
        }

    } catch (error) {

        console.error("Document summary error:", error);

        alert(
            "Unable to analyze document.\n\n" +
            error.message
        );

    } finally {

        if (analyzeBtn) restoreButton(analyzeBtn);
    }
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
        (event) => {
            if (event) event.preventDefault();
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

        // Restore view from URL hash if present (e.g. #ai-chat, #document)
        const initialHash = window.location.hash.replace("#", "").trim();
        if (initialHash && document.getElementById(initialHash)) {
            switchView(initialHash);
        }
    }
);

// Listen for hash changes
window.addEventListener("hashchange", () => {
    const hash = window.location.hash.replace("#", "").trim();
    if (hash && document.getElementById(hash)) {
        switchView(hash);
    }
});