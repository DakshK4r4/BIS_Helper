/**
 * BIS Sahayak - Master Client Controller
 * Connects Figma UI components to real backend APIs with full Light/Dark support,
 * responsive mobile navigation, modal management, and live reactive updates.
 */

// ========================================================
// 1. APPLICATION STATE & METADATA
// ========================================================

const STATE = {
    currentView: "landing",
    theme: localStorage.getItem("bis_theme") || "light",
    currentUser: null,
    attachedDocumentContext: null,
    attachedDocumentFilename: null,
    speechRecognition: null,
    isListening: false,
    bookmarks: new Set(["IS 1239 (Part 1) : 2004", "IS 2062 : 2011"]),
    standardsSearchDebounce: null
};

const VIEW_TITLES = {
    landing: {
        title: "BIS Compliance Portal",
        subtitle: "Smart India Hackathon 2026 • Final Presentation"
    },
    "ai-chat": {
        title: "AI Standard Finder & Assistant",
        subtitle: "Conversational Compliance Gateway"
    },
    document: {
        title: "Document Intelligence & Gap Analyzer",
        subtitle: "Instant specifications audit engine"
    },
    dashboard: {
        title: "Interactive Audit & Compliance Dashboard",
        subtitle: "Smart Monitoring Gateway"
    },
    standards: {
        title: "National Standards Library (IS)",
        subtitle: "Enterprise standards, compliance status, and AI-assisted review workspace"
    },
    complaints: {
        title: "Complaints & Violation Tracker",
        subtitle: "National Compliance Violations Log"
    },
    notifications: {
        title: "Alerts & Notification Hub",
        subtitle: "Notification Center"
    },
    gateway: {
        title: "BIS Compliance Gateway",
        subtitle: "Official Government Platform Access"
    }
};

// ========================================================
// 2. DOM CONTENT LOADED & INITIALIZATION
// ========================================================

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initAuth();
    initRouter();
    initGlobalSearch();
    initEventListeners();
    initSpeechRecognition();

    // Initial data fetch
    loadNotificationsCount();
    loadDashboardMetrics();
    loadStandardsCatalog();
    loadComplaintsLog();
});

// ========================================================
// 3. THEME SYSTEM (LIGHT & DARK MODES)
// ========================================================

function initTheme() {
    setTheme(STATE.theme);

    const btnLight = document.getElementById("btnThemeLight");
    const btnDark = document.getElementById("btnThemeDark");
    const mobileToggle = document.getElementById("mobileThemeToggle");

    if (btnLight) btnLight.addEventListener("click", () => setTheme("light"));
    if (btnDark) btnDark.addEventListener("click", () => setTheme("dark"));
    if (mobileToggle) {
        mobileToggle.addEventListener("click", () => {
            const nextTheme = STATE.theme === "light" ? "dark" : "light";
            setTheme(nextTheme);
        });
    }
}

function setTheme(theme) {
    STATE.theme = theme;
    localStorage.setItem("bis_theme", theme);
    document.documentElement.setAttribute("data-theme", theme);

    const btnLight = document.getElementById("btnThemeLight");
    const btnDark = document.getElementById("btnThemeDark");
    const mobileIcon = document.querySelector("#mobileThemeToggle i");

    if (btnLight && btnDark) {
        btnLight.classList.toggle("active", theme === "light");
        btnDark.classList.toggle("active", theme === "dark");
    }

    if (mobileIcon) {
        mobileIcon.className = theme === "dark" ? "fa-regular fa-sun" : "fa-regular fa-moon";
    }
}

// ========================================================
// 4. AUTHENTICATION & USER MANAGEMENT
// ========================================================

async function initAuth() {
    try {
        const res = await authApi.getMe();
        if (res?.user) {
            STATE.currentUser = res.user;
        } else {
            STATE.currentUser = {
                id: "usr_officer_demo_01",
                name: "Dr. R. K. Prasad",
                role: "Lead Quality Inspector",
                email: "rkprasad@nic.in"
            };
        }
    } catch (_) {
        STATE.currentUser = {
            id: "usr_officer_demo_01",
            name: "Dr. R. K. Prasad",
            role: "Lead Quality Inspector",
            email: "rkprasad@nic.in"
        };
    }
    updateUserInterface();
}

function updateUserInterface() {
    const user = STATE.currentUser;
    if (!user) return;

    const initials = user.name ? user.name.split(" ").map(p => p[0]).join("").slice(0, 2).toUpperCase() : "RP";
    
    const headerAvatar = document.getElementById("headerAvatar");
    const mobileAvatar = document.getElementById("mobileUserAvatar");
    const headerName = document.getElementById("headerUserName");
    const headerRole = document.getElementById("headerUserRole");
    const compNameInput = document.getElementById("compName");
    const compContactInput = document.getElementById("compContact");

    if (headerAvatar) headerAvatar.innerText = initials;
    if (mobileAvatar) mobileAvatar.innerText = initials;
    if (headerName) headerName.innerText = user.name;
    if (headerRole) headerRole.innerText = user.role || "Lead Quality Inspector";
    if (compNameInput && !compNameInput.value) compNameInput.value = user.name;
    if (compContactInput && !compContactInput.value) compContactInput.value = user.email || "";
}

function handleGatewayDemoRoleSelect(role) {
    const emailInput = document.getElementById("gwEmail");
    const roleBtns = document.querySelectorAll(".demo-role-btn");
    roleBtns.forEach(btn => btn.classList.toggle("active", btn.dataset.role === role));

    if (role === "officer") {
        if (emailInput) emailInput.value = "rkprasad@nic.in";
    } else if (role === "manufacturer") {
        if (emailInput) emailInput.value = "sunita@apex-elec.com";
    } else if (role === "consumer") {
        if (emailInput) emailInput.value = "amit.sharma@example.com";
    }
}

