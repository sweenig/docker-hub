// settings.js - Handles settings modal and CRUD for services and categories

function openSettingsDialog() {
    document.getElementById('settingsModal').style.display = 'block';
    loadCategories();
    showTab('general');
}

function closeSettingsDialog() {
    document.getElementById('settingsModal').style.display = 'none';
}

function openServiceDialog() {
    document.getElementById('serviceModal').style.display = 'block';
}

function closeServiceDialog() {
    document.getElementById('serviceModal').style.display = 'none';
}

function showTab(tab) {
    const tabs = document.querySelectorAll('#settings-tabs button');
    tabs.forEach(button => {
        button.classList.toggle('active', button.getAttribute('onclick') === `showTab('${tab}')`);
    });
    document.getElementById('settings-categories').style.display = (tab === 'categories') ? 'block' : 'none';
    document.getElementById('settings-general').style.display = (tab === 'general') ? 'block' : 'none';
    if (tab === 'general') {
        loadSettings();
    }
}

// --- Services CRUD ---
function loadServices() {
    fetch('/api/services')
        .then(res => res.json())
        .then(data => {
            const services = data.services || {};
            const list = document.getElementById('services-list');
            list.innerHTML = '';
            Object.entries(services).forEach(([name, svc]) => {
                const div = document.createElement('div');
                div.className = 'settings-item';
                div.innerHTML = `
                    <span class="item-name">${name}</span>
                    <div class="item-actions">
                        <button onclick="editService('${name}')" title="Edit Service">✎</button>
                        <button onclick="deleteService('${name}')" title="Delete Service">🗑</button>
                    </div>
                `;
                list.appendChild(div);
            });
        });
}

// Helper function to get categories and build the select options
async function getCategoryOptions(selectedCategory = '') {
    const response = await fetch('/api/categories');
    const categories = await response.json();
    let options = Object.entries(categories).map(([name, cat]) => 
        `<option value="${name}" ${name === selectedCategory ? 'selected' : ''}>${cat.name || name}</option>`
    );
    // Always include "Other" category
    options.push(`<option value="Other" ${selectedCategory === 'Other' ? 'selected' : ''}>Other</option>`);
    return options.join('\n');
}

async function showServiceForm(name = '', svc = {}) {
    // remember which service is being edited so we can access host_port if needed
    window.currentEditingService = svc || {};
    const form = document.getElementById('service-form');
    form.style.display = 'block';
    
    // Get category options before building the form
    const categoryOptions = await getCategoryOptions(svc.category || '');
    
    const keyVal = svc.container_name || name || '';
    const portVal = svc.host_port || '';
    form.innerHTML = `
        <form onsubmit="submitServiceForm(event, '${name}')">
            <input type="hidden" name="key" value="${keyVal}">
            <input type="hidden" name="port" value="${portVal}">
            <div class="service-key">
                <div class="form-row">
                    <label>Container key:</label>
                    <input class="key-display" value="${keyVal}" disabled>
                </div>
                <div class="form-row service-port">
                    <label>Host port:</label>
                    <input class="key-display" value="${portVal}" disabled>
                </div>
            </div>
            <div class="form-row">
                <label>Display Name:</label>
                <input name="name" value="${svc.name || ''}" required>
            </div>
            <div class="form-row">
                <label>Description:</label>
                <input name="description" value="${svc.description || ''}">
            </div>
            <div class="form-row">
                <label>Icon:</label>
                <input name="icon" value="${svc.icon || ''}">
            </div>
            <div class="form-row checkbox-row">
                <input type="checkbox" name="use_ssl" id="use_ssl" ${svc.use_ssl ? 'checked' : ''}>
                <label for="use_ssl">Use SSL</label>
            </div>
            <div class="form-row">
                <label>Root Path:</label>
                <input name="root_path" value="${svc.root_path || ''}" placeholder="/admin">
            </div>
            <div class="form-row">
                <label>Category:</label>
                <select name="category" required>
                    ${categoryOptions}
                </select>
            </div>
            <button type="submit">Save</button>
            <button type="button" onclick="cancelServiceForm()">Cancel</button>
            <button type="button" class="exclude-button" onclick="excludeServiceFromForm(this)">Exclude</button>
        </form>
    `;
}

// Load general settings (app title + excluded services)
function loadSettings() {
    fetch('/api/settings')
        .then(res => res.json())
        .then(data => {
            const settings = data.settings || {};
            const excluded = data.excludedServices || [];
            document.getElementById('appTitleInput').value = settings.appTitle || '';
            renderExcludedList(excluded);
        });
}

