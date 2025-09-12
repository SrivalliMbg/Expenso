// Enhanced Investments Frontend with Database Integration

// Global variables
let investmentsData = [];
let accountsData = [];

// Utility function to format currency properly
function formatCurrency(amount) {
  // Ensure amount is a valid number
  const numAmount = parseFloat(amount);
  if (isNaN(numAmount)) return '0';
  
  // Format with proper locale and limit decimal places
  return numAmount.toLocaleString('en-IN', {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0
  });
}

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
  console.log('Investments page loaded');
  loadInvestmentsData();
});

// Load investments data from database
async function loadInvestmentsData() {
  try {
    // Load investments from database
    const investmentsResponse = await fetch('/api/investments');
    const investments = await investmentsResponse.json();
    investmentsData = investments.investments || [];
    
    // Load accounts for linking
    const accountsResponse = await fetch('/api/dashboard/accounts');
    const accounts = await accountsResponse.json();
    accountsData = accounts.accounts || [];
    
    renderInvestmentsPage();
  } catch (error) {
    console.error('Error loading investments data:', error);
    renderInvestmentsPage(); // Render with empty data
  }
}

// Render the main investments page
function renderInvestmentsPage() {
  const root = document.getElementById('root');
  if (!root) return;
  
  // Calculate summary statistics
  const totalInvestments = investmentsData.length;
  const totalAmount = investmentsData.reduce((sum, investment) => {
    const amount = parseFloat(investment.amount) || 0;
    console.log('Investment amount:', investment.amount, 'Parsed:', amount);
    return sum + amount;
  }, 0);
  console.log('Total amount calculated:', totalAmount);
  const stocksCount = investmentsData.filter(inv => inv.investment_type === 'Stocks').length;
  const mutualFundsCount = investmentsData.filter(inv => inv.investment_type === 'Mutual Funds').length;
  const fixedDepositsCount = investmentsData.filter(inv => inv.investment_type === 'Fixed Deposits').length;
  
  // Calculate maturity dates
  const upcomingMaturities = investmentsData.filter(investment => {
    if (!investment.maturity_date) return false;
    const maturityDate = new Date(investment.maturity_date);
    const today = new Date();
    const diffTime = maturityDate - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays <= 30 && diffDays >= 0;
  }).length;
  
  root.innerHTML = `
    <div class="investments-container">
      <div class="page-header">
        <h1>📈 My Investments</h1>
        <p>Track your investment portfolio and returns</p>
      </div>
      
      <div class="investments-overview">
        <div class="overview-card">
          <h3>Total Investments</h3>
          <p class="investment-count">${totalInvestments}</p>
        </div>
        <div class="overview-card">
          <h3>Total Amount</h3>
          <p class="total-amount">₹${formatCurrency(totalAmount)}</p>
        </div>
        <div class="overview-card">
          <h3>Stocks</h3>
          <p class="stocks-count">${stocksCount}</p>
        </div>
        <div class="overview-card">
          <h3>Mutual Funds</h3>
          <p class="funds-count">${mutualFundsCount}</p>
        </div>
        <div class="overview-card">
          <h3>Fixed Deposits</h3>
          <p class="fd-count">${fixedDepositsCount}</p>
        </div>
        <div class="overview-card ${upcomingMaturities > 0 ? 'warning' : ''}">
          <h3>Maturity Soon</h3>
          <p class="maturity-count">${upcomingMaturities}</p>
        </div>
      </div>
      
      <div class="investments-section">
        <div class="section-header">
          <h2>My Investments</h2>
          <button class="add-btn" onclick="showAddInvestmentModal()">+</button>
        </div>
        
        <div class="investments-grid">
          ${renderInvestmentsGrid()}
        </div>
      </div>

      <!-- Add Investment Modal -->
      <div id="addInvestmentModal" class="modal">
        <div class="modal-content">
          <div class="modal-header">
            <h2>Add New Investment</h2>
            <span class="close" onclick="closeAddInvestmentModal()">&times;</span>
          </div>
          <div class="modal-body">
            <form id="addInvestmentForm">
              <div class="form-group">
                <label for="investmentType">Investment Type</label>
                <select id="investmentType" required>
                  <option value="">Select Investment Type</option>
                  <option value="Stocks">Stocks</option>
                  <option value="Mutual Funds">Mutual Funds</option>
                  <option value="Fixed Deposits">Fixed Deposits</option>
                  <option value="Bonds">Bonds</option>
                  <option value="Real Estate">Real Estate</option>
                  <option value="Gold">Gold</option>
                  <option value="Other">Other</option>
                </select>
              </div>
              <div class="form-group">
                <label for="amount">Investment Amount (₹)</label>
                <input type="number" id="amount" placeholder=" " min="0" required>
              </div>
              <div class="form-group">
                <label for="startDate">Start Date</label>
                <input type="date" id="startDate" required>
              </div>
              <div class="form-group">
                <label for="maturityDate">Maturity Date</label>
                <input type="date" id="maturityDate">
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
                <button type="button" class="btn-secondary" onclick="closeAddInvestmentModal()">Cancel</button>
                <button type="submit" class="btn-primary">Add Investment</button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  `;
  
  // Add event listeners
  setupInvestmentEventListeners();
}