async function handleGatewayLogin(event) {
    if (event) event.preventDefault();
    const email = document.getElementById("gwEmail")?.value.trim();
    const btn = document.getElementById("btnGatewaySubmit");

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Authenticating...`;
    }

    try {
        let role = "officer";
        let name = "Dr. R. K. Prasad";
        let userRoleDesc = "Lead Quality Inspector";

        if (email.includes("sunita") || email.includes("mfg")) {
            role = "manufacturer";
            name = "Sunita Verma";
            userRoleDesc = "Electronics Manufacturer";
        } else if (email.includes("amit") || email.includes("consumer") || email.includes("citizen")) {
            role = "consumer";
            name = "Amit Sharma";
            userRoleDesc = "Informed Citizen";
        }

        const res = await authApi.loginDemo(role, email, name);
        if (res.user) {
            STATE.currentUser = { ...res.user, role: userRoleDesc };
            localStorage.setItem("bis_user", JSON.stringify({ ...res.user, token: res.token }));
        }

        updateUserInterface();
        showToast("Authenticated successfully. Welcome to BIS Sahayak!", "success");
        navigateTo("landing");
    } catch (err) {
        showToast(err.message || "Authentication failed", "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-lock"></i> Secure Authenticate`;
        }
    }
}

async function handleLogout() {
    try {
        await authApi.logout();
    } catch (_) {}
    localStorage.removeItem("bis_user");
    localStorage.removeItem("bis_token");
    showToast("Signed out of official workstation.", "info");
    navigateTo("gateway");
}

// ========================================================
// 5. SPA ROUTER & NAVIGATION
// ========================================================

function initRouter() {
    const handleHash = () => {
        const hash = (window.location.hash || "#landing").replace(/^#/, "");
        navigateTo(hash, false);
    };

    window.addEventListener("hashchange", handleHash);
    handleHash();

    // Desktop nav clicks
    document.querySelectorAll(".sidebar-nav .nav-item").forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            const view = link.dataset.view;
            if (view) navigateTo(view);
        });
    });

    // Mobile nav clicks
    document.querySelectorAll(".mobile-bottom-nav .mobile-nav-item").forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            const view = link.dataset.view;
            if (view) navigateTo(view);
        });
    });
}

function navigateTo(viewId, updateHash = true) {
    if (!VIEW_TITLES[viewId]) {
        viewId = "landing";
    }

    STATE.currentView = viewId;
    if (updateHash) {
        try {
            history.pushState(null, "", `#${viewId}`);
        } catch (_) {
            window.location.hash = `#${viewId}`;
        }
    }

    // Switch active view section
    document.querySelectorAll(".view-section").forEach(sec => sec.classList.remove("active"));
    const targetSection = document.getElementById(`view-${viewId}`);
    if (targetSection) targetSection.classList.add("active");

    // Update active nav item in desktop sidebar
    document.querySelectorAll(".sidebar-nav .nav-item").forEach(nav => {
        nav.classList.toggle("active", nav.dataset.view === viewId);
    });

    // Update active nav item in mobile bottom bar
    document.querySelectorAll(".mobile-bottom-nav .mobile-nav-item").forEach(nav => {
        nav.classList.toggle("active", nav.dataset.view === viewId);
    });

    // Update top header titles
    const meta = VIEW_TITLES[viewId] || VIEW_TITLES.landing;
    const titleEl = document.getElementById("pageTitle");
    const subEl = document.getElementById("pageSubtitle");
    if (titleEl) titleEl.innerText = meta.title;
    if (subEl) subEl.innerText = meta.subtitle;

    // View-specific initialization triggers
    if (viewId === "dashboard") loadDashboardMetrics();
    if (viewId === "standards") loadStandardsCatalog();
    if (viewId === "complaints") loadComplaintsLog();
    if (viewId === "notifications") loadNotificationsHub();
    if (viewId === "landing") loadLandingPageData();

    // Close any open dropdowns
    closeDropdowns();
    window.scrollTo({ top: 0, behavior: "smooth" });
}

// ========================================================
// 6. GLOBAL SEARCH & EVENT LISTENERS
// ========================================================

function initGlobalSearch() {
    const globalInput = document.getElementById("globalStandardsSearch");
    if (globalInput) {
        globalInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                const query = globalInput.value.trim();
                if (query) {
                    navigateTo("standards");
                    const libInput = document.getElementById("standardsKeywordInput");
                    if (libInput) {
                        libInput.value = query;
                        loadStandardsCatalog();
                    }
                }
            }
        });
    }
}

