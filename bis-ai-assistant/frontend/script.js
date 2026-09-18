// ==================================================
// BIS SAHAYAK / BIS AI ASSISTANT - CLIENT SCRIPT
// Smart India Hackathon 2026
// ==================================================

const API_BASE = "http://localhost:5000/api";

// Current application state
let currentLanguage = localStorage.getItem("bis_lang") || "en";
let currentTheme = localStorage.getItem("bis_theme") || "light";
let currentHistoryFilter = "all";
let attachedFileContext = null;
let speechRecognition = null;
let isRecognizing = false;

// ==================================================
// AUTHENTICATION & USER MANAGEMENT
// ==================================================

const DEMO_USERS = {
    officer: {
        id: "usr_officer_demo_01",
        name: "Raj Kumar",
        email: "officer@bis.gov.in",
        role: "BIS Quality Officer",
        badge: "BIS Officer (Demo)",
        avatar: "RK",
        token: "demo_token_officer_123"
    },
    manufacturer: {
        id: "usr_mfg_demo_02",
        name: "Sunita Verma",
        email: "sunita@apex-elec.com",
        role: "Electronics Manufacturer",
        badge: "Manufacturer (Demo)",
        avatar: "SV",
        token: "demo_token_mfg_456"
    },
    consumer: {
        id: "usr_consumer_demo_03",
        name: "Amit Sharma",
        email: "amit.sharma@example.com",
        role: "Informed Citizen / Consumer",
        badge: "Consumer (Demo)",
        avatar: "AS",
        token: "demo_token_consumer_789"
    }
};

function getCurrentUser() {
    try {
        const stored = localStorage.getItem("bis_user");
        if (stored) return JSON.parse(stored);
    } catch (_) {}
    return DEMO_USERS.officer;
}

function setCurrentUser(user) {
    localStorage.setItem("bis_user", JSON.stringify(user));
    updateUserUI();
    loadNotifications();
    if (document.getElementById("history")?.classList.contains("active-view")) {
        loadHistory(currentHistoryFilter);
    }
    if (document.getElementById("dashboard")?.classList.contains("active-view")) {
        loadDashboard();
    }
}

function updateUserUI() {
    const user = getCurrentUser();
    const avatarEl = document.getElementById("userAvatar");
    const nameEl = document.getElementById("userName");
    const roleEl = document.getElementById("userRole");
    const menuNameEl = document.getElementById("menuUserName");
    const menuEmailEl = document.getElementById("menuUserEmail");
    const menuRoleEl = document.getElementById("menuUserRole");
    const dashGreetEl = document.querySelector(".dashboard-top-greet h2");

    if (avatarEl) avatarEl.innerText = user.avatar || user.name.slice(0, 2).toUpperCase();
    if (nameEl) nameEl.innerText = user.name;
    if (roleEl) roleEl.innerText = user.role;
    if (menuNameEl) menuNameEl.innerText = user.name;
    if (menuEmailEl) menuEmailEl.innerText = user.email;
    if (menuRoleEl) menuRoleEl.innerText = user.badge || user.role;
    if (dashGreetEl) dashGreetEl.innerText = `Welcome back, ${user.name}`;
}

function toggleUserMenu(event) {
    if (event) event.stopPropagation();
    const menu = document.getElementById("userDropdownMenu");
    if (!menu) return;
    const isShown = menu.style.display === "block";
    closeAllDropdowns();
    menu.style.display = isShown ? "none" : "block";
}

function openLoginModal() {
    const modal = document.getElementById("loginModal");
    if (modal) modal.style.display = "flex";
    closeAllDropdowns();
}

function closeLoginModal(event) {
    if (event && event.target !== event.currentTarget) return;
    const modal = document.getElementById("loginModal");
    if (modal) modal.style.display = "none";
}

async function loginWithDemo(roleKey) {
    const target = DEMO_USERS[roleKey] || DEMO_USERS.officer;
    try {
        const res = await apiRequest("/auth/demo", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ role: roleKey })
        });
        if (res.user) {
            setCurrentUser({ ...res.user, token: res.token || target.token });
        } else {
            setCurrentUser(target);
        }
    } catch (_) {
        setCurrentUser(target);
    }
    closeLoginModal();
    alert(`Signed in successfully as ${target.name} (${target.role})`);
}

async function loginWithCustom(event) {
    if (event) event.preventDefault();
    const name = document.getElementById("loginCustomName")?.value.trim();
    const email = document.getElementById("loginCustomEmail")?.value.trim();
    const role = document.getElementById("loginCustomRole")?.value;

    if (!name || !email) {
        alert("Please provide both name and email.");
        return;
    }

    const initials = name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();
    const customUser = {
        id: `usr_${Date.now()}`,
        name,
        email,
        role,
        badge: role,
        avatar: initials,
        token: `custom_token_${Date.now()}`
    };

    setCurrentUser(customUser);
    closeLoginModal();
    alert(`Welcome, ${name}! Signed in as ${role}.`);
}

function handleGoogleCredentialResponse(response) {
    if (!response || !response.credential) {
        console.error("Google Sign-In failed or was dismissed.");
        return;
    }

    apiRequest("/auth/google", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credential: response.credential })
    }).then(data => {
        if (data.user) {
            setCurrentUser({ ...data.user, token: data.token });
            closeLoginModal();
            alert(`Welcome ${data.user.name}! Signed in via Google.`);
        }
    }).catch(err => {
        console.warn("Backend Google auth returned:", err.message);
        const demoUser = {
            id: `usr_google_${Date.now()}`,
            name: "Verified Google User",
            email: "user@google.com",
            role: "BIS Registered User",
            badge: "Google Verified",
            avatar: "GU",
            token: response.credential.slice(0, 32)
        };
        setCurrentUser(demoUser);
        closeLoginModal();
        alert("Signed in with Google authentication.");
    });
}

function logoutUser() {
    closeAllDropdowns();
    try {
        apiRequest("/auth/logout", { method: "POST" });
    } catch (_) {}
    setCurrentUser(DEMO_USERS.officer);
    alert("Signed out. Switched to default guest session.");
}

function getAuthHeaders() {
    const user = getCurrentUser();
    const headers = {};
    if (user && user.token) {
        headers["Authorization"] = `Bearer ${user.token}`;
    }
    if (user && user.email) {
        headers["X-User-Email"] = user.email;
    }
    return headers;
}

// ==================================================
// GLOBAL HELPERS & API REQUEST
// ==================================================