// Render investments grid
function renderInvestmentsGrid() {
  if (investmentsData.length === 0) {
    return `
      <div class="empty-state">
        <div class="empty-icon">📈</div>
        <h3>No Investments Added Yet</h3>
        <p>Add your first investment to start building your portfolio</p>
        <button class="btn-primary" onclick="showAddInvestmentModal()">Add Your First Investment</button>
      </div>
    `;
  }
  
  return investmentsData.map(investment => renderInvestment(investment)).join('');
}

// Render individual investment
function renderInvestment(investment) {
  const startDate = investment.start_date ? new Date(investment.start_date).toLocaleDateString('en-GB') : 'N/A';
  const maturityDate = investment.maturity_date ? new Date(investment.maturity_date).toLocaleDateString('en-GB') : 'N/A';
  const isMaturitySoon = investment.maturity_date ? isMaturityWithin30Days(investment.maturity_date) : false;
  const amount = investment.amount ? `₹${formatCurrency(investment.amount)}` : 'N/A';
  
  return `
    <div class="investment-item ${isMaturitySoon ? 'maturity-soon' : ''}" data-investment-id="${investment.id}">
      <div class="item-header">
        <div class="item-title">
          <h4>${investment.investment_type}</h4>
          <span class="investment-amount">${amount}</span>
        </div>
        <div class="item-actions">
          <button class="edit-btn" onclick="editInvestment(${investment.id})" title="Edit Investment">✏️</button>
          <button class="delete-btn" onclick="deleteInvestment(${investment.id})" title="Delete Investment">🗑️</button>
        </div>
      </div>
      <div class="item-details">
        <div class="detail-row">
          <span class="label">Start Date:</span>
          <span class="value">${startDate}</span>
        </div>
        <div class="detail-row">
          <span class="label">Maturity Date:</span>
          <span class="value ${isMaturitySoon ? 'maturity-soon' : ''}">${maturityDate}</span>
        </div>
      </div>
      ${isMaturitySoon ? '<div class="status-badge maturity-soon">Maturity Soon</div>' : ''}
    </div>
  `;
}

// Check if investment is maturing within 30 days
function isMaturityWithin30Days(maturityDate) {
  const maturity = new Date(maturityDate);
  const today = new Date();
  const diffTime = maturity - today;
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  return diffDays <= 30 && diffDays >= 0;
}

// Setup event listeners
function setupInvestmentEventListeners() {
  // Form submission
  const addInvestmentForm = document.getElementById('addInvestmentForm');
  if (addInvestmentForm) {
    addInvestmentForm.addEventListener('submit', handleAddInvestment);
  }
}

// Handle add investment form submission
async function handleAddInvestment(e) {
  e.preventDefault();
  
  const formData = {
    investment_type: document.getElementById('investmentType').value,
    amount: document.getElementById('amount').value,
    start_date: document.getElementById('startDate').value,
    maturity_date: document.getElementById('maturityDate').value,
    account_id: document.getElementById('linkedAccount').value || null
  };
  
  try {
    const response = await fetch('/api/investments', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(formData)
    });
    
    if (response.ok) {
      closeAddInvestmentModal();
      loadInvestmentsData(); // Reload data
      showNotification('Investment added successfully!', 'success');
    } else {
      throw new Error('Failed to add investment');
    }
  } catch (error) {
    console.error('Error adding investment:', error);
    showNotification('Failed to add investment. Please try again.', 'error');
  }
}

// Show add investment modal
function showAddInvestmentModal() {
  document.getElementById('addInvestmentModal').style.display = 'block';
}

// Close add investment modal
function closeAddInvestmentModal() {
  document.getElementById('addInvestmentModal').style.display = 'none';
  document.getElementById('addInvestmentForm').reset();
}

// Edit investment
function editInvestment(investmentId) {
  const investment = investmentsData.find(inv => inv.id === investmentId);
  if (!investment) return;
  
  // Pre-fill form with investment data
  document.getElementById('investmentType').value = investment.investment_type;
  document.getElementById('amount').value = investment.amount || '';
  document.getElementById('startDate').value = investment.start_date || '';
  document.getElementById('maturityDate').value = investment.maturity_date || '';
  document.getElementById('linkedAccount').value = investment.account_id || '';
  
  showAddInvestmentModal();
}

// Delete investment
async function deleteInvestment(investmentId) {
  if (!confirm('Are you sure you want to delete this investment?')) return;
  
  try {
    const response = await fetch(`/api/investments/${investmentId}`, {
      method: 'DELETE'
    });
    
    if (response.ok) {
      loadInvestmentsData(); // Reload data
      showNotification('Investment deleted successfully!', 'success');
    } else {
      throw new Error('Failed to delete investment');
    }
  } catch (error) {
    console.error('Error deleting investment:', error);
    showNotification('Failed to delete investment. Please try again.', 'error');
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