function submitAppTitle() {
    const title = document.getElementById('appTitleInput').value;
    fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ appTitle: title })
    }).then(() => {
        alert('App title saved. Reload page to see changes if env not overriding.');
    });
}

function renderExcludedList(list) {
    const container = document.getElementById('excluded-list');
    container.innerHTML = '';
    if (!Array.isArray(list) || list.length === 0) {
        container.textContent = 'No excluded services.';
        return;
    }
    list.forEach(name => {
        const div = document.createElement('div');
        div.className = 'settings-item';
        div.innerHTML = `
            <span class="item-name">${name}</span>
            <div class="item-actions">
                <button onclick="unexcludeService('${name}')" title="Un-exclude">↩</button>
            </div>
        `;
        container.appendChild(div);
    });
}

function unexcludeService(name) {
    if (!confirm('Un-exclude ' + name + '?')) return;
    fetch(`/api/settings/exclude/${encodeURIComponent(name)}`, { method: 'DELETE' })
        .then(() => loadSettings());
}

function excludeServiceFromForm(btn) {
    // find the form and key value
    const form = btn && btn.form ? btn.form : btn.closest && btn.closest('form');
    if (!form) return;
    const key = form.key ? form.key.value : '';
    let port = form.port ? form.port.value : '';
    // if port not present in the form, try to read it from the current editing service
    if (!port && window.currentEditingService && window.currentEditingService.host_port) {
        port = window.currentEditingService.host_port;
    }
    if (!key) {
        alert('No container key available to exclude.');
        return;
    }
    const excludeName = port ? `${key}:${port}` : key;
    if (!confirm('Exclude ' + excludeName + ' from main view?')) return;
    fetch('/api/settings/exclude', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: excludeName, key: key, port: port })
    }).then(() => {
        // refresh excluded list in general tab
        loadSettings();
        // provide visual feedback
        alert('Service excluded.');
    });
}

function cancelServiceForm() {
    document.getElementById('service-form').style.display = 'none';
    window.currentEditingService = null;
    closeServiceDialog();
}

function submitServiceForm(e, oldName) {
    e.preventDefault();
    const form = e.target;
    const displayName = form.name.value;
    const svc = {
        name: displayName,
        description: form.description.value,
        icon: form.icon.value,
        use_ssl: !!(form.use_ssl && form.use_ssl.checked),
        root_path: form.root_path.value,
        category: form.category.value
    };
    const keyField = form.key ? form.key.value : '';
    const method = oldName && oldName !== '' ? 'PUT' : 'POST';
    const url = oldName && oldName !== '' ? `/api/services/${encodeURIComponent(oldName)}` : '/api/services';
    fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(keyField && method === 'POST' ? Object.assign({key: keyField}, svc) : svc)
    }).then(() => {
        loadServices();
        cancelServiceForm();
        // Refresh dashboard cards so edited service metadata is reflected immediately.
        window.location.reload();
    });
}

function editService(name) {
    fetch('/api/services')
        .then(res => res.json())
        .then(data => {
            const svc = data.services[name];
            showServiceForm(name, svc);
        });
}

// Open edit form for a service from its card
function openEditServiceModal(event, svc) {
    if (event && event.stopPropagation) event.stopPropagation();
    // Open the standalone service edit dialog
    openServiceDialog();
    // Fetch persisted services to determine whether to edit (PUT) or create (POST)
    fetch('/api/services')
        .then(res => res.json())
        .then(data => {
            const services = data.services || {};
            // Prefer container_name key if available, otherwise display name
            const key = svc.container_name || svc.name;
            if (key && services[key]) {
                const merged = Object.assign({}, svc, services[key]);
                showServiceForm(key, merged);
            } else if (svc.name && services[svc.name]) {
                const merged = Object.assign({}, svc, services[svc.name]);
                showServiceForm(svc.name, merged);
            } else {
                // New service - prefill form with values from the card
                const prefill = {
                    container_name: svc.container_name || key || '',
                    name: svc.name || key || '',
                    description: svc.description || '',
                    icon: svc.icon || '',
                    use_ssl: !!svc.use_ssl,
                    root_path: svc.root_path || '',
                    category: svc.category || ''
                };
                showServiceForm('', prefill);
            }
        });
}

function deleteService(name) {
    if (!confirm('Delete service ' + name + '?')) return;
    fetch(`/api/services/${encodeURIComponent(name)}`, { method: 'DELETE' })
        .then(() => loadServices());
}

