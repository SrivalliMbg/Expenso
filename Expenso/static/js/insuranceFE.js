// Enhanced Insurance Frontend with Database Integration

// Global variables
let insuranceData = [];
let accountsData = [];

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
  console.log('Insurance page loaded');
  loadInsuranceData();
});

// Load insurance data from database
async function loadInsuranceData() {
  try {
    // Load insurance from database
    const insuranceResponse = await fetch('/api/insurance');
    const insurance = await insuranceResponse.json();
    insuranceData = insurance.insurance || [];
    
    // Load accounts for linking
    const accountsResponse = await fetch('/api/dashboard/accounts');
    const accounts = await accountsResponse.json();
    accountsData = accounts.accounts || [];
    
    renderInsurancePage();
  } catch (error) {
    console.error('Error loading insurance data:', error);
    renderInsurancePage(); // Render with empty data
  }
}

// Render the main insurance page
function renderInsurancePage() {
  const root = document.getElementById('root');
  if (!root) return;
  
  // Calculate summary statistics
  const totalPolicies = insuranceData.length;
  const totalPremium = insuranceData.reduce((sum, policy) => sum + (policy.premium_amount || 0), 0);
  const totalCoverage = insuranceData.reduce((sum, policy) => sum + (policy.coverage_amount || 0), 0);
  const healthPolicies = insuranceData.filter(policy => policy.policy_type === 'Health').length;
  const lifePolicies = insuranceData.filter(policy => policy.policy_type === 'Life').length;
  const vehiclePolicies = insuranceData.filter(policy => policy.policy_type === 'Vehicle').length;
  
  // Calculate upcoming renewals
  const upcomingRenewals = insuranceData.filter(policy => {
    if (!policy.next_due_date) return false;
    const dueDate = new Date(policy.next_due_date);
    const today = new Date();
    const diffTime = dueDate - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays <= 30 && diffDays >= 0;
  }).length;
  
  root.innerHTML = `
    <div class="insurance-container">
      <div class="page-header">
        <h1>🛡️ My Insurance</h1>
        <p>Manage your insurance policies and coverage</p>
      </div>
      
      <div class="insurance-overview">
        <div class="overview-card">
          <h3>Total Policies</h3>
          <p class="policy-count">${totalPolicies}</p>
        </div>
        <div class="overview-card">
          <h3>Total Coverage</h3>
          <p class="coverage-amount">₹${totalCoverage.toLocaleString()}</p>
        </div>
        <div class="overview-card">
          <h3>Annual Premium</h3>
          <p class="premium-amount">₹${totalPremium.toLocaleString()}</p>
        </div>
        <div class="overview-card ${upcomingRenewals > 0 ? 'warning' : ''}">
          <h3>Due Soon</h3>
          <p class="renewal-count">${upcomingRenewals}</p>
        </div>
      </div>
      
      <div class="insurance-section">
        <div class="section-header">
          <h2>My Insurance Policies</h2>
          <div class="header-actions">
            <button class="add-btn" onclick="showAddPolicyModal()">+</button>
            <button class="reminder-btn" onclick="showRenewalReminders()">🔔 Renewals</button>
          </div>
        </div>
        
        <div class="policies-grid">
          ${renderInsuranceGrid()}
        </div>
      </div>

    <!-- Add Policy Modal -->
    <div id="addPolicyModal" class="modal">
      <div class="modal-content">
        <div class="modal-header">
          <h2>Add New Insurance Policy</h2>
          <span class="close" onclick="closeAddPolicyModal()">&times;</span>
        </div>
        <div class="modal-body">
          <form id="addPolicyForm">
            <div class="form-group">
              <label for="policyName">Policy Name</label>
              <input type="text" id="policyName" placeholder="e.g., Health Shield Plus" required>
            </div>
            <div class="form-group">
              <label for="policyType">Policy Type</label>
              <select id="policyType" required>
                <option value="">Select Policy Type</option>
                <option value="Health">Health Insurance</option>
                <option value="Life">Life Insurance</option>
                <option value="Vehicle">Vehicle Insurance</option>
                <option value="Home">Home Insurance</option>
                <option value="Travel">Travel Insurance</option>
                <option value="Other">Other</option>
              </select>
            </div>
            <div class="form-group">
              <label for="premiumAmount">Annual Premium (₹)</label>
              <input type="number" id="premiumAmount" placeholder="25000" min="0" required>
            </div>
            <div class="form-group">
              <label for="coverageAmount">Coverage Amount (₹)</label>
              <input type="number" id="coverageAmount" placeholder="500000" min="0" required>
            </div>
            <div class="form-group">
              <label for="nextDueDate">Next Due Date</label>
              <input type="date" id="nextDueDate" required>
            </div>
            <div class="form-group">
              <label for="linkedAccount">Linked Account</label>
              <select id="linkedAccount">
                <option value="">Select Account (Optional)</option>
                ${accountsData.map(account => 
                  `<option value="${account.id}">${account.bank} - ${account.type}</option>`
                ).join('')}
              </select>
            </div>
            <div class="form-actions">
              <button type="button" class="btn-secondary" onclick="closeAddPolicyModal()">Cancel</button>
              <button type="submit" class="btn-primary">Add Policy</button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Renewal Reminders Modal -->
    <div id="renewalModal" class="modal">
      <div class="modal-content">
        <div class="modal-header">
          <h2>Renewal Reminders</h2>
          <span class="close" onclick="closeRenewalModal()">&times;</span>
        </div>
        <div class="modal-body">
          ${renderRenewalReminders()}
        </div>
      </div>
    </div>
  `;
  
  // Add event listeners
  setupInsuranceEventListeners();
}

