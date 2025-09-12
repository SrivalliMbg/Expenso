function loadRecentTransactions() {
  // Empty transaction data - replace with actual API call
  const mockTransactions = [];

  const root = document.getElementById('root');
  if (!root) return;
  
  root.innerHTML = `
    <div class="transactions-container">
      <div class="page-header">
        <h1>Recent Transactions</h1>
        <p>Your latest financial activities</p>
      </div>
      
      <div class="transactions-overview">
        <div class="overview-card">
          <h3>Total Transactions</h3>
          <p class="transaction-count">${mockTransactions.length}</p>
        </div>
        <div class="overview-card">
          <h3>This Month</h3>
          <p class="monthly-total">₹${mockTransactions.filter(t => t.type === 'debit').reduce((sum, t) => sum + t.amount, 0).toLocaleString()}</p>
        </div>
      </div>
      
      <div class="transactions-section">
        <div class="section-header">
          <h2>Transaction History</h2>
        </div>
        
                 <div class="transactions-list">
           ${mockTransactions.length > 0 ? mockTransactions.map(transaction => `
             <div class="transaction-card ${transaction.type}">
               <div class="transaction-icon ${transaction.category}"></div>
               <div class="transaction-details">
                 <h4>${transaction.description}</h4>
                 <p class="transaction-meta">
                   <span class="transaction-date">${new Date(transaction.date).toLocaleDateString()}</span>
                   <span class="transaction-account">${transaction.account}</span>
                 </p>
               </div>
               <div class="transaction-amount ${transaction.type}">
                 <span class="amount-sign">${transaction.type === 'credit' ? '+' : transaction.type === 'debit' ? '-' : '→'}</span>
                 ₹${transaction.amount.toLocaleString()}
               </div>
             </div>
           `).join('') : `
             <div class="empty-state">
               <div class="empty-icon">📊</div>
               <h3>No Transactions Yet</h3>
               <p>Your transaction history will appear here once you start using your accounts</p>
             </div>
           `}
         </div>
      </div>
    </div>
  `;
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
  console.log('Recent transactions page loaded');
  loadRecentTransactions();
});