// --- Categories CRUD ---
function loadCategories() {
    fetch('/api/categories')
        .then(res => res.json())
        .then(categories => {
            const list = document.getElementById('categories-list');
            list.innerHTML = '';

            // Fetch current order to render in that order
            fetch('/api/services')
                .then(r => r.json())
                .then(cfg => {
                    const order = Array.isArray(cfg.categoryOrder) ? cfg.categoryOrder : [];
                    const categoryNames = Object.keys(categories);
                    const ordered = [...order.filter(n => categoryNames.includes(n)), ...categoryNames.filter(n => !order.includes(n))];

                    // Make list container sortable
                    list.classList.add('draggable-list');
                    list.dataset.sortable = 'categories';

                    ordered.forEach((name) => {
                        const cat = categories[name];
                        const div = document.createElement('div');
                        div.className = 'settings-item draggable';
                        div.draggable = true;
                        div.dataset.category = name;
                        div.innerHTML = `
                            <span class="drag-handle">⠿</span>
                            <span class="item-name">${name}</span>
                            <div class="item-actions">
                                <button onclick="editCategory('${name}')" title="Edit Category">✎</button>
                                <button onclick="deleteCategory('${name}')" title="Delete Category">🗑</button>
                            </div>
                        `;
                        addDragHandlers(div);
                        list.appendChild(div);
                    });
                });
        });
}

function showCategoryForm(name = '', cat = {}) {
    const form = document.getElementById('category-form');
    form.style.display = 'block';
    form.innerHTML = `
        <form onsubmit="submitCategoryForm(event, '${name}')">
            <label>Name: <input name="name" value="${cat.name || name}" required></label><br>
            <label>Icon: <input name="icon" value="${cat.icon || ''}"></label><br>
            <button type="submit">Save</button>
            <button type="button" onclick="cancelCategoryForm()">Cancel</button>
        </form>
    `;
}

function cancelCategoryForm() {
    document.getElementById('category-form').style.display = 'none';
}

function submitCategoryForm(e, oldName) {
    e.preventDefault();
    const form = e.target;
    const cat = {
        name: form.name.value,
        icon: form.icon.value
    };
    const method = oldName && oldName !== '' ? 'PUT' : 'POST';
    const url = oldName && oldName !== '' ? `/api/categories/${encodeURIComponent(oldName)}` : '/api/categories';
    fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cat)
    }).then(() => {
        loadCategories();
        cancelCategoryForm();
    });
}

function editCategory(name) {
    fetch('/api/categories')
        .then(res => res.json())
        .then(categories => {
            const cat = categories[name];
            showCategoryForm(name, cat);
        });
}

function deleteCategory(name) {
    if (!confirm('Delete category ' + name + '?')) return;
    fetch(`/api/categories/${encodeURIComponent(name)}`, { method: 'DELETE' })
        .then(() => loadCategories());
}

// Modal close on outside click — ignore clicks that follow a text selection
window.addEventListener('click', function(event) {
    const settingsModal = document.getElementById('settingsModal');
    const serviceModal = document.getElementById('serviceModal');
    const target = event.target;
    if (target === settingsModal || target === serviceModal) {
        try {
            // If the user just made a text selection (drag), don't close the modal
            if (window.getSelection && window.getSelection().toString().length > 0) {
                return;
            }
        } catch (e) {
            // ignore selection errors and proceed to close
        }
        if (target === settingsModal) closeSettingsDialog();
        if (target === serviceModal) closeServiceDialog();
    }
});

// --- Drag and Drop Helpers for Categories ---
let dragSrcEl = null;

function addDragHandlers(el) {
    el.addEventListener('dragstart', handleDragStart);
    el.addEventListener('dragover', handleDragOver);
    el.addEventListener('drop', handleDrop);
    el.addEventListener('dragend', handleDragEnd);
}

function handleDragStart(e) {
    dragSrcEl = this;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', this.dataset.category);
    this.classList.add('dragging');
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const dragging = document.querySelector('.dragging');
    if (!dragging || this === dragging) return;
    const list = this.parentElement;
    const rect = this.getBoundingClientRect();
    const next = (e.clientY - rect.top) / rect.height > 0.5;
    if (next) {
        list.insertBefore(dragging, this.nextSibling);
    } else {
        list.insertBefore(dragging, this);
    }
}

function handleDrop(e) {
    e.preventDefault();
}

function handleDragEnd() {
    this.classList.remove('dragging');
    const list = document.getElementById('categories-list');
    const newOrder = Array.from(list.querySelectorAll('[data-category]')).map(el => el.dataset.category);
    fetch('/api/categories/order', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order: newOrder })
    });
}
