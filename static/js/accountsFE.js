// Enhanced Accounts Frontend with Database Integration

// Global variables
let accountsData = [];

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    console.log('Accounts page loaded');
    loadAccountsData();
});

// Load accounts data from database
async function loadAccountsData() {
    try {
        // Load accounts from database
        const accountsResponse = await fetch('/api/dashboard/accounts');
        const accounts = await accountsResponse.json();
        accountsData = accounts.accounts || [];
        
        renderAccountsPage();
    } catch (error) {
        console.error('Error loading accounts data:', error);
        renderAccountsPage(); // Render with empty data
    }
}

// Render the main accounts page
function renderAccountsPage() {
    const root = document.getElementById('root');
    if (!root) return;
    
    // Calculate summary statistics
    const totalAccounts = accountsData.length;
    const totalBalance = accountsData.reduce((sum, account) => sum + (account.balance || 0), 0);
    const savingsAccounts = accountsData.filter(account => account.type === 'savings').length;
    const currentAccounts = accountsData.filter(account => account.type === 'current').length;
    const creditAccounts = accountsData.filter(account => account.type === 'credit').length;
    
    root.innerHTML = `
        <div class="accounts-container">
            <div class="page-header">
                <h1>🏦 My Accounts</h1>
                <p>Manage your bank accounts and financial institutions</p>
            </div>
            
            <div class="accounts-overview">
                <div class="overview-card">
                    <h3>Total Balance</h3>
                    <p class="balance-amount">₹${totalBalance.toLocaleString()}</p>
                </div>
                <div class="overview-card">
                    <h3>Total Accounts</h3>
                    <p class="account-count">${totalAccounts}</p>
                </div>
                <div class="overview-card">
                    <h3>Savings</h3>
                    <p class="savings-count">${savingsAccounts}</p>
                </div>
                <div class="overview-card">
                    <h3>Current</h3>
                    <p class="current-count">${currentAccounts}</p>
                </div>
                <div class="overview-card">
                    <h3>Credit</h3>
                    <p class="credit-count">${creditAccounts}</p>
                </div>
            </div>
            
            <div class="accounts-section">
                <div class="section-header">
                    <h2>My Bank Accounts</h2>
                    <button class="add-btn" onclick="showAddAccountModal()">+ Add Account</button>
                </div>
                
                <div class="accounts-grid">
                    ${renderAccountsGrid()}
                </div>
            </div>
            
            <!-- Add Account Modal -->
            <div id="addAccountModal" class="modal">
                <div class="modal-content">
                    <div class="modal-header">
                        <h2>Add New Account</h2>
                        <span class="close" onclick="closeAddAccountModal()">&times;</span>
                    </div>
                    <div class="modal-body">
                        <form id="addAccountForm">
                            <div class="form-group">
                                <label for="accountType">Account Type</label>
                                <select id="accountType" required>
                                    <option value="">Select Account Type</option>
                                    <option value="savings">Savings Account</option>
                                    <option value="current">Current Account</option>
                                    <option value="credit">Credit Account</option>
                                    <option value="fixed_deposit">Fixed Deposit</option>
                                    <option value="recurring_deposit">Recurring Deposit</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="bankName">Bank Name</label>
                                <input type="text" id="bankName" placeholder="e.g., HDFC Bank" required>
                            </div>
                            <div class="form-group">
                                <label for="branchName">Branch Name</label>
                                <input type="text" id="branchName" placeholder="e.g., Main Branch">
                            </div>
                            <div class="form-group">
                                <label for="accountNumber">Account Number</label>
                                <input type="text" id="accountNumber" placeholder="Account Number" required>
                            </div>
                            <div class="form-group">
                                <label for="balance">Current Balance (₹)</label>
                                <input type="number" id="balance" placeholder="0.00" step="0.01" required>
                            </div>
                            <div class="form-actions">
                                <button type="button" class="btn-secondary" onclick="closeAddAccountModal()">Cancel</button>
                                <button type="submit" class="btn-primary">Add Account</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Add event listeners
    setupAccountEventListeners();
}

// Render accounts grid
function renderAccountsGrid() {
    if (accountsData.length === 0) {
        return `
            <div class="empty-state">
                <div class="empty-icon">🏦</div>
                <h3>No Accounts Added Yet</h3>
                <p>Add your first bank account to get started with managing your finances</p>
                <button class="btn-primary" onclick="showAddAccountModal()">Add Your First Account</button>
            </div>
        `;
    }
    
    return accountsData.map(account => renderAccount(account)).join('');
}

// Render individual account
function renderAccount(account) {
    const balance = account.balance ? `₹${account.balance.toLocaleString()}` : '₹0';
    const accountNumber = account.acc_no ? `****${account.acc_no.slice(-4)}` : 'N/A';
    
    return `
        <div class="account-item" data-account-id="${account.id}">
            <div class="item-header">
                <div class="item-title">
                    <h4>${account.bank}</h4>
                    <span class="account-type">${account.type.charAt(0).toUpperCase() + account.type.slice(1)} Account</span>
                </div>
                <div class="item-actions">
                    <button class="edit-btn" onclick="editAccount(${account.id})" title="Edit Account">✏️</button>
                    <button class="delete-btn" onclick="deleteAccount(${account.id})" title="Delete Account">🗑️</button>
                </div>
            </div>
            <div class="item-details">
                <div class="detail-row">
                    <span class="label">Account Number:</span>
                    <span class="value">${accountNumber}</span>
                </div>
                <div class="detail-row">
                    <span class="label">Branch:</span>
                    <span class="value">${account.branch || 'N/A'}</span>
                </div>
                <div class="detail-row">
                    <span class="label">Balance:</span>
                    <span class="value balance-amount">${balance}</span>
                </div>
            </div>
        </div>
    `;
}

// Setup event listeners
function setupAccountEventListeners() {
    // Form submission
    const addAccountForm = document.getElementById('addAccountForm');
    if (addAccountForm) {
        addAccountForm.addEventListener('submit', handleAddAccount);
    }
}

// Handle add account form submission
async function handleAddAccount(e) {
    e.preventDefault();
    
    const formData = {
        type: document.getElementById('accountType').value,
        bank: document.getElementById('bankName').value,
        branch: document.getElementById('branchName').value,
        acc_no: document.getElementById('accountNumber').value,
        balance: parseFloat(document.getElementById('balance').value)
    };
    
    try {
        const response = await fetch('/api/accounts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });
        
        if (response.ok) {
            closeAddAccountModal();
            loadAccountsData(); // Reload data
            showNotification('Account added successfully!', 'success');
        } else {
            throw new Error('Failed to add account');
        }
    } catch (error) {
        console.error('Error adding account:', error);
        showNotification('Failed to add account. Please try again.', 'error');
    }
}

// Show add account modal
function showAddAccountModal() {
    document.getElementById('addAccountModal').style.display = 'block';
}

// Close add account modal
function closeAddAccountModal() {
    document.getElementById('addAccountModal').style.display = 'none';
    document.getElementById('addAccountForm').reset();
}

// Edit account
function editAccount(accountId) {
    const account = accountsData.find(acc => acc.id === accountId);
    if (!account) return;
    
    // Pre-fill form with account data
    document.getElementById('accountType').value = account.type;
    document.getElementById('bankName').value = account.bank;
    document.getElementById('branchName').value = account.branch || '';
    document.getElementById('accountNumber').value = account.acc_no || '';
    document.getElementById('balance').value = account.balance || '';
    
    showAddAccountModal();
}

// Delete account
async function deleteAccount(accountId) {
    if (!confirm('Are you sure you want to delete this account?')) return;
    
    try {
        const response = await fetch(`/api/accounts/${accountId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            loadAccountsData(); // Reload data
            showNotification('Account deleted successfully!', 'success');
        } else {
            throw new Error('Failed to delete account');
        }
    } catch (error) {
        console.error('Error deleting account:', error);
        showNotification('Failed to delete account. Please try again.', 'error');
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