function showLoading(button, text = "Processing...") {
    if (!button) return;
    button.dataset.originalText = button.innerHTML;
    button.disabled = true;
    button.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${text}`;
}

function restoreButton(button) {
    if (!button) return;
    button.disabled = false;
    if (button.dataset.originalText) {
        button.innerHTML = button.dataset.originalText;
    }
}

async function apiRequest(url, options = {}) {
    const authHeaders = getAuthHeaders();
    const headers = { ...authHeaders, ...(options.headers || {}) };

    const response = await fetch(`${API_BASE}${url}`, {
        ...options,
        headers
    });

    let data = {};
    try {
        data = await response.json();
    } catch {
        data = {};
    }

    if (!response.ok) {
        throw new Error(data.error || data.message || "Server request failed.");
    }

    return data;
}

function escapeHtml(value) {
    const div = document.createElement("div");
    div.innerText = value ?? "";
    return div.innerHTML;
}

function closeAllDropdowns() {
    const notifMenu = document.getElementById("notifDropdown");
    const userMenu = document.getElementById("userDropdownMenu");
    if (notifMenu) notifMenu.style.display = "none";
    if (userMenu) userMenu.style.display = "none";
}

// ==================================================
// THEME SWITCHING (DARK / LIGHT)
// ==================================================

function initTheme() {
    const saved = localStorage.getItem("bis_theme") || "light";
    currentTheme = saved;
    if (saved === "dark") {
        document.body.classList.add("dark-theme");
        const icon = document.getElementById("themeToggleIcon");
        if (icon) icon.className = "fa-solid fa-sun";
    }
}

function toggleTheme() {
    const isDark = document.body.classList.toggle("dark-theme");
    currentTheme = isDark ? "dark" : "light";
    localStorage.setItem("bis_theme", currentTheme);
    const icon = document.getElementById("themeToggleIcon");
    if (icon) {
        icon.className = isDark ? "fa-solid fa-sun" : "fa-solid fa-moon";
    }
}

// ==================================================
// MULTI-LINGUAL SUPPORT (ENGLISH | HINDI)
// ==================================================

const TRANSLATIONS = {
    en: {
        newChat: "New Chat",
        home: "Home",
        aiAssistant: "AI Assistant",
        standardsSearch: "Standards Search",
        bisServices: "BIS Services",
        complianceChecker: "Compliance Checker",
        docIntelligence: "Document Intelligence",
        certVerification: "Certification Verification",
        industryDashboard: "Industry Dashboard",
        history: "History",
        heroTag: "BIS AI Assistant",
        heroTitlePrefix: "India's Intelligent Assistant for",
        heroTitleSpan: "Standards & BIS Services",
        heroDesc: "Find Indian Standards, understand compliance requirements, discover BIS services, and get trusted guidance through AI.",
        askBisAi: "Ask BIS AI",
        exploreStandards: "Explore Standards",
        stat1: "Indian Standards",
        stat2: "One Platform",
        stat3: "Government Inspired",
        aiAskTitle: "Ask anything about",
        aiAskSpan: "Indian Standards",
        aiAskDesc: "Get accurate, reliable and easy-to-understand answers from our AI assistant",
        aiInputPlaceholder: "Ask about an Indian Standard, product certification, BIS license, hallmarking, testing or compliance...",
        searchStandardsTitle: "Find the Right Indian Standard",
        searchStandardsSubtitle: "Search by product, IS number, category or keyword",
        standardsInputPlaceholder: "Search for product, IS number, category, or keyword...",
        consumerHeader: "Verify Before You Buy",
        consumerSubtitle: "Check authenticity of BIS certified products, Hallmarked jewellery & file consumer grievances",
        tabVerifyLicense: "Verify License",
        tabVerifyHallmark: "Verify Hallmark (HUID)",
        tabReportComplaint: "Report Complaint"
    },
    hi: {
        newChat: "नई बातचीत",
        home: "मुख्य पृष्ठ",
        aiAssistant: "बी॰आई॰एस सहायक एआई",
        standardsSearch: "भारतीय मानक खोज",
        bisServices: "बी॰आई॰एस सेवाएँ",
        complianceChecker: "अनुपालन परीक्षक",
        docIntelligence: "दस्तावेज़ विश्लेषण",
        certVerification: "प्रमाणन सत्यापन",
        industryDashboard: "उद्योग डैशबोर्ड",
        history: "गतिविधि इतिहास",
        heroTag: "बी॰आई॰एस एआई सहायक",
        heroTitlePrefix: "भारतीय मानकों और सेवाओं के लिए",
        heroTitleSpan: "भारत का स्मार्ट सहायक",
        heroDesc: "भारतीय मानक खोजें, अनुपालन आवश्यकताएँ समझें, बीआईएस सेवाओं की जानकारी लें और एआई से विश्वसनीय मार्गदर्शन प्राप्त करें।",
        askBisAi: "एआई से पूछें",
        exploreStandards: "मानक खोजें",
        stat1: "भारतीय मानक",
        stat2: "एक मंच",
        stat3: "सरकारी प्रेरणा",
        aiAskTitle: "भारतीय मानकों के बारे में",
        aiAskSpan: "कुछ भी पूछें",
        aiAskDesc: "हमारे एआई सहायक से सटीक, विश्वसनीय और सरल मार्गदर्शन प्राप्त करें",
        aiInputPlaceholder: "भारतीय मानक, आईएसआई मार्क, उत्पाद प्रमाणन, हॉलमार्किंग या अनुपालन के बारे में पूछें...",
        searchStandardsTitle: "उपयुक्त भारतीय मानक खोजें",
        searchStandardsSubtitle: "उत्पाद, मानक संख्या (IS Number), श्रेणी या कीवर्ड द्वारा खोजें",
        standardsInputPlaceholder: "उत्पाद, मानक संख्या या कीवर्ड लिखें...",
        consumerHeader: "खरीदने से पहले जाँचें",
        consumerSubtitle: "बीआईएस प्रमाणित उत्पादों, हॉलमार्क आभूषणों की प्रामाणिकता जाँचें और शिकायत दर्ज करें",
        tabVerifyLicense: "लाइसेंस जाँचें",
        tabVerifyHallmark: "हॉलमार्क जाँचें (HUID)",
        tabReportComplaint: "शिकायत दर्ज करें"
    }
};

function initLanguage() {
    currentLanguage = localStorage.getItem("bis_lang") || "en";
    applyLanguage(currentLanguage);
}

function toggleLanguage() {
    currentLanguage = currentLanguage === "en" ? "hi" : "en";
    localStorage.setItem("bis_lang", currentLanguage);
    applyLanguage(currentLanguage);
}

function applyLanguage(lang) {
    const t = TRANSLATIONS[lang] || TRANSLATIONS.en;
    const langBtnText = document.getElementById("langBtnText");
    if (langBtnText) {
        langBtnText.innerText = lang === "hi" ? "हिंदी | English" : "English | हिंदी";
    }

    // Sidebar Items
    const navItems = document.querySelectorAll(".nav-menu li");
    if (navItems.length >= 9) {
        navItems[0].childNodes[1] && (navItems[0].lastChild.textContent = ` ${t.home}`);
        navItems[1].childNodes[1] && (navItems[1].lastChild.textContent = ` ${t.aiAssistant}`);
        navItems[2].childNodes[1] && (navItems[2].lastChild.textContent = ` ${t.standardsSearch}`);
        navItems[3].childNodes[1] && (navItems[3].lastChild.textContent = ` ${t.bisServices}`);
        navItems[4].childNodes[1] && (navItems[4].lastChild.textContent = ` ${t.complianceChecker}`);
        navItems[5].childNodes[1] && (navItems[5].lastChild.textContent = ` ${t.docIntelligence}`);
        navItems[6].childNodes[1] && (navItems[6].lastChild.textContent = ` ${t.certVerification}`);
        navItems[7].childNodes[1] && (navItems[7].lastChild.textContent = ` ${t.industryDashboard}`);
        navItems[8].childNodes[1] && (navItems[8].lastChild.textContent = ` ${t.history}`);
    }

    // Inputs Placeholders
    const aiInput = document.getElementById("aiQueryInput");
    if (aiInput) aiInput.placeholder = t.aiInputPlaceholder;

    const stdInput = document.getElementById("standardsSearchInput");
    if (stdInput) stdInput.placeholder = t.standardsInputPlaceholder;

    // Consumer Tabs
    const tabLic = document.getElementById("tabBtnLicense");
    if (tabLic) tabLic.innerHTML = `<i class="fa-solid fa-id-card"></i> ${t.tabVerifyLicense}`;
    const tabHmk = document.getElementById("tabBtnHallmark");
    if (tabHmk) tabHmk.innerHTML = `<i class="fa-solid fa-gem"></i> ${t.tabVerifyHallmark}`;
    const tabCmp = document.getElementById("tabBtnComplaint");
    if (tabCmp) tabCmp.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${t.tabReportComplaint}`;
}