// Render insurance grid
function renderInsuranceGrid() {
  if (insuranceData.length === 0) {
    return `
      <div class="empty-state">
        <div class="empty-icon">🛡️</div>
        <h3>No Insurance Policies Added Yet</h3>
        <p>Add your first insurance policy to get started with managing your coverage</p>
        <button class="btn-primary" onclick="showAddPolicyModal()">Add Your First Policy</button>
      </div>
    `;
  }
  
  return insuranceData.map(policy => renderPolicy(policy)).join('');
}

// Render individual policy
function renderPolicy(policy) {
  const dueDate = policy.next_due_date ? new Date(policy.next_due_date).toLocaleDateString('en-GB') : 'N/A';
  const isDueSoon = policy.next_due_date ? isDueWithin30Days(policy.next_due_date) : false;
  const premiumAmount = policy.premium_amount ? `₹${policy.premium_amount.toLocaleString()}` : 'N/A';
  const coverageAmount = policy.coverage_amount ? `₹${policy.coverage_amount.toLocaleString()}` : 'N/A';
  
  return `
    <div class="policy-item ${isDueSoon ? 'due-soon' : ''}" data-policy-id="${policy.id}">
      <div class="item-header">
        <div class="item-title">
          <h4>${policy.policy_name}</h4>
          <span class="policy-type">${policy.policy_type} Insurance</span>
        </div>
        <div class="item-actions">
          <button class="edit-btn" onclick="editPolicy(${policy.id})" title="Edit Policy">✏️</button>
          <button class="delete-btn" onclick="deletePolicy(${policy.id})" title="Delete Policy">🗑️</button>
        </div>
      </div>
      <div class="item-details">
        <div class="detail-row">
          <span class="label">Premium:</span>
          <span class="value">${premiumAmount}</span>
        </div>
        <div class="detail-row">
          <span class="label">Coverage:</span>
          <span class="value">${coverageAmount}</span>
        </div>
        <div class="detail-row">
          <span class="label">Next Due:</span>
          <span class="value ${isDueSoon ? 'due-soon' : ''}">${dueDate}</span>
        </div>
      </div>
      ${isDueSoon ? '<div class="status-badge due-soon">Due Soon</div>' : ''}
    </div>
  `;
}

// Check if policy is due within 30 days
function isDueWithin30Days(dueDate) {
  const due = new Date(dueDate);
  const today = new Date();
  const diffTime = due - today;
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  return diffDays <= 30 && diffDays >= 0;
}

