// settings.js - Handles settings modal and CRUD for services and categories

function openSettingsDialog() {
    document.getElementById('settingsModal').style.display = 'block';
    loadServices();
    loadCategories();
    showTab('services');
}

function closeSettingsDialog() {
    document.getElementById('settingsModal').style.display = 'none';
}

function showTab(tab) {
    document.getElementById('settings-services').style.display = (tab === 'services') ? 'block' : 'none';
    document.getElementById('settings-categories').style.display = (tab === 'categories') ? 'block' : 'none';
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
    const form = document.getElementById('service-form');
    form.style.display = 'block';
    
    // Get category options before building the form
    const categoryOptions = await getCategoryOptions(svc.category || '');
    
    form.innerHTML = `
        <form onsubmit="submitServiceForm(event, '${name}')">
            <label>Name: <input name="name" value="${svc.name || name}" required></label><br>
            <label>Description: <input name="description" value="${svc.description || ''}"></label><br>
            <label>Icon: <input name="icon" value="${svc.icon || ''}"></label><br>
            <label>Category: 
                <select name="category" required>
                    ${categoryOptions}
                </select>
            </label><br>
            <button type="submit">Save</button>
            <button type="button" onclick="cancelServiceForm()">Cancel</button>
        </form>
    `;
}

function cancelServiceForm() {
    document.getElementById('service-form').style.display = 'none';
}

function submitServiceForm(e, oldName) {
    e.preventDefault();
    const form = e.target;
    const svc = {
        name: form.name.value,
        description: form.description.value,
        icon: form.icon.value,
        category: form.category.value
    };
    const method = oldName && oldName !== '' ? 'PUT' : 'POST';
    const url = oldName && oldName !== '' ? `/api/services/${encodeURIComponent(oldName)}` : '/api/services';
    fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(svc)
    }).then(() => {
        loadServices();
        cancelServiceForm();
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

// Modal close on outside click
window.onclick = function(event) {
    const modal = document.getElementById('settingsModal');
    if (event.target === modal) {
        closeSettingsDialog();
    }
}

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