// ==================================================
// NOTIFICATIONS SYSTEM
// ==================================================

async function loadNotifications() {
    try {
        const data = await apiRequest("/notifications");
        const list = data.notifications || [];
        const unreadCount = data.unread_count || list.filter(n => !n.is_read).length;

        const badge = document.getElementById("notifBadge");
        if (badge) {
            if (unreadCount > 0) {
                badge.style.display = "inline-block";
                badge.innerText = unreadCount > 9 ? "9+" : unreadCount;
            } else {
                badge.style.display = "none";
            }
        }

        renderNotificationList(list);
    } catch (err) {
        console.warn("Notifications fetch error:", err.message);
    }
}

function renderNotificationList(notifications) {
    const container = document.getElementById("notifList");
    if (!container) return;

    if (!notifications || notifications.length === 0) {
        container.innerHTML = `<div class="notif-empty"><i class="fa-regular fa-bell-slash"></i><p>No notifications yet.</p></div>`;
        return;
    }

    container.innerHTML = notifications.map(item => {
        let iconClass = "fa-solid fa-bell";
        if (item.category === "ai") iconClass = "fa-solid fa-robot";
        else if (item.category === "compliance") iconClass = "fa-solid fa-shield-check";
        else if (item.category === "document") iconClass = "fa-solid fa-file-invoice";
        else if (item.category === "complaint") iconClass = "fa-solid fa-triangle-exclamation";
        else if (item.category === "hallmark") iconClass = "fa-solid fa-gem";

        const timeStr = item.created_at ? item.created_at.slice(0, 16).replace("T", " ") : "";

        return `
            <div class="notif-item ${item.is_read ? '' : 'unread'}" onclick="markNotificationRead('${item.id}')">
                <div class="notif-item-icon">
                    <i class="${iconClass}"></i>
                </div>
                <div class="notif-item-content">
                    <h5>${escapeHtml(item.title)}</h5>
                    <p>${escapeHtml(item.message)}</p>
                    <span class="notif-item-time">${escapeHtml(timeStr)}</span>
                </div>
            </div>
        `;
    }).join("");
}

function toggleNotifications(event) {
    if (event) event.stopPropagation();
    const dropdown = document.getElementById("notifDropdown");
    if (!dropdown) return;
    const isShown = dropdown.style.display === "flex";
    closeAllDropdowns();
    dropdown.style.display = isShown ? "none" : "flex";
    if (!isShown) loadNotifications();
}

async function markAllNotificationsRead() {
    try {
        await apiRequest("/notifications/read-all", { method: "POST" });
        loadNotifications();
    } catch (err) {
        console.error("Mark read error:", err);
    }
}

async function markNotificationRead(id) {
    try {
        await apiRequest(`/notifications/${id}/read`, { method: "POST" });
        loadNotifications();
    } catch (_) {}
}

// ==================================================
// VIEW NAVIGATION & BREADCRUMBS
// ==================================================

const VIEW_METADATA = {
    landing: { title: "Home", subtitle: "Understand Standards, Simplify Compliance" },
    "ai-chat": { title: "AI Assistant", subtitle: "Ask Anything About Indian Standards & Services" },
    "ai-response": { title: "AI Guidance", subtitle: "Recommended Standard & Compliance Guidance" },
    standards: { title: "Standards Search", subtitle: "Find the Right Indian Standard & Requirements" },
    services: { title: "BIS Services", subtitle: "Explore Certification Schemes, Labs & Training" },
    compliance: { title: "Compliance Checker", subtitle: "Automated Product Compliance Assessment" },
    document: { title: "Document Intelligence", subtitle: "Upload & Analyze BIS Documents with AI" },
    consumer: { title: "Certification Verification", subtitle: "Verify Licenses, Hallmarks & Report Complaints" },
    dashboard: { title: "Industry Dashboard", subtitle: "Manage Your Certification & Standards Portfolio" },
    history: { title: "Activity History", subtitle: "User Action Audit Log & SIH 2026 Overview" }
};

function switchView(viewId, element) {
    document.querySelectorAll(".app-view").forEach(view => {
        view.classList.remove("active-view");
    });

    const targetView = document.getElementById(viewId);
    if (targetView) {
        targetView.classList.add("active-view");
    }

    document.querySelectorAll(".nav-menu li").forEach(li => {
        li.classList.remove("active");
    });

    if (element) {
        element.classList.add("active");
    } else {
        const matchingLi = document.querySelector(`.nav-menu li[onclick*="'${viewId}'"]`);
        if (matchingLi) matchingLi.classList.add("active");
    }

    const meta = VIEW_METADATA[viewId] || { title: "BIS Sahayak", subtitle: "Smart India Hackathon 2026" };
    const headTitle = document.getElementById("topHeaderTitle");
    const headSubtitle = document.getElementById("topHeaderSubtitle");
    if (headTitle) headTitle.innerText = meta.title;
    if (headSubtitle) headSubtitle.innerText = meta.subtitle;

    if (window.location.hash !== `#${viewId}`) {
        try {
            history.replaceState(null, "", `#${viewId}`);
        } catch (_) {}
    }

    if (viewId === "dashboard") loadDashboard();
    if (viewId === "history") loadHistory(currentHistoryFilter);
    if (viewId === "standards" && !window.hasLoadedInitialStandards) {
        window.hasLoadedInitialStandards = true;
        applyStandardsFilters();
    }
}

// ==================================================
// AI ASSISTANT (LLM + VOICE + ATTACHMENT)
// ==================================================

function formatAiMarkdown(text) {
    if (!text) return "";
    let formatted = escapeHtml(text);

    formatted = formatted.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    formatted = formatted.replace(/^### (.*$)/gim, '<h4 style="color: var(--primary); margin: 12px 0 6px 0;">$1</h4>');
    formatted = formatted.replace(/^## (.*$)/gim, '<h3 style="color: var(--primary); margin: 14px 0 8px 0;">$1</h3>');
    formatted = formatted.replace(/^\* (.*$)/gim, '<li style="margin-left: 18px;">$1</li>');
    formatted = formatted.replace(/^- (.*$)/gim, '<li style="margin-left: 18px;">$1</li>');
    formatted = formatted.replace(/\n\n/g, "<p style='margin-bottom: 8px;'></p>");
    formatted = formatted.replace(/\n/g, "<br>");

    return formatted;
}

function toggleVoiceInput(event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
        alert("Speech Recognition is not supported by your browser. Please use Chrome, Edge, or Safari.");
        return;
    }

    const micBtn = document.getElementById("aiMicBtn");
    const micIcon = document.getElementById("aiMicIcon");

    if (isRecognizing && speechRecognition) {
        speechRecognition.stop();
        isRecognizing = false;
        if (micBtn) micBtn.classList.remove("listening");
        if (micIcon) micIcon.className = "fa-solid fa-microphone";
        return;
    }

    try {
        speechRecognition = new SpeechRec();
        speechRecognition.lang = currentLanguage === "hi" ? "hi-IN" : "en-IN";
        speechRecognition.continuous = false;
        speechRecognition.interimResults = false;

        speechRecognition.onstart = () => {
            isRecognizing = true;
            if (micBtn) micBtn.classList.add("listening");
            if (micIcon) micIcon.className = "fa-solid fa-microphone-lines";
        };

        speechRecognition.onresult = (e) => {
            const transcript = e.results[0][0].transcript;
            const input = document.getElementById("aiQueryInput");
            if (input && transcript) {
                input.value = transcript;
                triggerAiChat();
            }
        };

        speechRecognition.onerror = (e) => {
            console.warn("Speech recognition error:", e.error);
            isRecognizing = false;
            if (micBtn) micBtn.classList.remove("listening");
            if (micIcon) micIcon.className = "fa-solid fa-microphone";
        };

        speechRecognition.onend = () => {
            isRecognizing = false;
            if (micBtn) micBtn.classList.remove("listening");
            if (micIcon) micIcon.className = "fa-solid fa-microphone";
        };

        speechRecognition.start();
    } catch (err) {
        console.error("Speech rec init failed:", err);
    }
}

function triggerAiAttachment(event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    const fileInput = document.getElementById("aiAttachmentInput");
    if (fileInput) fileInput.click();
}

function handleAiAttachmentSelected(event) {
    const input = event.target;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];

    const chip = document.getElementById("aiAttachmentChip");
    const chipName = document.getElementById("aiAttachmentName");
    if (chip && chipName) {
        chipName.innerText = `${file.name} (${(file.size / 1024).toFixed(0)} KB)`;
        chip.style.display = "inline-flex";
    }

    const reader = new FileReader();
    reader.onload = function(e) {
        attachedFileContext = {
            filename: file.name,
            content: e.target.result.slice(0, 15000)
        };
    };
    reader.readAsText(file);
}