function initEventListeners() {
    // User profile dropdown toggle
    const profileBtn = document.getElementById("userProfileBtn");
    const dropdown = document.getElementById("userDropdown");
    if (profileBtn && dropdown) {
        profileBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            dropdown.classList.toggle("show");
        });
    }

    document.addEventListener("click", () => closeDropdowns());

    // Gateway switch and logout from dropdown
    document.getElementById("btnSwitchGateway")?.addEventListener("click", () => navigateTo("gateway"));
    document.getElementById("btnOpenVerification")?.addEventListener("click", () => openModal("verificationModal"));
    document.getElementById("btnLogout")?.addEventListener("click", handleLogout);

    // Hero action buttons
    document.getElementById("heroCtaQuery")?.addEventListener("click", () => navigateTo("ai-chat"));
    document.getElementById("heroCtaWalkthrough")?.addEventListener("click", () => openModal("walkthroughModal"));

    // Toolkit cards on Home
    document.getElementById("toolkitAiFinder")?.addEventListener("click", () => navigateTo("ai-chat"));
    document.getElementById("toolkitDocAnalyzer")?.addEventListener("click", () => navigateTo("document"));
    document.getElementById("toolkitHallmark")?.addEventListener("click", () => {
        openModal("verificationModal");
        switchVerifyTab("hallmark");
    });

    // AI chat query triggers
    document.getElementById("btnNewAiChat")?.addEventListener("click", resetAiChatSession);
    document.getElementById("btnAttachDoc")?.addEventListener("click", () => document.getElementById("aiDocAttachInput")?.click());
    document.getElementById("aiDocAttachInput")?.addEventListener("change", handleAiDocAttachment);

    // Document Analyzer dropzone
    const dropzone = document.getElementById("docDropzone");
    const fileInput = document.getElementById("docFileInput");
    const btnBrowse = document.getElementById("btnBrowseFiles");

    if (btnBrowse && fileInput) {
        btnBrowse.addEventListener("click", () => fileInput.click());
        fileInput.addEventListener("change", (e) => {
            if (e.target.files?.length > 0) handleDocumentUpload(e.target.files[0]);
        });
    }

    if (dropzone) {
        dropzone.addEventListener("dragover", (e) => {
            e.preventDefault();
            dropzone.classList.add("dragover");
        });
        dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
        dropzone.addEventListener("drop", (e) => {
            e.preventDefault();
            dropzone.classList.remove("dragover");
            if (e.dataTransfer?.files?.length > 0) handleDocumentUpload(e.dataTransfer.files[0]);
        });
    }

    // Standards filters
    const stdKeyword = document.getElementById("standardsKeywordInput");
    const stdDivision = document.getElementById("standardsDivisionSelect");
    const stdStatus = document.getElementById("standardsStatusSelect");

    const debouncedSearch = () => {
        clearTimeout(STATE.standardsSearchDebounce);
        STATE.standardsSearchDebounce = setTimeout(() => loadStandardsCatalog(), 300);
    };

    stdKeyword?.addEventListener("input", debouncedSearch);
    stdDivision?.addEventListener("change", loadStandardsCatalog);
    stdStatus?.addEventListener("change", loadStandardsCatalog);

    // Sector pills
    document.querySelectorAll("#sectorPills .sector-pill").forEach(pill => {
        pill.addEventListener("click", () => {
            document.querySelectorAll("#sectorPills .sector-pill").forEach(p => p.classList.remove("active"));
            pill.classList.add("active");
            loadStandardsCatalog();
        });
    });

    // Complaints triggers
    document.getElementById("btnOpenComplaintModal")?.addEventListener("click", () => openModal("complaintModal"));
    document.getElementById("complaintsSearchInput")?.addEventListener("input", () => loadComplaintsLog());
    document.getElementById("complaintsSeverityFilter")?.addEventListener("change", () => loadComplaintsLog());
    document.getElementById("complaintsStatusFilter")?.addEventListener("change", () => loadComplaintsLog());

    // Notifications triggers
    document.getElementById("btnMarkAllNotifsRead")?.addEventListener("click", handleMarkAllNotifsRead);
    document.querySelectorAll("#notifCategoryTabs .notif-tab").forEach(tab => {
        tab.addEventListener("click", () => {
            document.querySelectorAll("#notifCategoryTabs .notif-tab").forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            loadNotificationsHub();
        });
    });

    // Gateway demo selector clicks
    document.querySelectorAll(".demo-role-btn").forEach(btn => {
        btn.addEventListener("click", () => handleGatewayDemoRoleSelect(btn.dataset.role));
    });

    // Password visibility toggle
    document.getElementById("btnTogglePassword")?.addEventListener("click", () => {
        const pwdInput = document.getElementById("gwPassword");
        const icon = document.querySelector("#btnTogglePassword i");
        if (pwdInput && icon) {
            const isPassword = pwdInput.type === "password";
            pwdInput.type = isPassword ? "text" : "password";
            icon.className = isPassword ? "fa-regular fa-eye-slash" : "fa-regular fa-eye";
        }
    });

    // Close modals on ESC key
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            document.querySelectorAll(".modal-overlay.active").forEach(m => m.classList.remove("active"));
        }
    });

    // Global custom event listeners from client.js
    window.addEventListener("bis:network-error", (e) => {
        showToast("Unable to connect to BIS Sahayak backend. Ensure Flask is running on port 5000.", "error");
    });
    window.addEventListener("bis:unauthorized", () => {
        showToast("Session expired. Please authenticate via Gateway.", "warning");
        navigateTo("gateway");
    });
}

function closeDropdowns() {
    document.getElementById("userDropdown")?.classList.remove("show");
}

// ========================================================
// 7. VIEW 1: HOME PAGE DATA & METRICS
// ========================================================

async function loadLandingPageData() {
    try {
        const [dashData, stdData, histData] = await Promise.allSettled([
            dashboardApi.getMetrics(),
            standardsApi.search(),
            historyApi.getAll()
        ]);

        if (dashData.status === "fulfilled" && dashData.value?.metrics) {
            const m = dashData.value.metrics;
            const auditsEl = document.getElementById("homeAuditsCount");
            const stdEl = document.getElementById("statTotalStandards");
            if (auditsEl) auditsEl.innerText = m.certificates * 7 || "128";
            if (stdEl) stdEl.innerText = `${m.standards_tracked || 18}+ Standards`;
        }

        if (histData.status === "fulfilled" && histData.value?.history?.length > 0) {
            renderHomeActivityFeed(histData.value.history.slice(0, 4));
        }
    } catch (_) {}
}

function renderHomeActivityFeed(items) {
    const feed = document.getElementById("homeActivityFeed");
    if (!feed || !items || items.length === 0) return;

    feed.innerHTML = items.map(item => {
        let badgeClass = "badge-neutral";
        let statusText = item.status || "Completed";
        if (statusText === "SUCCESS" || statusText === "VERIFIED" || statusText === "Compliant") {
            badgeClass = "badge-success";
            statusText = "Compliant";
        } else if (statusText === "PARTIAL" || statusText === "Partially Compliant") {
            badgeClass = "badge-warning";
            statusText = "Partially Compliant";
        }

        const timeStr = item.created_at ? formatTimeAgo(item.created_at) : "Recently";
        return `
            <div class="activity-feed-item">
                <div class="feed-item-left">
                    <span class="feed-title">${escapeHtml(item.title)}</span>
                    <span class="feed-meta">${escapeHtml(item.action_type)} • ${timeStr}</span>
                </div>
                <span class="badge ${badgeClass}">${statusText}</span>
            </div>
        `;
    }).join("");
}

// ========================================================
// 8. VIEW 2: AI ASSISTANT / CHAT (POST /api/ai/query)
// ========================================================

