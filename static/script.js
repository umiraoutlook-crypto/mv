// Interactive UI scripts for Job Portal & Admin Portal

document.addEventListener('DOMContentLoaded', function () {
    // 1. Quick Fill Demo Credentials on Login Page
    const fillAdminBtn = document.getElementById('fill-admin-creds');
    const fillUserBtn = document.getElementById('fill-user-creds');
    const emailInput = document.getElementById('login-email');
    const passwordInput = document.getElementById('login-password');

    if (fillAdminBtn && emailInput && passwordInput) {
        fillAdminBtn.addEventListener('click', function () {
            emailInput.value = 'admin';
            passwordInput.value = 'admin123';
            emailInput.focus();
        });
    }

    const loginParams = new URLSearchParams(window.location.search);
    if (loginParams.get('role') === 'admin' && emailInput && passwordInput) {
        emailInput.value = 'admin';
        passwordInput.value = 'admin123';
    }

    if (fillUserBtn && emailInput && passwordInput) {
        fillUserBtn.addEventListener('click', function () {
            emailInput.value = 'kaifhadgone@gmail.com';
            passwordInput.value = '';
            passwordInput.focus();
        });
    }

    // 2. Client-side Search / Filter for Job Openings on Home Page
    const searchInput = document.getElementById('job-search-input');
    const deptSelect = document.getElementById('job-dept-filter');
    const jobCards = document.querySelectorAll('.job-card-wrapper');
    const noResultsMsg = document.getElementById('no-search-results');

    function filterJobs() {
        if (!jobCards.length) return;
        const query = searchInput ? searchInput.value.toLowerCase().trim() : '';
        const dept = deptSelect ? deptSelect.value.toLowerCase().trim() : '';

        let visibleCount = 0;

        jobCards.forEach(function (card) {
            const title = card.getAttribute('data-title') || '';
            const cardDept = card.getAttribute('data-dept') || '';
            const desc = card.getAttribute('data-desc') || '';
            const location = card.getAttribute('data-location') || '';

            const matchesQuery = !query || title.includes(query) || desc.includes(query) || location.includes(query);
            const matchesDept = !dept || cardDept === dept;

            if (matchesQuery && matchesDept) {
                card.style.display = '';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });

        if (noResultsMsg) {
            noResultsMsg.style.display = (visibleCount === 0) ? 'block' : 'none';
        }

        const countBadge = document.getElementById('visible-jobs-count');
        if (countBadge) {
            countBadge.textContent = visibleCount;
        }
    }

    if (searchInput) {
        searchInput.addEventListener('input', filterJobs);
    }
    if (deptSelect) {
        deptSelect.addEventListener('change', filterJobs);
    }

    // 3. Client-side Filter for Applications Table in Admin
    const appStatusFilter = document.getElementById('admin-app-status-filter');
    const appOpeningFilter = document.getElementById('admin-app-opening-filter');
    const appSearchInput = document.getElementById('admin-app-search');
    const appRows = document.querySelectorAll('.app-table-row');
    const noAppResults = document.getElementById('no-app-filter-results');

    function filterApplications() {
        if (!appRows.length) return;
        const status = appStatusFilter ? appStatusFilter.value.toLowerCase().trim() : '';
        const opening = appOpeningFilter ? appOpeningFilter.value.trim() : '';
        const query = appSearchInput ? appSearchInput.value.toLowerCase().trim() : '';

        let visible = 0;

        appRows.forEach(function (row) {
            const rowStatus = (row.getAttribute('data-status') || '').toLowerCase();
            const rowOpening = row.getAttribute('data-opening-id') || '';
            const rowText = (row.textContent || '').toLowerCase();

            const matchesStatus = !status || rowStatus === status;
            const matchesOpening = !opening || rowOpening === opening;
            const matchesQuery = !query || rowText.includes(query);

            if (matchesStatus && matchesOpening && matchesQuery) {
                row.style.display = '';
                visible++;
            } else {
                row.style.display = 'none';
            }
        });

        if (noAppResults) {
            noAppResults.style.display = (visible === 0) ? '' : 'none';
        }
    }

    if (appStatusFilter) appStatusFilter.addEventListener('change', filterApplications);
    if (appOpeningFilter) appOpeningFilter.addEventListener('change', filterApplications);
    if (appSearchInput) appSearchInput.addEventListener('input', filterApplications);

    document.querySelectorAll('[data-admin-tab]').forEach(function (card) {
        card.addEventListener('click', function () {
            const tabId = card.getAttribute('data-admin-tab');
            const status = card.getAttribute('data-admin-status');
            const tabBtn = document.getElementById(tabId);
            if (tabBtn) {
                tabBtn.click();
            }
            if (status && appStatusFilter) {
                appStatusFilter.value = status;
                filterApplications();
            }
        });
    });

    // 4. Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            try {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            } catch (e) {
                alert.style.display = 'none';
            }
        }, 6000);
    });
});