// Render renewal reminders
function renderRenewalReminders() {
  const upcomingRenewals = insuranceData.filter(policy => {
    if (!policy.next_due_date) return false;
    return isDueWithin30Days(policy.next_due_date);
  });
  
  if (upcomingRenewals.length === 0) {
    return `
      <div class="no-reminders">
        <div class="reminder-icon">✅</div>
        <h3>All Policies Up to Date!</h3>
        <p>No policies are due for renewal in the next 30 days.</p>
      </div>
    `;
  }
  
  return `
    <div class="reminders-list">
      ${upcomingRenewals.map(policy => {
        const dueDate = new Date(policy.next_due_date);
        const today = new Date();
        const diffTime = dueDate - today;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        
        return `
          <div class="reminder-item">
            <div class="reminder-info">
              <h4>${policy.policy_name}</h4>
              <p>${policy.policy_type} Insurance</p>
              <p>Premium: ₹${policy.premium_amount?.toLocaleString() || 'N/A'}</p>
            </div>
            <div class="reminder-date">
              <div class="days-left ${diffDays <= 7 ? 'urgent' : ''}">${diffDays} days</div>
              <div class="due-date">Due: ${dueDate.toLocaleDateString('en-GB')}</div>
            </div>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

// Setup event listeners
function setupInsuranceEventListeners() {
  // Form submission
  const addPolicyForm = document.getElementById('addPolicyForm');
  if (addPolicyForm) {
    addPolicyForm.addEventListener('submit', handleAddPolicy);
  }
}

// Handle add policy form submission
async function handleAddPolicy(e) {
  e.preventDefault();
  
  const formData = {
    policy_name: document.getElementById('policyName').value,
    policy_type: document.getElementById('policyType').value,
    premium_amount: document.getElementById('premiumAmount').value,
    coverage_amount: document.getElementById('coverageAmount').value,
    next_due_date: document.getElementById('nextDueDate').value,
    account_id: document.getElementById('linkedAccount').value || null
  };
  
  try {
    const response = await fetch('/api/insurance', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(formData)
    });
    
    if (response.ok) {
      closeAddPolicyModal();
      loadInsuranceData(); // Reload data
      showNotification('Policy added successfully!', 'success');
    } else {
      throw new Error('Failed to add policy');
    }
  } catch (error) {
    console.error('Error adding policy:', error);
    showNotification('Failed to add policy. Please try again.', 'error');
  }
}

// Show add policy modal
function showAddPolicyModal() {
  document.getElementById('addPolicyModal').style.display = 'block';
}

// Close add policy modal
function closeAddPolicyModal() {
  document.getElementById('addPolicyModal').style.display = 'none';
  document.getElementById('addPolicyForm').reset();
}

// Show renewal reminders modal
function showRenewalReminders() {
  document.getElementById('renewalModal').style.display = 'block';
}

// Close renewal reminders modal
function closeRenewalModal() {
  document.getElementById('renewalModal').style.display = 'none';
}

// Edit policy
function editPolicy(policyId) {
  const policy = insuranceData.find(p => p.id === policyId);
  if (!policy) return;
  
  // Pre-fill form with policy data
  document.getElementById('policyName').value = policy.policy_name;
  document.getElementById('policyType').value = policy.policy_type;
  document.getElementById('premiumAmount').value = policy.premium_amount || '';
  document.getElementById('coverageAmount').value = policy.coverage_amount || '';
  document.getElementById('nextDueDate').value = policy.next_due_date || '';
  document.getElementById('linkedAccount').value = policy.account_id || '';
  
  showAddPolicyModal();
}

// Delete policy
async function deletePolicy(policyId) {
  if (!confirm('Are you sure you want to delete this policy?')) return;
  
  try {
    const response = await fetch(`/api/insurance/${policyId}`, {
      method: 'DELETE'
    });
    
    if (response.ok) {
      loadInsuranceData(); // Reload data
      showNotification('Policy deleted successfully!', 'success');
    } else {
      throw new Error('Failed to delete policy');
    }
  } catch (error) {
    console.error('Error deleting policy:', error);
    showNotification('Failed to delete policy. Please try again.', 'error');
  }
}


// Show notification
function showNotification(message, type = 'info') {
  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.textContent = message;
  
  document.body.appendChild(notification);
  
  setTimeout(() => {
    notification.remove();
  }, 3000);
}