async function handleAiChatSubmit(event) {
    if (event) event.preventDefault();
    const input = document.getElementById("aiQueryInput");
    const query = input?.value.trim();
    if (!query) return;

    input.value = "";

    // Append user message bubble
    appendChatBubble("user", query, STATE.currentUser?.name ? STATE.currentUser.name.split(" ").map(p => p[0]).join("").slice(0, 2).toUpperCase() : "RP");

    // Append typing indicator bot bubble
    const typingBubbleId = appendChatBubble("bot", `<i class="fa-solid fa-spinner fa-spin"></i> Analyzing Indian Standards & legal codes...`, `<i class="fa-solid fa-wand-magic-sparkles"></i>`);

    try {
        const res = await aiApi.query(query, STATE.attachedDocumentContext, STATE.attachedDocumentFilename);
        
        // Remove typing indicator
        document.getElementById(typingBubbleId)?.remove();

        if (res.answer) {
            let contentHtml = formatMarkdown(res.answer);

            // If recommended standard is present, render standard card
            if (res.recommended_standard) {
                const std = res.recommended_standard;
                contentHtml += `
                    <div class="embedded-standard-card">
                        <div class="std-card-top">
                            <span class="std-code-tag">${escapeHtml(std.is_number)}</span>
                            <span class="badge badge-success">${res.confidence_score ? Math.round(res.confidence_score * 100) : 95}% Match</span>
                        </div>
                        <div class="std-title">${escapeHtml(std.title || "")}</div>
                        <div class="std-desc">${escapeHtml(std.description || "")}</div>
                        <div class="std-meta-tags">
                            <span class="meta-pill">Category: ${escapeHtml(std.category || "General")}</span>
                            <span class="meta-pill">Status: ${escapeHtml(std.status || "Active")}</span>
                            <span class="meta-pill">Certification: ${escapeHtml(std.certification || "Product Certification")}</span>
                        </div>
                    </div>
                `;

                // Update context text
                const ctxEl = document.getElementById("activeAiContextText");
                if (ctxEl) ctxEl.innerText = `Current Subject Context: ${std.is_number} (${std.title})`;
            }

            appendChatBubble("bot", contentHtml, `<i class="fa-solid fa-wand-magic-sparkles"></i>`, true);
        } else {
            appendChatBubble("bot", "No matching standard guidance found. Please try rephrasing your product inquiry.", `<i class="fa-solid fa-wand-magic-sparkles"></i>`);
        }

        // Add to past conversations
        addPastConversation(query);
    } catch (err) {
        document.getElementById(typingBubbleId)?.remove();
        appendChatBubble("bot", `<span style="color: var(--danger);">Error processing query: ${escapeHtml(err.message)}</span>`, `<i class="fa-solid fa-triangle-exclamation"></i>`, true);
    }
}

function appendChatBubble(sender, content, avatarContent, isRawHtml = false) {
    const feed = document.getElementById("chatFeed");
    if (!feed) return "";

    const id = `bubble_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${sender}`;
    bubble.id = id;

    bubble.innerHTML = `
        <div class="chat-avatar">${avatarContent}</div>
        <div class="bubble-content">
            ${isRawHtml ? content : escapeHtml(content)}
        </div>
    `;

    feed.appendChild(bubble);
    feed.scrollTop = feed.scrollHeight;
    return id;
}

function resetAiChatSession() {
    const feed = document.getElementById("chatFeed");
    if (feed) {
        feed.innerHTML = `
            <div class="chat-bubble bot">
                <div class="chat-avatar"><i class="fa-solid fa-wand-magic-sparkles"></i></div>
                <div class="bubble-content">
                    Greetings! I am BIS Sahayak, your AI Standards Assistant. Ask any technical query regarding Indian Standards (IS), mandatory ISI certification clauses, or testing tolerances.
                </div>
            </div>
        `;
    }
    clearAiAttachment();
}

function loadPromptQuery(promptText) {
    const input = document.getElementById("aiQueryInput");
    if (input) {
        input.value = promptText;
        input.focus();
    }
}

function addPastConversation(title) {
    const list = document.getElementById("aiPastConversations");
    if (!list) return;

    const item = document.createElement("div");
    item.className = "past-query-item";
    item.innerHTML = `<i class="fa-regular fa-message"></i> ${escapeHtml(title.slice(0, 32))}`;
    item.onclick = () => loadPromptQuery(title);
    list.prepend(item);
}

function handleAiDocAttachment(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        STATE.attachedDocumentContext = e.target.result;
        STATE.attachedDocumentFilename = file.name;

        const chip = document.getElementById("attachedFileChip");
        const nameEl = document.getElementById("attachedFileName");
        if (chip && nameEl) {
            nameEl.innerText = file.name;
            chip.style.display = "inline-flex";
        }
        showToast(`Document "${file.name}" attached as context.`, "info");
    };
    reader.readAsText(file);
}

function clearAiAttachment() {
    STATE.attachedDocumentContext = null;
    STATE.attachedDocumentFilename = null;
    const chip = document.getElementById("attachedFileChip");
    const input = document.getElementById("aiDocAttachInput");
    if (chip) chip.style.display = "none";
    if (input) input.value = "";
}

// Voice Recognition Speech-to-Text
function initSpeechRecognition() {
    const btnVoice = document.getElementById("btnVoiceQuery");
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRec) {
        if (btnVoice) btnVoice.style.display = "none";
        return;
    }

    const recognition = new SpeechRec();
    recognition.continuous = false;
    recognition.lang = "en-IN";

    recognition.onstart = () => {
        STATE.isListening = true;
        btnVoice?.classList.add("text-danger");
        showToast("Listening... Speak your BIS inquiry.", "info");
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        const input = document.getElementById("aiQueryInput");
        if (input) input.value = transcript;
    };

    recognition.onend = () => {
        STATE.isListening = false;
        btnVoice?.classList.remove("text-danger");
    };

    if (btnVoice) {
        btnVoice.addEventListener("click", () => {
            if (STATE.isListening) {
                recognition.stop();
            } else {
                recognition.start();
            }
        });
    }
}

// ========================================================
// 9. VIEW 3: DOCUMENT INTELLIGENCE (POST /api/documents/upload)
// ========================================================

