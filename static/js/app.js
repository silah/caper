// Test steps array
let testSteps = [];

// Selector types available for all element-targeting actions
const SELECTOR_OPTIONS = ['css', 'id', 'xpath', 'name', 'class', 'tag', 'link_text', 'partial_link_text', 'jspath', 'aria', 'text', 'label', 'placeholder', 'role'];

// Step categories
const stepCategories = {
    Navigation: [
        { value: 'navigate',             label: 'Navigate to URL' },
        { value: 'wait',                 label: 'Wait' },
        { value: 'wait_for_element',     label: 'Wait for Element' },
        { value: 'wait_for_load_state',  label: 'Wait for Load State' },
    ],
    Interactions: [
        { value: 'click',        label: 'Click' },
        { value: 'double_click', label: 'Double Click' },
        { value: 'right_click',  label: 'Right Click' },
        { value: 'hover',        label: 'Hover' },
        { value: 'type',         label: 'Type Text' },
        { value: 'clear',        label: 'Clear Input' },
        { value: 'select',       label: 'Select Dropdown Option' },
        { value: 'check',        label: 'Check (checkbox/radio)' },
        { value: 'uncheck',      label: 'Uncheck (checkbox/radio)' },
        { value: 'key_press',    label: 'Key Press' },
        { value: 'scroll_to',    label: 'Scroll To Element' },
        { value: 'drag_and_drop',label: 'Drag and Drop' },
        { value: 'upload_file',  label: 'Upload File' },
    ],
    Assertions: [
        { value: 'assert_title',   label: 'Assert Title' },
        { value: 'assert_text',    label: 'Assert Element Text' },
        { value: 'assert_visible', label: 'Assert Element Visible' },
        { value: 'assert_hidden',  label: 'Assert Element Hidden' },
        { value: 'assert_url',     label: 'Assert URL' },
        { value: 'assert_value',   label: 'Assert Input Value' },
    ],
    Utilities: [
        { value: 'screenshot',  label: 'Take Screenshot' },
        { value: 'execute_js',  label: 'Execute JavaScript' },
    ],
    Conditionals: [
        { value: 'click_if_exists', label: 'Click If Exists' },
        { value: 'pick_random',     label: 'Pick Random Element' },
    ],
};

function populateActionType(categorySelect, actionSelect) {
    const cat = categorySelect.value;
    const steps = stepCategories[cat] || [];
    actionSelect.innerHTML = steps.map(s => `<option value="${s.value}">${s.label}</option>`).join('');
}