function clearAiAttachment() {
    attachedFileContext = null;
    const chip = document.getElementById("aiAttachmentChip");
    if (chip) chip.style.display = "none";
    const fileInput = document.getElementById("aiAttachmentInput");
    if (fileInput) fileInput.value = "";
}

async function triggerAiChat(event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    const input = document.getElementById("aiQueryInput");
    const query = input?.value.trim();

    if (!query) {
        alert("Please enter a question or topic about BIS standards.");
        return;
    }

    const submitBtn = document.getElementById("aiSubmitBtn");
    showLoading(submitBtn, "");

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
        let docContext = "";
        if (attachedFileContext) {
            docContext = `Attachment File: ${attachedFileContext.filename}\n${attachedFileContext.content}`;
        } else if (window.latestUploadedDocument && window.latestUploadedDocument.extracted_text) {
            docContext = `Uploaded Document: ${window.latestUploadedDocument.filename}\n${window.latestUploadedDocument.extracted_text.slice(0, 5000)}`;
        }

        const data = await apiRequest("/ai/query", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                query,
                document_context: docContext
            })
        });

        renderInlineAiResponse(data);
        renderAiResponse(data);
        loadNotifications();

    } catch (error) {
        console.error("AI Assistant query error:", error);
        alert(error.message || "AI request failed. Please check backend connection.");
        if (inlineResults) inlineResults.style.display = "none";
    } finally {
        restoreButton(submitBtn);
        if (inlineLoading) inlineLoading.style.display = "none";
    }
}