async function handleDocumentUpload(file) {
    if (!file) return;

    const allowed = ["pdf", "docx", "png", "jpg", "jpeg"];
    const ext = file.name.split(".").pop().toLowerCase();
    if (!allowed.includes(ext)) {
        showToast("Unsupported file format. Please upload PDF, DOCX, PNG, or JPG.", "warning");
        return;
    }

    const dropzone = document.getElementById("docDropzone");
    if (dropzone) {
        dropzone.innerHTML = `
            <div style="padding: 24px;">
                <i class="fa-solid fa-spinner fa-spin doc-upload-icon"></i>
                <h3>Extracting & Analyzing "${escapeHtml(file.name)}"...</h3>
                <p>Parsing technical clauses, dimensional bounds, and chemical schedules via BIS Engine.</p>
            </div>
        `;
    }

    try {
        const res = await documentsApi.upload(file);
        showToast("Document analyzed successfully!", "success");

        // Restore upload box
        if (dropzone) {
            dropzone.innerHTML = `
                <input type="file" id="docFileInput" style="display: none;" accept=".pdf,.docx,.png,.jpg,.jpeg">
                <i class="fa-solid fa-cloud-arrow-up doc-upload-icon"></i>
                <h3>Analyze Product Specification Manual</h3>
                <p>Drop PDF, DOCX or images here, or browse. Standard verification starts automatically.</p>
                <button type="button" class="btn btn-primary" id="btnBrowseFiles" onclick="document.getElementById('docFileInput').click()">
                    Browse files
                </button>
                <div class="format-tags-row">PDF • DOCX • PNG • JPG</div>
            `;
            document.getElementById("docFileInput")?.addEventListener("change", (e) => {
                if (e.target.files?.length > 0) handleDocumentUpload(e.target.files[0]);
            });
        }

        renderDocumentIntelligenceResult(res.document || res);
    } catch (err) {
        showToast(err.message || "Failed to analyze document", "error");
        if (dropzone) {
            dropzone.innerHTML = `
                <input type="file" id="docFileInput" style="display: none;" accept=".pdf,.docx,.png,.jpg,.jpeg">
                <i class="fa-solid fa-triangle-exclamation doc-upload-icon" style="color: var(--danger);"></i>
                <h3>Upload Failed</h3>
                <p>${escapeHtml(err.message)}</p>
                <button type="button" class="btn btn-outline" onclick="document.getElementById('docFileInput').click()">
                    Try Again
                </button>
            `;
        }
    }
}

function renderDocumentIntelligenceResult(doc) {
    if (!doc) return;

    const score = doc.compliance_score || doc.compliance?.score || 78;
    const scoreEl = document.getElementById("displayScore");
    const verdictEl = document.getElementById("displayVerdict");
    const gaugeCircle = document.getElementById("gaugeCircle");

    if (scoreEl) scoreEl.innerText = `${score}%`;

    // SVG dashoffset calculation (Circumference ~ 251.2)
    if (gaugeCircle) {
        const offset = 251.2 - (251.2 * score) / 100;
        gaugeCircle.style.strokeDashoffset = offset;
    }

    if (verdictEl) {
        let verdict = "Compliant";
        let badgeClass = "badge-success";
        if (score < 60) {
            verdict = "Non-Compliant";
            badgeClass = "badge-danger";
        } else if (score < 85) {
            verdict = "Partially Compliant";
            badgeClass = "badge-warning";
        }
        verdictEl.className = `badge ${badgeClass}`;
        verdictEl.innerText = `Verdict: ${verdict}`;
    }

    // Extracted Specs
    const meta = doc.metadata || {};
    document.getElementById("specProductName").innerText = meta.product || doc.filename?.replace(/\.[^/.]+$/, "") || "Cold-Rolled Carbon Tubes";
    document.getElementById("specManufacturer").innerText = meta.manufacturer || "Tata Quality Castings";
    document.getElementById("specModelCode").innerText = meta.model || "CRC-PIPE-1239";
    document.getElementById("specDetectedCode").innerText = meta.standard || "IS 1239 Part 1 (2004)";

    // Requirements Checklist
    const reqList = document.getElementById("requirementsList");
    const reqCounter = document.getElementById("checklistCounter");

    if (reqList && doc.requirements && doc.requirements.length > 0) {
        const passedCount = doc.requirements.filter(r => r.status === "PASS").length;
        const failedCount = doc.requirements.length - passedCount;

        if (reqCounter) reqCounter.innerText = `Total Checklist: ${doc.requirements.length} (${passedCount} passed, ${failedCount} failed)`;

        reqList.innerHTML = doc.requirements.map(req => {
            const isPass = req.status === "PASS";
            return `
                <div class="req-item">
                    <div class="req-left">
                        <i class="fa-solid ${isPass ? 'fa-circle-check pass' : 'fa-triangle-exclamation fail'} req-status-icon"></i>
                        <div>
                            <div class="req-title">${escapeHtml(req.clause || req.parameter || "Standard Requirement")}</div>
                            <div class="req-extract">${escapeHtml(req.extracted_value || req.observed || "")}</div>
                        </div>
                    </div>
                    <span class="badge ${isPass ? 'badge-success' : 'badge-danger'}">${isPass ? 'Pass' : 'Fail'}</span>
                </div>
            `;
        }).join("");
    }

    // Recommendations
    const recList = document.getElementById("recommendationsList");
    if (recList && doc.recommendations && doc.recommendations.length > 0) {
        recList.innerHTML = doc.recommendations.map(rec => {
            const isCritical = (rec.priority || "").toUpperCase() === "HIGH" || (rec.type || "").toUpperCase() === "CRITICAL";
            return `
                <div class="rec-callout ${isCritical ? 'critical' : 'warning'}">
                    <div class="rec-body">
                        <span class="badge ${isCritical ? 'badge-danger' : 'badge-warning'}" style="margin-bottom: 4px;">${isCritical ? 'CRITICAL' : 'WARNING'}</span>
                        <p>${escapeHtml(rec.action || rec.description || rec)}</p>
                        <a href="#standards" class="rec-action-link">View Indian Standard guidelines &rarr;</a>
                    </div>
                </div>
            `;
        }).join("");
    }
}

// ========================================================
// 10. VIEW 4: DASHBOARD (GET /api/dashboard)
// ========================================================

async function loadDashboardMetrics() {
    try {
        const res = await dashboardApi.getMetrics();
        if (!res.metrics) return;

        const m = res.metrics;
        const pEl = document.getElementById("dashProducts");
        const cEl = document.getElementById("dashCertificates");
        const rEl = document.getElementById("dashRenewals");
        const compEl = document.getElementById("dashCompliance");

        if (pEl) pEl.innerText = m.products || "42";
        if (cEl) cEl.innerText = m.certificates || "18";
        if (rEl) rEl.innerText = m.reports ? Math.min(m.reports, 4) : "2";
        if (compEl) compEl.innerText = `${m.compliance || "84.2"}%`;
    } catch (_) {}
}

// ========================================================
// 11. VIEW 5: STANDARDS CATALOG (GET /api/standards)
// ========================================================

