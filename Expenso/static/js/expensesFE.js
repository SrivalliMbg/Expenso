function loadExpenses() {
  // Empty expense data - replace with actual API call
  const mockExpenses = [];

  // Group expenses by category
  const expensesByCategory = mockExpenses.reduce((acc, expense) => {
    if (!acc[expense.category]) {
      acc[expense.category] = [];
    }
    acc[expense.category].push(expense);
    return acc;
  }, {});

  // Calculate totals
  const totalExpenses = mockExpenses.reduce((sum, expense) => sum + expense.amount, 0);
  const categoryTotals = {};
  Object.keys(expensesByCategory).forEach(category => {
    categoryTotals[category] = expensesByCategory[category].reduce((sum, expense) => sum + expense.amount, 0);
  });

  const root = document.getElementById('root');
  if (!root) return;
  
  root.innerHTML = `
    <div class="expenses-container">
      <div class="page-header">
        <h1>My Expenses</h1>
        <p>Track your spending by category</p>
      </div>
      
      <div class="expenses-overview">
        <div class="overview-card">
          <h3>Total Expenses</h3>
          <p class="total-amount">₹${totalExpenses.toLocaleString()}</p>
        </div>
        <div class="overview-card">
          <h3>This Month</h3>
          <p class="monthly-expenses">₹${totalExpenses.toLocaleString()}</p>
        </div>
        <div class="overview-card">
          <h3>Categories</h3>
          <p class="category-count">${Object.keys(expensesByCategory).length}</p>
        </div>
      </div>
      
      <div class="expenses-section">
        <div class="section-header">
          <h2>Expenses by Category</h2>
        </div>
        
                 <div class="categories-grid">
           ${Object.keys(expensesByCategory).length > 0 ? Object.keys(expensesByCategory).map(category => `
             <div class="category-card">
               <div class="category-header">
                 <div class="category-icon ${category}"></div>
                 <div class="category-info">
                   <h3>${category.charAt(0).toUpperCase() + category.slice(1)}</h3>
                   <p class="category-total">₹${categoryTotals[category].toLocaleString()}</p>
                 </div>
               </div>
               <div class="category-expenses">
                 ${expensesByCategory[category].map(expense => `
                   <div class="expense-item">
                     <div class="expense-details">
                       <h4>${expense.description}</h4>
                       <p class="expense-date">${new Date(expense.date).toLocaleDateString()}</p>
                     </div>
                     <div class="expense-amount">₹${expense.amount.toLocaleString()}</div>
                   </div>
                 `).join('')}
               </div>
             </div>
           `).join('') : `
             <div class="empty-state">
               <div class="empty-icon">💰</div>
               <h3>No Expenses Yet</h3>
               <p>Your expense categories will appear here once you start tracking your spending</p>
             </div>
           `}
         </div>
      </div>
    </div>
  `;
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
  console.log('Expenses page loaded');
  loadExpenses();
});