// Action configurations
const actionConfigs = {
    navigate: {
        fields: [
            { name: 'value', label: 'URL', type: 'text', placeholder: 'https://example.com', required: true }
        ]
    },
    click: {
        fields: [
            { name: 'selectorType', label: 'Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'Selector', type: 'text', placeholder: '#submit-button  or  role:button:Submit', required: true }
        ]
    },
    type: {
        fields: [
            { name: 'selectorType', label: 'Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'Selector', type: 'text', placeholder: '#email-input', required: true },
            { name: 'value', label: 'Text to Type', type: 'text', placeholder: 'test@example.com', required: true }
        ]
    },
    wait: {
        fields: [
            { name: 'value', label: 'Seconds', type: 'number', placeholder: '1', required: true }
        ]
    },
    execute_js: {
        fields: [
            { name: 'value', label: 'JavaScript Code', type: 'textarea', rows: 8, placeholder: 'window.scrollTo(0, document.body.scrollHeight);', required: true }
        ]
    },
    screenshot: {
        fields: []
    },
    assert_title: {
        fields: [
            { name: 'value', label: 'Expected Title (partial match)', type: 'text', placeholder: 'Welcome', required: true }
        ]
    },
    assert_text: {
        fields: [
            { name: 'selectorType', label: 'Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'Selector', type: 'text', placeholder: '.message', required: true },
            { name: 'value', label: 'Expected Text (partial match)', type: 'text', placeholder: 'Success', required: true }
        ]
    },
    scroll_to: {
        fields: [
            { name: 'selectorType', label: 'Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'Selector', type: 'text', placeholder: '#footer', required: true }
        ]
    },
    select: {
        fields: [
            { name: 'selectorType', label: 'Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'Selector', type: 'text', placeholder: '#country-select', required: true },
            { name: 'selectBy', label: 'Select By', type: 'select', options: ['text', 'value', 'index'], required: true },
            { name: 'value', label: 'Option', type: 'text', placeholder: 'United Kingdom', required: true }
        ]
    },
    assert_visible: {
        fields: [
            { name: 'selectorType', label: 'Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'Selector', type: 'text', placeholder: '.success-banner', required: true }
        ]
    },
    assert_hidden: {
        fields: [
            { name: 'selectorType', label: 'Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'Selector', type: 'text', placeholder: '.loading-spinner', required: true }
        ]
    },
    assert_url: {
        fields: [
            { name: 'value', label: 'URL contains', type: 'text', placeholder: '/dashboard', required: true }
        ]
    },
    assert_value: {
        fields: [
            { name: 'selectorType', label: 'Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'Selector', type: 'text', placeholder: '#email-input', required: true },
            { name: 'value', label: 'Expected Value (partial match)', type: 'text', placeholder: 'user@example.com', required: true }
        ]
    },
    key_press: {
        fields: [
            { name: 'key', label: 'Key', type: 'select', options: ['Enter', 'Tab', 'Escape', 'Space', 'Backspace', 'Delete', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'], required: true },
            { name: 'selectorType', label: 'Target Selector Type (optional)', type: 'select', options: SELECTOR_OPTIONS, required: false },
            { name: 'selector', label: 'Target Selector (optional)', type: 'text', placeholder: 'Leave blank to send to focused element', required: false }
        ]
    },
    hover: {
        fields: [
            { name: 'selectorType', label: 'Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'Selector', type: 'text', placeholder: '.dropdown-trigger', required: true }
        ]
    },
    double_click: {
        fields: [
            { name: 'selectorType', label: 'Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'Selector', type: 'text', placeholder: '.editable-cell', required: true }
        ]
    },
    right_click: {
        fields: [
            { name: 'selectorType', label: 'Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'Selector', type: 'text', placeholder: '.context-menu-trigger', required: true }
        ]
    },
    check: {
        fields: [
            { name: 'selectorType', label: 'Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'Selector', type: 'text', placeholder: '#agree-checkbox', required: true }
        ]
    },
    uncheck: {
        fields: [
            { name: 'selectorType', label: 'Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'Selector', type: 'text', placeholder: '#newsletter-checkbox', required: true }
        ]
    },
    upload_file: {
        fields: [
            { name: 'selectorType', label: 'Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'File Input Selector', type: 'text', placeholder: 'input[type="file"]', required: true },
            { name: 'value', label: 'File Path', type: 'text', placeholder: '/path/to/file.pdf', required: true }
        ]
    },
    wait_for_load_state: {
        fields: [
            { name: 'value', label: 'Load State', type: 'select', options: ['networkidle', 'load', 'domcontentloaded'], required: true }
        ]
    },
    wait_for_element: {
        fields: [
            { name: 'selectorType', label: 'Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'Selector', type: 'text', placeholder: '.results-table', required: true },
            { name: 'value', label: 'Timeout (seconds)', type: 'number', placeholder: '10', required: false }
        ]
    },
    clear: {
        fields: [
            { name: 'selectorType', label: 'Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'Selector', type: 'text', placeholder: '#search-input', required: true }
        ]
    },
    drag_and_drop: {
        fields: [
            { name: 'selectorType', label: 'Source Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'Source Selector', type: 'text', placeholder: '.drag-handle', required: true },
            { name: 'targetSelectorType', label: 'Target Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'targetSelector', label: 'Target Selector', type: 'text', placeholder: '.drop-zone', required: true }
        ]
    },
    click_if_exists: {
        fields: [
            { name: 'selectorType', label: 'Selector Type', type: 'select', options: SELECTOR_OPTIONS, required: true },
            { name: 'selector', label: 'Selector', type: 'text', placeholder: '#cookie-banner .accept-btn', required: true }
        ]
    },
    pick_random: {
        fields: [
            { name: 'selector', label: 'CSS Selector (candidates)', type: 'text', placeholder: '.product-card', required: true },
            { name: 'filter', label: 'Exclude selector (optional)', type: 'text', placeholder: '.out-of-stock', required: false },
            { name: 'captureAttr', label: 'Capture attribute (blank = inner text)', type: 'text', placeholder: 'data-product-id', required: false },
            { name: 'storeAs', label: 'Store as variable name', type: 'text', placeholder: 'selected_product', required: true },
            { name: 'clickElement', label: 'Click picked element', type: 'select', options: ['yes', 'no'], required: true }
        ]
    }
};

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    const categorySelect = document.getElementById('stepCategory');
    const actionTypeSelect = document.getElementById('actionType');
    if (categorySelect && actionTypeSelect) {
        populateActionType(categorySelect, actionTypeSelect);
        categorySelect.addEventListener('change', () => {
            populateActionType(categorySelect, actionTypeSelect);
            updateStepConfig();
        });
        actionTypeSelect.addEventListener('change', updateStepConfig);
        updateStepConfig();
    }
    renderSteps();
});

// Update step configuration based on selected action
function updateStepConfig() {
    const actionType = document.getElementById('actionType').value;
    const config = actionConfigs[actionType];
    const stepConfig = document.getElementById('stepConfig');
    
    if (!config) {
        stepConfig.innerHTML = '';
        return;
    }
    
    let html = '';
    
    config.fields.forEach(field => {
        html += `<div class="form-group">`;
        html += `<label for="step_${field.name}">${field.label}${field.required ? ' *' : ''}</label>`;
        
        if (field.type === 'select') {
            html += `<select id="step_${field.name}" ${field.required ? 'required' : ''}>`;
            field.options.forEach(opt => {
                html += `<option value="${opt}">${opt}</option>`;
            });
            html += `</select>`;
        } else if (field.type === 'textarea') {
            html += `<textarea id="step_${field.name}" placeholder="${field.placeholder || ''}" ${field.required ? 'required' : ''} rows="${field.rows || 3}"></textarea>`;
        } else {
            html += `<input type="${field.type}" id="step_${field.name}" placeholder="${field.placeholder || ''}" ${field.required ? 'required' : ''}>`;
        }
        
        html += `</div>`;
    });
    
    stepConfig.innerHTML = html;
}

// Add a step to the test
function addStep() {
    const actionType = document.getElementById('actionType').value;
    const config = actionConfigs[actionType];

    if (!config) {
        alert('Invalid action type');
        return;
    }

    const step = { action: actionType };

    // Collect field values
    for (const field of config.fields) {
        const element = document.getElementById(`step_${field.name}`);
        if (!element) continue;

        const value = element.value.trim();

        if (field.required && !value) {
            alert(`${field.label} is required`);
            return;
        }

        step[field.name] = value;
    }

    // Collect intent (optional, shared across all step types)
    const intentEl = document.getElementById('stepIntent');
    if (intentEl && intentEl.value.trim()) {
        step.intent = intentEl.value.trim();
    }

    // Check if we should insert after a specific index
    if (typeof window.insertAfterIndex !== 'undefined') {
        testSteps.splice(window.insertAfterIndex + 1, 0, step);
        delete window.insertAfterIndex;
    } else {
        testSteps.push(step);
    }

    renderSteps();

    // Clear form
    for (const field of config.fields) {
        const element = document.getElementById(`step_${field.name}`);
        if (element) element.value = '';
    }
    if (intentEl) intentEl.value = '';
}

// Render the steps list
function renderSteps() {
    const stepsList = document.getElementById('stepsList');
    if (!stepsList) return;
    
    if (testSteps.length === 0) {
        stepsList.innerHTML = '<p class="empty-steps">No steps added yet. Add your first step below.</p>';
        return;
    }
    
    let html = '<ol class="steps-list">';
    
    testSteps.forEach((step, index) => {
        html += `<li class="step-item" draggable="true" data-index="${index}">`;
        html += `<div class="drag-handle">⋮⋮</div>`;
        html += `<div class="step-content">`;
        html += `<strong>${(step.action||'unknown').toUpperCase()}</strong>`;
        
        if (step.action === 'navigate') {
            html += ` - Navigate to: <code>${step.value}</code>`;
        } else if (step.action === 'click') {
            html += ` - Click element: <code>${step.selector}</code> (${step.selectorType})`;
        } else if (step.action === 'type') {
            html += ` - Type "${step.value}" into: <code>${step.selector}</code> (${step.selectorType})`;
        } else if (step.action === 'wait') {
            html += ` - Wait ${step.value} seconds`;
        } else if (step.action === 'execute_js') {
            html += ` - Execute: <code>${step.value.substring(0, 50)}${step.value.length > 50 ? '...' : ''}</code>`;
        } else if (step.action === 'screenshot') {
            html += ` - Take screenshot`;
        } else if (step.action === 'assert_title') {
            html += ` - Assert title contains: "${step.value}"`;
        } else if (step.action === 'assert_text') {
            html += ` - Assert element <code>${step.selector}</code> contains: "${step.value}"`;
        } else if (step.action === 'scroll_to') {
            html += ` - Scroll to element: <code>${step.selector}</code> (${step.selectorType})`;
        } else if (step.action === 'select') {
            html += ` - Select "${step.value}" by ${step.selectBy} in: <code>${step.selector}</code>`;
        } else if (step.action === 'assert_visible') {
            html += ` - Assert visible: <code>${step.selector}</code> (${step.selectorType})`;
        } else if (step.action === 'assert_url') {
            html += ` - Assert URL contains: "${step.value}"`;
        } else if (step.action === 'key_press') {
            html += ` - Press ${step.key}${step.selector ? ` on <code>${step.selector}</code>` : ' (focused element)'}`;
        } else if (step.action === 'hover') {
            html += ` - Hover over: <code>${step.selector}</code> (${step.selectorType})`;
        } else if (step.action === 'double_click') {
            html += ` - Double-click: <code>${step.selector}</code> (${step.selectorType})`;
        } else if (step.action === 'wait_for_element') {
            html += ` - Wait for: <code>${step.selector}</code> (${step.value || 10}s timeout)`;
        } else if (step.action === 'clear') {
            html += ` - Clear: <code>${step.selector}</code> (${step.selectorType})`;
        } else if (step.action === 'check') {
            html += ` - Check: <code>${step.selector}</code> (${step.selectorType})`;
        } else if (step.action === 'uncheck') {
            html += ` - Uncheck: <code>${step.selector}</code> (${step.selectorType})`;
        } else if (step.action === 'upload_file') {
            html += ` - Upload "${step.value}" to: <code>${step.selector}</code>`;
        } else if (step.action === 'wait_for_load_state') {
            html += ` - Wait for load state: ${step.value}`;
        } else if (step.action === 'assert_hidden') {
            html += ` - Assert hidden: <code>${step.selector}</code> (${step.selectorType})`;
        } else if (step.action === 'assert_value') {
            html += ` - Assert value "${step.value}" in: <code>${step.selector}</code>`;
        } else if (step.action === 'right_click') {
            html += ` - Right-click: <code>${step.selector}</code> (${step.selectorType})`;
        } else if (step.action === 'drag_and_drop') {
            html += ` - Drag <code>${step.selector}</code> to <code>${step.targetSelector}</code>`;
        } else if (step.action === 'click_if_exists') {
            html += ` - Click <code>${step.selector}</code> if present, skip otherwise`;
        } else if (step.action === 'pick_random') {
            const capture = step.captureAttr ? `attr:${step.captureAttr}` : 'text';
            const click = step.clickElement !== 'no' ? ', click' : '';
            const excl = step.filter ? ` (excl. <code>${step.filter}</code>)` : '';
            html += ` - Pick random <code>${step.selector}</code>${excl} → <code>{{${step.storeAs}}}</code> [${capture}${click}]`;
        }

        if (step.intent) {
            html += `<div class="step-intent">${step.intent.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</div>`;
        }
        html += `</div>`;
        html += `<div class="step-actions">`;
        html += `<button class="btn btn-sm btn-primary" onclick="insertStepAfter(${index})">+ Insert</button>`;
        html += `<button class="btn btn-sm btn-danger" onclick="removeStep(${index})">Remove</button>`;
        html += `</div>`;
        html += `</li>`;
    });
    
    html += '</ol>';
    stepsList.innerHTML = html;
    
    // Add drag and drop event listeners
    setupDragAndDrop();
}

// Setup drag and drop functionality
function setupDragAndDrop() {
    const items = document.querySelectorAll('.step-item');
    let draggedItem = null;
    
    items.forEach(item => {
        item.addEventListener('dragstart', function(e) {
            draggedItem = this;
            this.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/html', this.innerHTML);
        });
        
        item.addEventListener('dragend', function(e) {
            this.classList.remove('dragging');
            items.forEach(item => item.classList.remove('drag-over'));
        });
        
        item.addEventListener('dragover', function(e) {
            if (e.preventDefault) {
                e.preventDefault();
            }
            e.dataTransfer.dropEffect = 'move';
            
            if (this !== draggedItem) {
                this.classList.add('drag-over');
            }
            return false;
        });
        
        item.addEventListener('dragleave', function(e) {
            this.classList.remove('drag-over');
        });
        
        item.addEventListener('drop', function(e) {
            if (e.stopPropagation) {
                e.stopPropagation();
            }
            
            if (draggedItem !== this) {
                const draggedIndex = parseInt(draggedItem.dataset.index);
                const targetIndex = parseInt(this.dataset.index);
                
                // Reorder the array
                const item = testSteps.splice(draggedIndex, 1)[0];
                testSteps.splice(targetIndex, 0, item);
                
                renderSteps();
            }
            
            return false;
        });
    });
}

// Insert a step after a specific index
function insertStepAfter(index) {
    // Save the current index where we want to insert
    window.insertAfterIndex = index;
    
    // Scroll to the add step section
    document.querySelector('.add-step-section').scrollIntoView({ behavior: 'smooth' });
    
    // Show a message
    const actionType = document.getElementById('actionType');
    if (actionType) {
        actionType.focus();
    }
}

// Remove a step
function removeStep(index) {
    testSteps.splice(index, 1);
    renderSteps();
}

// Save the test
function saveTest() {
    const name = document.getElementById('testName').value.trim();
    const description = document.getElementById('testDescription').value.trim();
    
    if (!name) {
        alert('Please enter a test name');
        return;
    }
    
    if (testSteps.length === 0) {
        alert('Please add at least one step');
        return;
    }
    
    const browserEl = document.querySelector('input[name="browserChoice"]:checked');
    const autoHealEl = document.getElementById('autoHeal');
    const data = {
        name: name,
        description: description,
        steps: testSteps,
        browser: browserEl ? browserEl.value : 'firefox',
        auto_heal: autoHealEl ? autoHealEl.checked : false,
    };

    fetch('/api/tests', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Test created successfully!');
            window.location.href = '/tests';
        } else {
            alert('Error creating test: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('Error creating test: ' + error);
    });
}

// Update an existing test
function updateTest() {
    // Get testId from window (set in edit page)
    if (typeof testId === 'undefined') {
        alert('Test ID not found');
        return;
    }
    
    const name = document.getElementById('testName').value.trim();
    const description = document.getElementById('testDescription').value.trim();
    
    if (!name) {
        alert('Please enter a test name');
        return;
    }
    
    if (testSteps.length === 0) {
        alert('Please add at least one step');
        return;
    }
    
    const data = {
        name: name,
        description: description,
        steps: testSteps
    };
    
    fetch(`/api/tests/${testId}`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Test updated successfully!');
            window.location.href = `/test/${testId}`;
        } else {
            alert('Error updating test: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        alert('Error updating test: ' + error);
    });
}

// Reset the test builder
function resetTest() {
    if (!confirm('Are you sure you want to reset? All steps will be lost.')) {
        return;
    }
    
    document.getElementById('testName').value = '';
    document.getElementById('testDescription').value = '';
    testSteps = [];
    renderSteps();
}