function quickQuery(queryText) {
    const input = document.getElementById("aiQueryInput");
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
    const llmBody = document.getElementById("aiLlmBodyText");
    const modelBadge = document.getElementById("aiModelName");

    if (queryEcho) queryEcho.innerText = data.query || "";
    if (llmBody) llmBody.innerHTML = formatAiMarkdown(data.answer || "No response text received.");
    if (modelBadge && data.model_used) {
        modelBadge.innerText = data.model_used.split("/").pop();
    }

    const numEl = document.getElementById("aiStandardNumber");
    const titleEl = document.getElementById("aiStandardTitle");
    const descEl = document.getElementById("aiStandardDesc");
    const confBadge = document.getElementById("aiConfidenceBadge");
    const certEl = document.getElementById("aiMetricCert");
    const catEl = document.getElementById("aiMetricCat");
    const statusEl = document.getElementById("aiMetricStatus");
    const srcEl = document.getElementById("aiMetricSource");
    const recCard = document.getElementById("aiRecommendedStandardCard");

    if (!data.recommended_standard) {
        if (recCard) recCard.style.display = "none";
        return;
    }

    if (recCard) recCard.style.display = "block";
    const std = data.recommended_standard;
    if (numEl) numEl.innerText = std.is_number;
    if (titleEl) titleEl.innerText = std.title;
    if (descEl) descEl.innerText = std.description || "";
    if (confBadge) confBadge.innerHTML = `<i class="fa-solid fa-gauge-high"></i> Confidence: ${data.confidence_score}`;
    if (certEl) certEl.innerText = std.certification || "Product Certification";
    if (catEl) catEl.innerText = std.category || "General";
    if (statusEl) statusEl.innerText = std.status || "Active";
    if (srcEl) srcEl.innerText = data.source || "BIS Knowledge Base";

    inlineResults.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function clearAiChatResult() {
    const inlineResults = document.getElementById("aiChatResults");
    if (inlineResults) inlineResults.style.display = "none";
    clearAiAttachment();
    const input = document.getElementById("aiQueryInput");
    if (input) {
        input.value = "";
        input.focus();
    }
}

function renderAiResponse(data) {
    const queryBar = document.querySelector(".query-echo-bar");
    const title = document.querySelector(".answer-card-box h2");
    const subtitle = document.querySelector(".std-subtitle");
    const confidence = document.querySelector(".confidence-badge");
    const description = document.querySelector(".std-desc-text");

    if (queryBar) queryBar.innerText = data.query || "";

    if (!data.recommended_standard) {
        if (title) title.innerText = "No matching standard found";
        if (subtitle) subtitle.innerText = "Try providing more product details or keyword specifications.";
        if (description) description.innerText = data.answer || "";
        return;
    }

    const standard = data.recommended_standard;
    if (title) title.innerText = standard.is_number;
    if (subtitle) subtitle.innerText = standard.title;
    if (confidence) confidence.innerHTML = `<i class="fa-solid fa-gauge-high"></i> Confidence: ${data.confidence_score}`;
    if (description) description.innerText = data.answer || standard.description || "";

    const metrics = document.querySelectorAll(".sub-metrics-row strong");
    if (metrics.length >= 4) {
        metrics[0].innerText = standard.certification || "Guidance";
        metrics[1].innerText = standard.category || "General";
        metrics[2].innerText = standard.status || "Active";
        metrics[3].innerText = data.source || "BIS Knowledge Base";
    }
}

// ==================================================
// STANDARDS SEARCH & FILTERING
// ==================================================

async function applyStandardsFilters() {
    const container = document.getElementById("standardsListContainer");
    const countBadge = document.getElementById("standardsCountBadge");
    const query = document.getElementById("standardsSearchInput")?.value.trim() || "";

    const category = document.getElementById("filterCategory")?.value || "";
    const industry = document.getElementById("filterIndustry")?.value || "";
    const year = document.getElementById("filterYear")?.value || "";
    const status = document.getElementById("filterStatus")?.value || "";
    const type = document.getElementById("filterType")?.value || "";
    const sort = document.getElementById("standardsSort")?.value || "relevance";

    if (container) {
        container.innerHTML = `
            <div class="loading-state">
                <i class="fa-solid fa-spinner fa-spin"></i>
                <span>Searching BIS Indian Standards...</span>
            </div>
        `;
    }

    try {
        const params = new URLSearchParams();
        if (query) params.set("q", query);
        if (category) params.set("category", category);
        if (industry) params.set("industry", industry);
        if (year) params.set("year", year);
        if (status) params.set("status", status);
        if (type) params.set("type", type);
        if (sort) params.set("sort", sort);

        const data = await apiRequest(`/standards?${params.toString()}`);
        renderStandards(data.standards || []);

        if (countBadge) {
            countBadge.innerHTML = `Results <b>(${data.count || 0} standards)</b>`;
        }
    } catch (err) {
        console.error("Standards fetch error:", err);
        if (container) {
            container.innerHTML = `
                <div class="error-state">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    ${escapeHtml(err.message)}
                </div>
            `;
        }
    }
}

function searchStandards(keyword = "") {
    const input = document.getElementById("standardsSearchInput");
    if (input) input.value = keyword;
    applyStandardsFilters();
}

function renderStandards(standards) {
    const container = document.getElementById("standardsListContainer");
    if (!container) return;

    if (!standards || standards.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="padding: 40px; text-align: center;">
                <i class="fa-solid fa-magnifying-glass" style="font-size: 2rem; color: var(--text-muted); margin-bottom: 12px;"></i>
                <h3 style="font-size: 1.1rem; color: var(--text-main);">No Indian Standards Found</h3>
                <p style="color: var(--text-muted); font-size: 0.85rem;">Try adjusting your query or resetting dropdown filters.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = standards.map(std => {
        return `
            <div class="standard-row-card" onclick='openStandard(${JSON.stringify(std)})'>
                <div class="std-info-left">
                    <h4>${escapeHtml(std.is_number)}</h4>
                    <p>${escapeHtml(std.title)}</p>
                    <div class="tags-row">
                        <span class="tag electrical">${escapeHtml(std.category || 'General')}</span>
                        <span class="tag active">${escapeHtml(std.status || 'Active')}</span>
                        <span class="tag mandatory">${escapeHtml(std.certification || 'Product Certification')}</span>
                        <span class="tag" style="background: #e2e8f0; color: #475569;">${escapeHtml(String(std.year || ''))}</span>
                    </div>
                </div>
                <button type="button" class="text-link-btn" onclick="event.stopPropagation(); openStandard(${JSON.stringify(std)})">
                    View Details
                    <i class="fa-solid fa-arrow-right"></i>
                </button>
            </div>
        `;
    }).join("");
}

function openStandard(standard) {
    const input = document.getElementById("aiQueryInput");
    if (input) input.value = `Explain ${standard.is_number} (${standard.title})`;

    renderAiResponse({
        query: `Details for ${standard.is_number}`,
        confidence_score: "100%",
        source: "BIS Knowledge Base",
        recommended_standard: standard,
        answer: `${standard.description}\n\nApplicable Sector: ${standard.category || 'General'} | Status: ${standard.status || 'Active'}`
    });

    switchView("ai-response");
}

// ==================================================
// BIS SERVICES (MODALS & PORTAL LINKS)
// ==================================================

const SERVICES_DATA = {
    product_certification: {
        title: "Product Certification (ISI Mark Scheme-I)",
        subtitle: "Conformity Assessment Scheme under BIS Act 2016",
        icon: "fa-solid fa-certificate",
        overview: "The BIS Product Certification Scheme (Scheme-I) grants manufacturers licenses to use the prestigious ISI Mark, providing third-party assurance of product quality, safety and reliability.",
        features: [
            "Covers over 900 mandatory products under Quality Control Orders (QCOs)",
            "Factory audit and independent lab testing verification",
            "Nationwide consumer trust and preference in government tenders",
            "Surveillance inspections to ensure sustained compliance"
        ],
        workflow: [
            "Submit online application on Manakonline with factory and test equipment details",
            "Preliminary inspection by BIS quality officers at manufacturing unit",
            "Independent sample testing at BIS or recognized referral laboratories",
            "Grant of license (CM/L number) upon satisfactory compliance verification"
        ],
        docs: [
            "Proof of factory ownership / registered premises",
            "List of manufacturing machinery and in-house testing equipment",
            "Calibration certificates of testing instruments",
            "Manufacturing process flowchart and quality manual"
        ],
        link: "https://www.manakonline.in"
    },
    hallmarking: {
        title: "Hallmarking Scheme (Gold & Silver Jewellery)",
        subtitle: "HUID-Based Purity Assurance for Precious Metals",
        icon: "fa-solid fa-gem",
        overview: "Mandatory hallmarking of gold jewellery ensures accurate purity determination through 6-digit alphanumeric Hallmark Unique Identification (HUID) laser etched onto every individual jewellery article.",
        features: [
            "Mandatory purity standards: 14K (585), 18K (750), 20K (833), 22K (916), 23K (958), 24K (995)",
            "Every piece tracked via centralized BIS database",
            "Protection against under-caratage and fraudulent trade",
            "Zero cost registration for small jewelers in designated districts"
        ],
        workflow: [
            "Jeweler registers on Manakonline Hallmarking portal",
            "Jewellery submitted to BIS recognized Assaying & Hallmarking Centre (AHC)",
            "XRF assaying and fire assay chemical testing for purity validation",
            "HUID laser engraving and uploading to national registry"
        ],
        docs: [
            "GST Registration Certificate",
            "Proof of jeweler outlet / establishment address",
            "Identity proof of proprietor / partners / directors",
            "Declaration of turnover"
        ],
        link: "https://www.services.bis.gov.in"
    },
    crs: {
        title: "Compulsory Registration Scheme (CRS)",
        subtitle: "IT & Electronic Products Safety Certification",
        icon: "fa-solid fa-microchip",
        overview: "Under Scheme-II of BIS (Conformity Assessment) Regulations, CRS requires manufacturers of specified electronic and IT goods to register their products prior to marketing in India.",
        features: [
            "Covers 80+ electronic categories: laptops, mobile phones, LED lights, power banks, adapters",
            "Self-declaration of conformity based on test reports from BIS recognized labs",
            "Streamlined digital application process on CRS portal",
            "Valid for 2 years with convenient online renewal"
        ],
        workflow: [
            "Product testing in a BIS-recognized testing laboratory in India",
            "Lab uploads test report directly to BIS CRS portal",
            "Manufacturer submits online application with test report reference",
            "Grant of CRS registration number (R-XXXXXXXX) and standard mark authorization"
        ],
        docs: [
            "Valid test report from accredited BIS laboratory (less than 90 days old)",
            "Brand authorization / trademark registration document",
            "Affidavit and undertaking for Indian representative (for foreign manufacturers)",
            "Technical specification sheet and circuit schematic"
        ],
        link: "https://www.crsbis.in"
    },
    fmcs: {
        title: "Foreign Manufacturers Certification Scheme (FMCS)",
        subtitle: "ISI Mark Certification for Overseas Manufacturing Units",
        icon: "fa-solid fa-earth-asia",
        overview: "FMCS enables overseas manufacturing units to obtain BIS license and apply the ISI mark on goods manufactured abroad and exported to India.",
        features: [
            "Ensures foreign products comply with Indian quality standards",
            "Authorized Indian Representative (AIR) liaison mechanism",
            "Pre-certification physical factory audit by BIS technical officers",
            "Customs clearance facilitation across Indian ports"
        ],
        workflow: [
            "Nomination of Authorized Indian Representative (AIR)",
            "Application submission along with factory documentation and inspection fees",
            "On-site audit of overseas plant by BIS quality delegation",
            "Independent testing of drawn samples in Indian laboratories"
        ],
        docs: [
            "Manufacturing license issued by native country regulator",
            "Factory layout, machinery list, and QC testing facilities",
            "Authorized Indian Representative agreement and proof of Indian presence",
            "Test reports from internationally accredited laboratories"
        ],
        link: "https://www.services.bis.gov.in"
    },
    laboratory: {
        title: "Laboratory Recognition & Testing Services (LRS)",
        subtitle: "National Network of Central, Regional & Recognized Labs",
        icon: "fa-solid fa-flask-vial",
        overview: "BIS operates eight state-of-the-art branch laboratories and recognizes numerous external commercial and government labs to test products against relevant Indian Standards.",
        features: [
            "Testing across chemical, electrical, mechanical, civil and microbiological disciplines",
            "Strict adherence to ISO/IEC 17025 accreditation standards",
            "Laboratory Information Management System (LIMS) integration",
            "Support for dispute testing and enforcement sample evaluation"
        ],
        workflow: [
            "Lab applies on LIMS portal with scope of testing and accreditation details",
            "Technical assessment by BIS auditing team",
            "Inter-laboratory proficiency testing and comparison round",
            "Grant of recognition with published scope of Indian Standards"
        ],
        docs: [
            "NABL Accreditation Certificate (ISO/IEC 17025)",
            "Equipment calibration logs traceable to national metrology standards",
            "List of qualified technical staff and signatories",
            "Quality manual and standard operating procedures (SOPs)"
        ],
        link: "https://www.services.bis.gov.in"
    },
    training: {
        title: "National Institute of Training for Standardization (NITS)",
        subtitle: "Capacity Building for Industry, Regulators & Auditors",
        icon: "fa-solid fa-graduation-cap",
        overview: "NITS is the apex training wing of BIS, offering structured certification courses and capacity building programs in standardisation, quality management, and testing.",
        features: [
            "Lead Auditor and Internal Auditor courses (ISO 9001, 14001, 45001, 22000)",
            "Specialized training on specific Indian Standards and testing techniques",
            "International training programs for standardisation bodies of developing nations",
            "Hybrid online and classroom executive development programs"
        ],
        workflow: [
            "Browse upcoming calendar on NITS portal",
            "Select course, participant designation, and session mode",
            "Complete online registration and payment",
            "Attend interactive sessions and receive verifiable BIS certificate"
        ],
        docs: [
            "Organization sponsorship letter (for industry candidates)",
            "Academic / professional qualification credentials",
            "Passport / Government ID for international attendees"
        ],
        link: "https://www.services.bis.gov.in"
    }
};

async function openServiceModal(serviceKey) {
    const modal = document.getElementById("serviceDetailsModal");
    if (!modal) return;

    let svc = SERVICES_DATA[serviceKey];

    try {
        const res = await apiRequest("/services");
        if (res.services && res.services[serviceKey]) {
            svc = { ...svc, ...res.services[serviceKey] };
        }
    } catch (_) {}

    if (!svc) return;

    const iconEl = document.getElementById("svcModalIcon");
    const titleEl = document.getElementById("svcModalTitle");
    const subtitleEl = document.getElementById("svcModalSubtitle");
    const overviewEl = document.getElementById("svcModalOverview");
    const featuresEl = document.getElementById("svcModalFeatures");
    const workflowEl = document.getElementById("svcModalWorkflow");
    const docsEl = document.getElementById("svcModalDocs");
    const linkEl = document.getElementById("svcModalPortalLink");

    if (iconEl) iconEl.className = svc.icon || "fa-solid fa-certificate";
    if (titleEl) titleEl.innerText = svc.title;
    if (subtitleEl) subtitleEl.innerText = svc.subtitle;
    if (overviewEl) overviewEl.innerText = svc.overview;

    if (featuresEl) {
        featuresEl.innerHTML = (svc.features || []).map(f => `<li>${escapeHtml(f)}</li>`).join("");
    }
    if (workflowEl) {
        workflowEl.innerHTML = (svc.workflow || []).map(w => `<li>${escapeHtml(w)}</li>`).join("");
    }
    if (docsEl) {
        docsEl.innerHTML = (svc.docs || []).map(d => `<li>${escapeHtml(d)}</li>`).join("");
    }
    if (linkEl && svc.link) {
        linkEl.href = svc.link;
    }

    modal.style.display = "flex";
}

function closeServiceModal() {
    const modal = document.getElementById("serviceDetailsModal");
    if (modal) modal.style.display = "none";
}

// ==================================================
// CONSUMER VERIFICATION (LICENSE, HALLMARK, COMPLAINTS)
// ==================================================

function switchConsumerTab(tabName) {
    const tabs = ["license", "hallmark", "complaint"];
    tabs.forEach(t => {
        const btn = document.getElementById(`tabBtn${t.charAt(0).toUpperCase() + t.slice(1)}`);
        const panel = document.getElementById(`verTab${t.charAt(0).toUpperCase() + t.slice(1)}`);
        if (btn) btn.classList.toggle("active", t === tabName);
        if (panel) panel.style.display = t === tabName ? "block" : "none";
    });
}

function setLicenseSample(sampleVal) {
    const input = document.getElementById("licenseInput");
    if (input) {
        input.value = sampleVal;
        verifyLicenseNumber(sampleVal);
    }
}

function setHallmarkSample(sampleHuid) {
    const input = document.getElementById("hallmarkInput");
    if (input) {
        input.value = sampleHuid;
        verifyHallmark();
    }
}

async function verifyLicenseNumber(licenseNo) {
    if (!licenseNo) {
        alert("Please enter a BIS license or registration number.");
        return;
    }

    const btn = document.getElementById("licenseVerifyBtn");
    showLoading(btn, "Verifying...");

    const resultBox = document.getElementById("licenseResultBox");

    try {
        const data = await apiRequest(`/verify/${encodeURIComponent(licenseNo)}`);
        renderVerification(data.details);
        loadNotifications();
    } catch (error) {
        if (resultBox) {
            resultBox.className = "verified-success-box verification-failed";
            resultBox.style.display = "flex";
            resultBox.innerHTML = `
                <i class="fa-solid fa-circle-xmark" style="color: #dc2626;"></i>
                <div>
                    <h4 style="color: #dc2626;">License Not Verified</h4>
                    <p style="color: var(--text-muted);">${escapeHtml(error.message || 'No active record found for this license number.')}</p>
                </div>
            `;
        }
    } finally {
        restoreButton(btn);
    }
}

function renderVerification(details) {
    const resultBox = document.getElementById("licenseResultBox");
    if (!resultBox || !details) return;

    resultBox.className = "verified-success-box";
    resultBox.style.display = "flex";
    resultBox.innerHTML = `
        <i class="fa-solid fa-circle-check"></i>
        <div>
            <h4>Verified</h4>
            <p>This BIS license is active in the national database.</p>
            <div class="ver-details-grid">
                <span>License Number: <b>${escapeHtml(details.license_number)}</b></span>
                <span>Product: <b>${escapeHtml(details.product)}</b></span>
                <span>Manufacturer: <b>${escapeHtml(details.manufacturer)}</b></span>
                <span>Validity: <b>${escapeHtml(details.validity_from)} – ${escapeHtml(details.validity_to)}</b></span>
                <span>Applicable Standard: <b>${escapeHtml(details.standard)}</b></span>
                <span>Status: <b style="color: #059669;">${escapeHtml(details.status || 'Active')}</b></span>
            </div>
        </div>
    `;
}

async function verifyHallmark() {
    const input = document.getElementById("hallmarkInput");
    const huid = input?.value.trim().toUpperCase();

    if (!huid) {
        alert("Please enter a 6-character Hallmark Unique Identification (HUID).");
        return;
    }

    if (huid.length !== 6) {
        alert("A valid HUID must be exactly 6 alphanumeric characters (e.g. AB1234, MN5678).");
        return;
    }

    const btn = document.getElementById("hallmarkVerifyBtn");
    showLoading(btn, "Verifying HUID...");

    const resultBox = document.getElementById("hallmarkResultBox");

    try {
        const data = await apiRequest(`/verify/hallmark/${encodeURIComponent(huid)}`);
        const item = data.hallmark;

        if (resultBox) {
            resultBox.style.display = "block";
            resultBox.innerHTML = `
                <div class="hallmark-result-card">
                    <div class="hallmark-seal-badge">
                        <i class="fa-solid fa-award"></i>
                    </div>
                    <div class="hallmark-details-wrap">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <h4>Authentic Hallmarked Jewellery</h4>
                            <span class="badge-tag success">Verified HUID</span>
                        </div>
                        <p style="color: var(--text-muted); font-size: 0.85rem;">Registered under BIS Hallmarking Scheme</p>
                        <div class="hallmark-grid">
                            <span>HUID: <b>${escapeHtml(item.huid)}</b></span>
                            <span>Metal & Purity: <b>${escapeHtml(item.metal_purity || item.purity)}</b></span>
                            <span>Article Type: <b>${escapeHtml(item.article_type || 'Jewellery')}</b></span>
                            <span>Jeweler: <b>${escapeHtml(item.jeweler_name)}</b></span>
                            <span>Assaying Center: <b>${escapeHtml(item.center_name)}</b></span>
                            <span>Hallmarking Date: <b>${escapeHtml(item.hallmarking_date)}</b></span>
                        </div>
                    </div>
                </div>
            `;
        }

        loadNotifications();
    } catch (err) {
        if (resultBox) {
            resultBox.style.display = "block";
            resultBox.innerHTML = `
                <div class="hallmark-result-card" style="border-color: #f87171; background: #fff5f5;">
                    <div class="hallmark-seal-badge" style="background: #dc2626;">
                        <i class="fa-solid fa-triangle-exclamation"></i>
                    </div>
                    <div class="hallmark-details-wrap">
                        <h4 style="color: #dc2626;">HUID Verification Failed</h4>
                        <p style="color: var(--text-muted); font-size: 0.88rem;">${escapeHtml(err.message || 'HUID not found in national registry.')}</p>
                    </div>
                </div>
            `;
        }
    } finally {
        restoreButton(btn);
    }
}

async function submitComplaint(event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    const name = document.getElementById("cmpName")?.value.trim();
    const email = document.getElementById("cmpEmail")?.value.trim();
    const phone = document.getElementById("cmpPhone")?.value.trim();
    const category = document.getElementById("cmpCategory")?.value;
    const reference = document.getElementById("cmpReference")?.value.trim();
    const subject = document.getElementById("cmpSubject")?.value.trim();
    const description = document.getElementById("cmpDescription")?.value.trim();

    if (!name || !email || !phone || !category || !subject || !description) {
        alert("Please complete all required fields marked with *.");
        return;
    }

    const submitBtn = document.getElementById("cmpSubmitBtn");
    showLoading(submitBtn, "Submitting to BIS...");

    const resultBox = document.getElementById("complaintResultBox");

    try {
        const payload = {
            complainant_name: name,
            complainant_email: email,
            complainant_phone: phone,
            category,
            reference_number: reference,
            subject,
            description
        };

        const res = await apiRequest("/complaints", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (resultBox) {
            resultBox.style.display = "block";
            resultBox.innerHTML = `
                <div class="complaint-success-box">
                    <i class="fa-solid fa-circle-check"></i>
                    <div>
                        <h4 style="color: #059669; font-size: 1.05rem;">Grievance Successfully Registered with BIS</h4>
                        <p style="color: #065f46; font-size: 0.85rem; margin-top: 2px;">Your complaint has been logged in the central BIS Quality Vigilance system.</p>
                        <div class="tracking-pill">${escapeHtml(res.tracking_id || 'BIS-CMP-2026-REGISTERED')}</div>
                        <p style="font-size: 0.82rem; color: #065f46; margin-top: 4px;">
                            A confirmation email and SMS have been dispatched to <b>${escapeHtml(email)}</b>. You will receive progress notifications regarding inspection and action taken.
                        </p>
                    </div>
                </div>
            `;
            resultBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }

        document.getElementById("complaintForm")?.reset();
        loadNotifications();

    } catch (err) {
        console.error("Complaint error:", err);
        alert(err.message || "Failed to submit grievance. Please try again.");
    } finally {
        restoreButton(submitBtn);
    }
}

// ==================================================
// ACTIVITY & AUDIT HISTORY
// ==================================================

function filterHistory(filterType) {
    currentHistoryFilter = filterType;
    document.querySelectorAll(".history-filter-chip").forEach(chip => {
        chip.classList.toggle("active", chip.dataset.filter === filterType);
    });
    loadHistory(filterType);
}

async function loadHistory(filter = "all") {
    const container = document.getElementById("historyTimelineContainer");
    if (!container) return;

    container.innerHTML = `
        <div class="loading-state">
            <i class="fa-solid fa-spinner fa-spin"></i>
            <span>Loading activity history...</span>
        </div>
    `;

    try {
        const queryParam = filter && filter !== "all" ? `?filter=${encodeURIComponent(filter)}` : "";
        const data = await apiRequest(`/history${queryParam}`);
        const items = data.history || [];

        renderHistoryTimeline(items);
    } catch (err) {
        console.error("History fetch error:", err);
        container.innerHTML = `
            <div class="error-state">
                <i class="fa-solid fa-triangle-exclamation"></i>
                <span>${escapeHtml(err.message || 'Failed to load activity history.')}</span>
            </div>
        `;
    }
}

function renderHistoryTimeline(items) {
    const container = document.getElementById("historyTimelineContainer");
    if (!container) return;

    if (!items || items.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="padding: 40px; text-align: center; background: var(--white); border-radius: 12px; border: 1px solid var(--border);">
                <i class="fa-solid fa-clock-rotate-left" style="font-size: 2rem; color: var(--text-muted); margin-bottom: 12px;"></i>
                <h3 style="font-size: 1.1rem; color: var(--text-main);">No Activity Recorded</h3>
                <p style="color: var(--text-muted); font-size: 0.85rem;">Your queries, document analyses, hallmark checks, and complaints will appear here.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = items.map(item => {
        let badgeClass = "badge-ai";
        let iconClass = "fa-solid fa-robot";
        let typeName = "AI Query";

        if (item.action_type === "standard_search") {
            badgeClass = "badge-std";
            iconClass = "fa-solid fa-magnifying-glass";
            typeName = "Standards Search";
        } else if (item.action_type === "document_upload") {
            badgeClass = "badge-doc";
            iconClass = "fa-solid fa-file-arrow-up";
            typeName = "Document Upload";
        } else if (item.action_type === "compliance_check") {
            badgeClass = "badge-comp";
            iconClass = "fa-solid fa-list-check";
            typeName = "Compliance Check";
        } else if (item.action_type === "hallmark_verification") {
            badgeClass = "badge-hallmark";
            iconClass = "fa-solid fa-gem";
            typeName = "Hallmark Check";
        } else if (item.action_type === "complaint") {
            badgeClass = "badge-complaint";
            iconClass = "fa-solid fa-triangle-exclamation";
            typeName = "Complaint";
        }

        const timeStr = item.created_at ? item.created_at.slice(0, 16).replace("T", " ") : "";

        return `
            <div class="history-timeline-item">
                <div class="history-icon-badge ${badgeClass}">
                    <i class="${iconClass}"></i>
                </div>
                <div class="history-item-body">
                    <div class="history-item-top">
                        <span class="history-item-title">${escapeHtml(item.action_title || item.query || 'Activity')}</span>
                        <span class="history-item-time">${escapeHtml(timeStr)}</span>
                    </div>
                    <p class="history-item-desc">${escapeHtml(item.action_details || item.response_summary || '')}</p>
                    <div class="history-item-tags">
                        <span class="badge-tag" style="background: #f1f5f9; color: #475569;">${typeName}</span>
                        ${item.status ? `<span class="badge-tag success">${escapeHtml(item.status)}</span>` : ''}
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

async function clearUserHistory() {
    if (!confirm("Are you sure you want to clear your activity history?")) return;

    try {
        await apiRequest("/history", { method: "DELETE" });
        loadHistory(currentHistoryFilter);
    } catch (err) {
        alert(err.message || "Failed to clear history.");
    }
}

// ==================================================
// DOCUMENT UPLOAD & INTELLIGENCE
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

    if (idleState && loadingState) {
        idleState.style.display = "none";
        loadingState.style.display = "block";
        if (loadingTitle) loadingTitle.innerText = `Analyzing ${file.name}...`;
        if (loadingSubtitle) loadingSubtitle.innerText = "Extracting text, requirements & computing compliance";
    }

    if (analyzeBtn) showLoading(analyzeBtn, "Analyzing...");

    try {
        const formData = new FormData();
        formData.append("file", file);

        const data = await apiRequest("/documents/upload", {
            method: "POST",
            body: formData
        });

        if (!data.success) {
            alert(data.error || "Document processing failed.");
            return;
        }

        const doc = data.document;
        window.latestUploadedDocument = doc;

        if (currentTag) currentTag.innerText = doc.filename;
        if (currentIcon) {
            currentIcon.className = doc.file_type === "pdf" ? "fa-regular fa-file-pdf" : "fa-regular fa-file-word";
        }

        renderDocumentAnalysis(doc);
        loadNotifications();

    } catch (error) {
        console.error("Document upload error:", error);
        alert("Document upload failed.\n\n" + error.message);
    } finally {
        if (idleState && loadingState) {
            idleState.style.display = "block";
            loadingState.style.display = "none";
        }
        if (analyzeBtn) restoreButton(analyzeBtn);
    }
}

function renderDocumentAnalysis(doc) {
    const resultsContainer = document.getElementById("documentAnalysisResults");
    if (!resultsContainer) return;

    resultsContainer.style.display = "block";

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

    const tbody = document.getElementById("docRequirementsTbody");
    const reqBadge = document.getElementById("docReqCountBadge");
    const requirements = doc.requirements || [];

    if (reqBadge) reqBadge.innerText = `${requirements.length} Requirements`;

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

    const charCountLabel = document.getElementById("docCharCountLabel");
    const textPre = document.getElementById("docExtractedTextPre");

    if (charCountLabel) {
        const count = doc.characters_extracted || (doc.extracted_text ? doc.extracted_text.length : 0);
        charCountLabel.innerText = `${count.toLocaleString()} characters extracted`;
    }

    if (textPre) {
        textPre.innerText = doc.extracted_text || doc.preview || "";
    }

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
        .then(() => alert("Extracted document text copied to clipboard!"))
        .catch(() => alert("Failed to copy to clipboard."));
}

async function summarizeDocument(event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    if (window.latestUploadedDocument) {
        renderDocumentAnalysis(window.latestUploadedDocument);
        return;
    }

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
        alert("Unable to analyze document.\n\n" + error.message);
    } finally {
        if (analyzeBtn) restoreButton(analyzeBtn);
    }
}

function setupDocumentUpload() {
    const dropzone = document.querySelector("#documentDropzone") || document.querySelector(".dropzone-box");
    if (!dropzone) return;

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
                uploadDocument(input.files[0]);
                input.value = "";
            }
        });
    }

    dropzone.addEventListener("click", function(event) {
        event.preventDefault();
        event.stopPropagation();
        input.click();
    });

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

    window.addEventListener("dragover", event => event.preventDefault(), false);
    window.addEventListener("drop", event => event.preventDefault(), false);
}

// ==================================================
// COMPLIANCE CHECKER
// ==================================================

async function runComplianceCheck() {
    const product = document.getElementById("complianceProduct")?.value.trim();
    const standard = document.getElementById("complianceStandard")?.value.trim();
    const documents = window.uploadedDocuments || [];

    try {
        const result = await apiRequest("/compliance/check", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ product, standard, documents })
        });

        renderComplianceResult(result);
        loadNotifications();
    } catch (error) {
        alert(error.message || "Compliance analysis failed.");
    }
}

function renderComplianceResult(result) {
    const body = document.querySelector(".stepper-card-body");
    if (!body) return;

    body.innerHTML = `
        <div class="compliance-result">
            <div class="score-circle">${result.score}%</div>
            <h2>${escapeHtml(result.result)}</h2>
            <span class="risk-badge">Risk: ${escapeHtml(result.risk)}</span>
            <div class="compliance-checks">
                ${result.checks.map(check => `
                    <div class="check-row">
                        <div>
                            <strong>${escapeHtml(check.name)}</strong>
                            <p>${escapeHtml(check.message)}</p>
                        </div>
                        <span class="check-status ${check.status.toLowerCase()}">${escapeHtml(check.status)}</span>
                    </div>
                `).join("")}
            </div>
            <div class="recommendations">
                <h3>AI Recommendations</h3>
                <ul>
                    ${result.recommendations.map(r => `<li>${escapeHtml(r)}</li>`).join("")}
                </ul>
            </div>
        </div>
    `;
}

// ==================================================
// INDUSTRY DASHBOARD
// ==================================================

async function loadDashboard() {
    try {
        const data = await apiRequest("/dashboard");
        const metrics = data.metrics || {};

        const pEl = document.getElementById("dashboard-products");
        const cEl = document.getElementById("dashboard-certificates");
        const sEl = document.getElementById("dashboard-score");
        const rEl = document.getElementById("dashboard-renewals");

        if (pEl) pEl.innerText = metrics.products || 12;
        if (cEl) cEl.innerText = metrics.certificates || 8;
        if (sEl) sEl.innerText = `${metrics.compliance || 92}%`;
        if (rEl) rEl.innerText = metrics.reports || metrics.renewals || 2;

        renderRecentActivity(data.recent_activity || []);
    } catch (error) {
        console.error("Dashboard error:", error);
    }
}

function renderRecentActivity(activities) {
    const existing = document.querySelector(".recent-activity");
    if (!existing) return;

    if (!activities.length) {
        existing.innerHTML = "<p>No recent activity.</p>";
        return;
    }

    existing.innerHTML = `
        <h3>Recent Activity</h3>
        ${activities.map(activity => `
            <div class="activity-row">
                <i class="fa-solid fa-clock"></i>
                <span>${escapeHtml(activity.query || activity.action_title || 'Activity')}</span>
            </div>
        `).join("")}
    `;
}

// ==================================================
// EVENT LISTENERS & INITIALIZATION
// ==================================================

function setupKeyboardListeners() {
    const aiInput = document.getElementById("aiQueryInput");
    if (aiInput) {
        aiInput.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                event.preventDefault();
                triggerAiChat();
            }
        });
    }

    const stdInput = document.getElementById("standardsSearchInput");
    if (stdInput) {
        stdInput.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                event.preventDefault();
                applyStandardsFilters();
            }
        });
    }

    const licInput = document.getElementById("licenseInput");
    if (licInput) {
        licInput.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                event.preventDefault();
                verifyLicenseNumber(licInput.value.trim());
            }
        });
    }

    const hmkInput = document.getElementById("hallmarkInput");
    if (hmkInput) {
        hmkInput.addEventListener("keydown", event => {
            if (event.key === "Enter") {
                event.preventDefault();
                verifyHallmark();
            }
        });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initLanguage();
    updateUserUI();

    setupDocumentUpload();
    setupKeyboardListeners();
    loadNotifications();

    const initialHash = window.location.hash.replace("#", "").trim();
    if (initialHash && document.getElementById(initialHash)) {
        switchView(initialHash);
    } else {
        switchView("landing");
    }

    document.addEventListener("click", () => {
        closeAllDropdowns();
    });
});

window.addEventListener("hashchange", () => {
    const hash = window.location.hash.replace("#", "").trim();
    if (hash && document.getElementById(hash)) {
        switchView(hash);
    }
});