async function loadStandardsCatalog() {
    const q = document.getElementById("standardsKeywordInput")?.value.trim() || "";
    const division = document.getElementById("standardsDivisionSelect")?.value || "";
    const status = document.getElementById("standardsStatusSelect")?.value || "";
    const activeSectorPill = document.querySelector("#sectorPills .sector-pill.active")?.dataset.sector || "";

    const params = {};
    if (q) params.q = q;
    if (division) params.category = division;
    if (activeSectorPill) params.category = activeSectorPill;
    if (status) params.status = status;

    const tbody = document.getElementById("standardsTableBody");
    const countEl = document.getElementById("standardsCountText");

    if (tbody) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 24px; color: var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Loading Indian Standards catalog...</td></tr>`;
    }

    try {
        const res = await standardsApi.search(params);
        const list = res.standards || [];

        if (countEl) countEl.innerText = `Showing ${list.length} of ${res.count || "24,012"} Standards`;

        if (!list || list.length === 0) {
            if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 28px; color: var(--text-muted);">No standards found matching your criteria. Try searching "IS 1239" or "steel".</td></tr>`;
            return;
        }

        if (tbody) {
            tbody.innerHTML = list.map(std => {
                const isBookmarked = STATE.bookmarks.has(std.is_number);
                let badgeType = "badge-primary";
                if (std.status === "Active") badgeType = "badge-success";
                if (std.status === "Voluntary") badgeType = "badge-neutral";
                if (std.status === "Revision") badgeType = "badge-warning";

                return `
                    <tr>
                        <td><strong>${escapeHtml(std.is_number)}</strong><br><small style="color: var(--text-muted); font-size: 0.72rem;">${escapeHtml(std.category || "")}</small></td>
                        <td>
                            <div style="font-weight: 600; color: var(--text-primary);">${escapeHtml(std.title)}</div>
                            <small style="color: var(--text-muted); font-size: 0.74rem;">Type: ${escapeHtml(std.certification || "Product Licensing")}</small>
                        </td>
                        <td><span class="badge ${badgeType}">${escapeHtml(std.status || "Mandatory")}</span></td>
                        <td>${std.year ? std.year : "2024"}</td>
                        <td>
                            <div style="display: flex; gap: 8px; align-items: center;">
                                <button type="button" class="btn btn-outline btn-sm" onclick="openStandardModal('${escapeHtml(std.is_number)}')">
                                    View PDF
                                </button>
                                <button type="button" class="btn btn-outline btn-sm" style="padding: 6px 8px;" onclick="toggleBookmark('${escapeHtml(std.is_number)}')">
                                    <i class="${isBookmarked ? 'fa-solid' : 'fa-regular'} fa-bookmark" style="${isBookmarked ? 'color: var(--primary);' : ''}"></i>
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
            }).join("");
        }
    } catch (err) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 24px; color: var(--danger);">Failed to load standards: ${escapeHtml(err.message)}</td></tr>`;
    }
}

async function openStandardModal(isNumber) {
    try {
        const res = await standardsApi.getDetail(isNumber);
        const std = res.standard;
        if (!std) return;

        document.getElementById("stdModalCode").innerText = std.is_number;
        document.getElementById("stdModalBody").innerHTML = `
            <div style="display: flex; flex-direction: column; gap: 14px;">
                <h4 style="font-size: 1.05rem; font-weight: 700; color: var(--text-primary);">${escapeHtml(std.title)}</h4>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <span class="badge badge-primary">${escapeHtml(std.category || "General")}</span>
                    <span class="badge badge-success">${escapeHtml(std.status || "Active")}</span>
                    <span class="badge badge-neutral">Year: ${std.year || "N/A"}</span>
                </div>
                <p style="font-size: 0.88rem; color: var(--text-secondary); line-height: 1.5;">${escapeHtml(std.description || "No full scope description provided in registry.")}</p>
                <div style="background: var(--surface-alt); padding: 12px; border-radius: var(--radius-md); font-size: 0.8rem;">
                    <strong>Certification Scheme:</strong> ${escapeHtml(std.certification || "Product Certification (Scheme-I)")}<br>
                    <strong>Keywords:</strong> ${escapeHtml(std.keywords || "N/A")}
                </div>
            </div>
        `;

        document.getElementById("btnAskAiAboutStandard").onclick = () => {
            closeModal("standardDetailModal");
            navigateTo("ai-chat");
            loadPromptQuery(`Explain mandatory compliance clauses and testing tolerances under ${std.is_number}`);
        };

        openModal("standardDetailModal");
    } catch (err) {
        showToast("Standard details unavailable", "error");
    }
}

function toggleBookmark(isNumber) {
    if (STATE.bookmarks.has(isNumber)) {
        STATE.bookmarks.delete(isNumber);
        showToast(`Removed ${isNumber} from Watchlist.`, "info");
    } else {
        STATE.bookmarks.add(isNumber);
        showToast(`Bookmarked ${isNumber} to Watchlist!`, "success");
    }
    loadStandardsCatalog();
}

// ========================================================
// 12. VIEW 6: COMPLAINTS & VIOLATION LOG (GET/POST /api/complaints)
// ========================================================

async function loadComplaintsLog() {
    const q = document.getElementById("complaintsSearchInput")?.value.trim() || "";
    const status = document.getElementById("complaintsStatusFilter")?.value || "";

    const params = {};
    if (q) params.q = q;
    if (status) params.status = status;

    const tbody = document.getElementById("complaintsTableBody");
    const countEl = document.getElementById("complaintsCountText");

    try {
        const res = await complaintsApi.getAll(params);
        const list = res.complaints || [];

        if (countEl) countEl.innerText = `Showing ${list.length} records of ${res.count || 148}`;
        const totalStat = document.getElementById("compTotalCount");
        if (totalStat) totalStat.innerText = res.count || 148;

        if (!list || list.length === 0) {
            if (tbody) tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 24px; color: var(--text-muted);">No complaints matching your query.</td></tr>`;
            return;
        }

        if (tbody) {
            tbody.innerHTML = list.map(c => {
                let statusBadge = "badge-warning";
                if (c.status === "RESOLVED") statusBadge = "badge-success";
                if (c.status === "UNDER_REVIEW") statusBadge = "badge-primary";
                if (c.status === "PENDING") statusBadge = "badge-danger";

                return `
                    <tr>
                        <td><strong>${escapeHtml(c.complaint_id)}</strong></td>
                        <td><span style="color: var(--primary); font-weight: 600;">${escapeHtml(c.ref_number || "General")}</span></td>
                        <td>
                            <strong>${escapeHtml(c.subject)}</strong><br>
                            <small style="color: var(--text-muted); font-size: 0.74rem;">${escapeHtml(c.category)}</small>
                        </td>
                        <td><span class="badge ${c.category?.includes('Misuse') ? 'badge-danger' : 'badge-warning'}">High</span></td>
                        <td>${escapeHtml(c.name || "Assigned Officer")}</td>
                        <td><span class="badge ${statusBadge}">${escapeHtml(c.status || "SUBMITTED")}</span></td>
                        <td>
                            <button type="button" class="btn btn-outline btn-sm" onclick="investigateComplaint('${escapeHtml(c.complaint_id)}', '${escapeHtml(c.subject)}')">
                                Investigate
                            </button>
                        </td>
                    </tr>
                `;
            }).join("");
        }
    } catch (_) {}
}

async function handleComplaintSubmit(event) {
    if (event) event.preventDefault();
    const btn = document.getElementById("btnSubmitComplaint");
    if (btn) {
        btn.disabled = true;
        btn.innerText = "Submitting...";
    }

    const payload = {
        name: document.getElementById("compName")?.value.trim(),
        contact: document.getElementById("compContact")?.value.trim(),
        category: document.getElementById("compCategory")?.value,
        ref_number: document.getElementById("compRef")?.value.trim(),
        subject: document.getElementById("compSubject")?.value.trim(),
        description: document.getElementById("compDesc")?.value.trim()
    };

    try {
        const res = await complaintsApi.submit(payload);
        showToast(`Complaint registered successfully! Tracking ID: ${res.tracking_id || res.complaint_id}`, "success");
        closeModal("complaintModal");
        document.getElementById("complaintForm")?.reset();
        loadComplaintsLog();
        loadNotificationsCount();
    } catch (err) {
        showToast(err.message || "Failed to submit complaint", "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = "Submit Grievance";
        }
    }
}

function investigateComplaint(id, subject) {
    showToast(`Investigating complaint record ${id}: ${subject}`, "info");
    navigateTo("ai-chat");
    loadPromptQuery(`Audit violation details and applicable legal enforcement clauses for complaint ${id}: ${subject}`);
}

// ========================================================
// 13. VIEW 7: ALERTS & NOTIFICATIONS HUB
// ========================================================

async function loadNotificationsCount() {
    try {
        const res = await notificationsApi.getAll();
        const badge = document.getElementById("sidebarNotifBadge");
        const tabCount = document.getElementById("notifTabAllCount");
        const unread = res.unread_count !== undefined ? res.unread_count : 3;

        if (badge) {
            badge.innerText = unread;
            badge.style.display = unread > 0 ? "inline-block" : "none";
        }
        if (tabCount) tabCount.innerText = res.notifications?.length || 32;
    } catch (_) {}
}

async function loadNotificationsHub() {
    const container = document.getElementById("notificationsContainer");
    if (!container) return;

    try {
        const res = await notificationsApi.getAll();
        const notifs = res.notifications || [];

        if (notifs.length === 0) {
            container.innerHTML = `<div style="text-align: center; padding: 36px; color: var(--text-muted);">No notifications at this time. All systems optimal.</div>`;
            return;
        }

        container.innerHTML = `
            <div class="date-group-heading">Today's Updates</div>
            ${notifs.map((n, idx) => {
                const isHighlight = idx === 1;
                let cardClass = n.type || "system";
                let icon = "fa-solid fa-server";
                if (cardClass === "warning") icon = "fa-solid fa-triangle-exclamation";
                if (cardClass === "info") icon = "fa-regular fa-bookmark";

                return `
                    <div class="notif-card ${cardClass} ${isHighlight ? 'highlight' : ''}" id="notif_${n.id}">
                        <div class="notif-icon-wrap">
                            <i class="${icon}"></i>
                        </div>
                        <div class="notif-body">
                            <div class="notif-top">
                                <span class="notif-title">${escapeHtml(n.title)}</span>
                                <span class="notif-time">${n.created_at ? formatTimeAgo(n.created_at) : '10 mins ago'}</span>
                            </div>
                            <p class="notif-desc">${escapeHtml(n.message)}</p>
                            <div class="notif-actions">
                                <span class="notif-btn-link" onclick="viewNotifDetails('${escapeHtml(n.title)}')">View details</span>
                                <span class="notif-btn-dismiss" onclick="dismissNotif(${n.id})">Dismiss</span>
                            </div>
                        </div>
                    </div>
                `;
            }).join("")}
        `;
    } catch (_) {}
}

async function handleMarkAllNotifsRead() {
    try {
        await notificationsApi.markAllRead();
        showToast("All alerts marked as read.", "success");
        loadNotificationsCount();
        loadNotificationsHub();
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function dismissNotif(id) {
    try {
        await notificationsApi.markRead(id);
        document.getElementById(`notif_${id}`)?.remove();
        loadNotificationsCount();
        showToast("Notification dismissed", "info");
    } catch (_) {}
}

function viewNotifDetails(title) {
    showToast(`Opening details for: ${title}`, "info");
}

// ========================================================
// 14. VERIFICATION MODAL (HALLMARK HUID & ISI LICENSE)
// ========================================================

function switchVerifyTab(tab) {
    const isHallmark = tab === "hallmark";
    document.getElementById("verifyHallmarkSection").style.display = isHallmark ? "block" : "none";
    document.getElementById("verifyLicenseSection").style.display = isHallmark ? "none" : "block";
    document.getElementById("tabVerifyHallmark").classList.toggle("active", isHallmark);
    document.getElementById("tabVerifyLicense").classList.toggle("active", !isHallmark);
    document.getElementById("verificationResultBox").style.display = "none";
}

async function handleVerifyHuid() {
    const input = document.getElementById("huidInput");
    const resultBox = document.getElementById("verificationResultBox");
    const huid = input?.value.trim().toUpperCase();

    if (!huid || huid.length !== 6) {
        showToast("Hallmark Unique Identification (HUID) must be exactly 6 alphanumeric characters.", "warning");
        return;
    }

    resultBox.style.display = "block";
    resultBox.innerHTML = `<div style="text-align: center; padding: 14px;"><i class="fa-solid fa-spinner fa-spin"></i> Querying National Hallmarking Gateway for HUID ${escapeHtml(huid)}...</div>`;

    try {
        const res = await verificationApi.verifyHallmark(huid);
        const h = res.hallmark || res.details || {};

        resultBox.innerHTML = `
            <div class="card" style="border-left: 4px solid var(--success); background: var(--success-bg);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-weight: 800; color: var(--success-text); font-size: 1.05rem;">
                        <i class="fa-solid fa-circle-check"></i> Hallmark Authenticity Confirmed
                    </span>
                    <span class="badge badge-success">VERIFIED</span>
                </div>
                <div style="font-size: 0.86rem; line-height: 1.6; color: var(--text-primary);">
                    <strong>HUID Stamp:</strong> ${escapeHtml(huid)}<br>
                    <strong>Article Type:</strong> ${escapeHtml(h.article_type || "Gold Jewelry")}<br>
                    <strong>Purity Standard:</strong> ${escapeHtml(h.purity || "22K (916)")}<br>
                    <strong>Assaying & Hallmarking Center:</strong> ${escapeHtml(h.ahc_name || "Certified AHC")}<br>
                    <strong>Jeweler Establishment:</strong> ${escapeHtml(h.jeweler_name || "Registered Jeweler")}
                </div>
            </div>
        `;
        showToast(`HUID ${huid} verified successfully!`, "success");
    } catch (err) {
        resultBox.innerHTML = `
            <div class="card" style="border-left: 4px solid var(--warning); background: var(--warning-bg);">
                <span style="font-weight: 800; color: var(--warning-text); font-size: 0.95rem;">
                    <i class="fa-solid fa-circle-info"></i> Local Prototype Notice
                </span>
                <p style="font-size: 0.82rem; color: var(--text-secondary); margin-top: 6px;">
                    HUID '${escapeHtml(huid)}' was not found in the local BIS prototype registry. Real-time national verification operates on the centralized Manakonline database and BIS Care App.
                </p>
            </div>
        `;
    }
}

async function handleVerifyLicense() {
    const input = document.getElementById("licenseInput");
    const resultBox = document.getElementById("verificationResultBox");
    const licenseNo = input?.value.trim();

    if (!licenseNo) {
        showToast("Please enter a valid BIS License Number (CM/L Number).", "warning");
        return;
    }

    resultBox.style.display = "block";
    resultBox.innerHTML = `<div style="text-align: center; padding: 14px;"><i class="fa-solid fa-spinner fa-spin"></i> Checking BIS License Registry for ${escapeHtml(licenseNo)}...</div>`;

    try {
        const res = await verificationApi.verifyLicense(licenseNo);
        const lic = res.details || {};

        resultBox.innerHTML = `
            <div class="card" style="border-left: 4px solid var(--success); background: var(--success-bg);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-weight: 800; color: var(--success-text); font-size: 1.05rem;">
                        <i class="fa-solid fa-circle-check"></i> BIS License Active & Valid
                    </span>
                    <span class="badge badge-success">${escapeHtml(lic.status || "Active")}</span>
                </div>
                <div style="font-size: 0.86rem; line-height: 1.6; color: var(--text-primary);">
                    <strong>License No:</strong> ${escapeHtml(lic.license_number)}<br>
                    <strong>Certified Product:</strong> ${escapeHtml(lic.product || "Product")}<br>
                    <strong>Conforming Standard:</strong> ${escapeHtml(lic.standard || "Indian Standard")}<br>
                    <strong>Manufacturer Unit:</strong> ${escapeHtml(lic.manufacturer || "Certified Manufacturer")}<br>
                    <strong>Validity Period:</strong> ${escapeHtml(lic.validity_from || "")} to ${escapeHtml(lic.validity_to || "")}
                </div>
            </div>
        `;
        showToast(`License ${licenseNo} verified!`, "success");
    } catch (err) {
        resultBox.innerHTML = `
            <div class="card" style="border-left: 4px solid var(--danger); background: var(--danger-bg);">
                <span style="font-weight: 800; color: var(--danger-text); font-size: 0.95rem;">
                    <i class="fa-solid fa-triangle-exclamation"></i> License Not Found
                </span>
                <p style="font-size: 0.82rem; color: var(--text-secondary); margin-top: 6px;">
                    License '${escapeHtml(licenseNo)}' could not be found in the current prototype database.
                </p>
            </div>
        `;
    }
}

// ========================================================
// 15. MODAL SYSTEM HELPERS
// ========================================================

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add("active");
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove("active");
    }
}

// ========================================================
// 16. TOAST NOTIFICATION SYSTEM
// ========================================================

function showToast(message, type = "info", duration = 4000) {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    let icon = "fa-solid fa-circle-info";
    if (type === "success") icon = "fa-solid fa-circle-check";
    if (type === "error") icon = "fa-solid fa-circle-exclamation";
    if (type === "warning") icon = "fa-solid fa-triangle-exclamation";

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <i class="${icon} toast-icon"></i>
        <div style="flex: 1; line-height: 1.4;">${escapeHtml(message)}</div>
        <i class="fa-solid fa-xmark" style="cursor: pointer; opacity: 0.6;" onclick="this.parentElement.remove()"></i>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.transition = "opacity 0.3s, transform 0.3s";
        toast.style.opacity = "0";
        toast.style.transform = "translateX(100%)";
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ========================================================
// 17. UTILITY & FORMATTING FUNCTIONS
// ========================================================

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatMarkdown(text) {
    if (!text) return "";
    let html = escapeHtml(text);
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    // Headers
    html = html.replace(/^### (.*$)/gim, '<h4 style="color: var(--primary); margin: 10px 0 4px 0;">$1</h4>');
    html = html.replace(/^## (.*$)/gim, '<h3 style="color: var(--primary); margin: 12px 0 6px 0;">$1</h3>');
    // Lists
    html = html.replace(/^\* (.*$)/gim, '<li style="margin-left: 18px;">$1</li>');
    html = html.replace(/^- (.*$)/gim, '<li style="margin-left: 18px;">$1</li>');
    // Paragraphs & breaks
    html = html.replace(/\n\n/g, "<p style='margin-bottom: 8px;'></p>");
    html = html.replace(/\n/g, "<br>");
    return html;
}

function formatTimeAgo(isoString) {
    try {
        const diff = (Date.now() - new Date(isoString).getTime()) / 1000;
        if (diff < 60) return "Just now";
        if (diff < 3600) return `${Math.floor(diff / 60)} mins ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
        return `${Math.floor(diff / 86400)} days ago`;
    } catch (_) {
        return "Recently";
    }
}
