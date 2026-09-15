/* app.js */

// Navigation controller for switching between UI screens/views
function switchView(viewId) {
    const sections = document.querySelectorAll('.view-section');
    sections.forEach(section => {
        section.classList.add('hidden');
    });

    const targetView = document.getElementById(`view-${viewId}`);
    if (targetView) {
        targetView.classList.remove('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

// Role selection modal controls
function openRoleModal() {
    const modal = document.getElementById('role-modal');
    if (modal) {
        modal.classList.remove('hidden');
    }
}

function closeRoleModal() {
    const modal = document.getElementById('role-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

function selectRole(roleName) {
    console.log(`Role selected: ${roleName}`);
    closeRoleModal();
}