// Enhanced Cards Frontend with Database Integration

// Global variables
let cardsData = [];
let accountsData = [];

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
  console.log('Cards page loaded');
  loadCardsData();
});

// Load cards data from database
async function loadCardsData() {
  try {
    // Load cards from database
    const cardsResponse = await fetch('/api/cards');
    const cards = await cardsResponse.json();
    cardsData = cards.cards || [];
    
    // Load accounts for linking
    const accountsResponse = await fetch('/api/dashboard/accounts');
    const accounts = await accountsResponse.json();
    accountsData = accounts.accounts || [];
    
    renderCardsPage();
  } catch (error) {
    console.error('Error loading cards data:', error);
    renderCardsPage(); // Render with empty data
  }
}

// Render the main cards page
function renderCardsPage() {
  const root = document.getElementById('root');
  if (!root) return;
  
  // Calculate summary statistics
  const totalCards = cardsData.length;
  const totalLimit = cardsData.reduce((sum, card) => sum + (card.limit_amount || 0), 0);
  const debitCards = cardsData.filter(card => card.card_type === 'Debit').length;
  const creditCards = cardsData.filter(card => card.card_type === 'Credit').length;
  
  root.innerHTML = `
    <div class="cards-container">
      <div class="page-header">
        <h1>💳 My Cards</h1>
        <p>Manage your debit and credit cards</p>
      </div>
      
      <div class="cards-overview">
        <div class="overview-card">
          <h3>Total Cards</h3>
          <p class="card-count">${totalCards}</p>
        </div>
        <div class="overview-card">
          <h3>Credit Limit</h3>
          <p class="limit-amount">₹${totalLimit.toLocaleString()}</p>
        </div>
        <div class="overview-card">
        <h3>Debit Cards</h3>
          <p class="debit-count">${debitCards}</p>
        </div>
        <div class="overview-card">
          <h3>Credit Cards</h3>
          <p class="credit-count">${creditCards}</p>
        </div>
      </div>
      
      <div class="cards-section">
        <div class="section-header">
          <h2>My Cards</h2>
          <button class="add-btn" onclick="showAddCardModal()">+ Add Card</button>
        </div>
        
        <div class="cards-grid">
          ${renderCardsGrid()}
    </div>
      </div>

    <!-- Add Card Modal -->
    <div id="addCardModal" class="modal">
      <div class="modal-content">
        <div class="modal-header">
          <h2>Add New Card</h2>
          <span class="close" onclick="closeAddCardModal()">&times;</span>
        </div>
        <div class="modal-body">
          <form id="addCardForm">
            <div class="form-group">
              <label for="cardType">Card Type</label>
              <select id="cardType" required>
                <option value="">Select Card Type</option>
                <option value="Debit">Debit Card</option>
                <option value="Credit">Credit Card</option>
                <option value="Prepaid">Prepaid Card</option>
              </select>
            </div>
            <div class="form-group">
              <label for="cardNumber">Card Number</label>
              <input type="text" id="cardNumber" placeholder="1234 5678 9012 3456" maxlength="19" required>
            </div>
            <div class="form-group">
              <label for="expiryDate">Expiry Date</label>
              <input type="text" id="expiryDate" placeholder="MM/YY" maxlength="5" required>
            </div>
            <div class="form-group">
              <label for="cvv">CVV</label>
              <input type="text" id="cvv" placeholder="123" maxlength="3" required>
            </div>
            <div class="form-group" id="limitGroup" style="display: none;">
              <label for="limitAmount">Credit Limit (₹)</label>
              <input type="number" id="limitAmount" placeholder="50000" min="0">
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
              <button type="button" class="btn-secondary" onclick="closeAddCardModal()">Cancel</button>
              <button type="submit" class="btn-primary">Add Card</button>
            </div>
          </form>
    </div>
      </div>
    </div>
  `;

  // Add event listeners
  setupCardEventListeners();
}

// Render cards grid
function renderCardsGrid() {
  if (cardsData.length === 0) {
    return `
      <div class="empty-state">
        <div class="empty-icon">💳</div>
        <h3>No Cards Added Yet</h3>
        <p>Add your first card to get started with managing your finances</p>
        <button class="btn-primary" onclick="showAddCardModal()">Add Your First Card</button>
      </div>
    `;
  }
  
  return cardsData.map(card => renderCard(card)).join('');
}

// Render individual card
function renderCard(card) {
  const expiryDate = card.expiry_date ? new Date(card.expiry_date).toLocaleDateString('en-GB') : 'N/A';
  const isExpired = card.expiry_date ? new Date(card.expiry_date) < new Date() : false;
  const limitAmount = card.limit_amount ? `₹${card.limit_amount.toLocaleString()}` : 'N/A';
  
  return `
    <div class="card-item ${isExpired ? 'expired' : ''}" data-card-id="${card.id}">
      <div class="item-header">
        <div class="item-title">
          <h4>${card.card_type} Card</h4>
          <span class="card-number">${formatCardNumber(card.card_number)}</span>
        </div>
        <div class="item-actions">
          <button class="edit-btn" onclick="editCard(${card.id})" title="Edit Card">✏️</button>
          <button class="delete-btn" onclick="deleteCard(${card.id})" title="Delete Card">🗑️</button>
        </div>
      </div>
      <div class="item-details">
        <div class="detail-row">
          <span class="label">Expiry Date:</span>
          <span class="value ${isExpired ? 'expired' : ''}">${expiryDate}</span>
        </div>
        <div class="detail-row">
          <span class="label">CVV:</span>
          <span class="value">***</span>
        </div>
        ${card.card_type === 'Credit' && card.limit_amount ? `
          <div class="detail-row">
            <span class="label">Credit Limit:</span>
            <span class="value">${limitAmount}</span>
          </div>
        ` : ''}
      </div>
      ${isExpired ? '<div class="status-badge expired">Expired</div>' : ''}
    </div>
  `;
}

// Format card number for display
function formatCardNumber(number) {
  if (!number) return '**** **** **** ****';
  const cleaned = number.replace(/\s+/g, '');
  if (cleaned.length < 16) return cleaned;
  return cleaned.replace(/(\d{4})(\d{4})(\d{4})(\d{4})/, "$1 **** **** $4");
}

// Setup event listeners
function setupCardEventListeners() {
  // Card number formatting
  const cardNumberInput = document.getElementById('cardNumber');
  if (cardNumberInput) {
    cardNumberInput.addEventListener('input', function(e) {
      let value = e.target.value.replace(/\s+/g, '').replace(/[^0-9]/gi, '');
      let formattedValue = value.match(/.{1,4}/g)?.join(' ') || value;
      e.target.value = formattedValue;
    });
  }
  
  // Expiry date formatting
  const expiryInput = document.getElementById('expiryDate');
  if (expiryInput) {
    expiryInput.addEventListener('input', function(e) {
      let value = e.target.value.replace(/\D/g, '');
      if (value.length >= 2) {
        value = value.substring(0, 2) + '/' + value.substring(2, 4);
      }
      e.target.value = value;
    });
  }
  
  // CVV formatting
  const cvvInput = document.getElementById('cvv');
  if (cvvInput) {
    cvvInput.addEventListener('input', function(e) {
      e.target.value = e.target.value.replace(/[^0-9]/g, '');
    });
  }
  
  // Card type change - show/hide credit limit field
  const cardTypeSelect = document.getElementById('cardType');
  if (cardTypeSelect) {
    cardTypeSelect.addEventListener('change', function(e) {
      const limitGroup = document.getElementById('limitGroup');
      const limitInput = document.getElementById('limitAmount');
      
      if (e.target.value === 'Credit') {
        limitGroup.style.display = 'block';
        limitInput.required = true;
        limitInput.placeholder = '50000';
      } else {
        limitGroup.style.display = 'none';
        limitInput.required = false;
        limitInput.value = '';
        limitInput.placeholder = '0';
      }
    });
  }
  
  // Form submission
  const addCardForm = document.getElementById('addCardForm');
  if (addCardForm) {
    addCardForm.addEventListener('submit', handleAddCard);
  }
}

// Handle add card form submission
async function handleAddCard(e) {
  e.preventDefault();
  
  const formData = {
    card_type: document.getElementById('cardType').value,
    card_number: document.getElementById('cardNumber').value.replace(/\s/g, ''),
    expiry_date: document.getElementById('expiryDate').value,
    cvv: document.getElementById('cvv').value,
    limit_amount: document.getElementById('limitAmount').value || 0,
    account_id: document.getElementById('linkedAccount').value || null
  };
  
  try {
    const response = await fetch('/api/cards', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(formData)
    });
    
    if (response.ok) {
      closeAddCardModal();
      loadCardsData(); // Reload data
      showNotification('Card added successfully!', 'success');
    } else {
      throw new Error('Failed to add card');
    }
  } catch (error) {
    console.error('Error adding card:', error);
    showNotification('Failed to add card. Please try again.', 'error');
  }
}

// Show add card modal
function showAddCardModal() {
  document.getElementById('addCardModal').style.display = 'block';
}

// Close add card modal
function closeAddCardModal() {
  document.getElementById('addCardModal').style.display = 'none';
  document.getElementById('addCardForm').reset();
}

// Edit card
function editCard(cardId) {
  const card = cardsData.find(c => c.id === cardId);
  if (!card) return;
  
  // Pre-fill form with card data
  document.getElementById('cardType').value = card.card_type;
  document.getElementById('cardNumber').value = formatCardNumber(card.card_number);
  document.getElementById('expiryDate').value = card.expiry_date ? new Date(card.expiry_date).toLocaleDateString('en-GB') : '';
  document.getElementById('limitAmount').value = card.limit_amount || '';
  document.getElementById('linkedAccount').value = card.account_id || '';
  
  showAddCardModal();
}

// Delete card
async function deleteCard(cardId) {
  if (!confirm('Are you sure you want to delete this card?')) return;
  
  try {
    const response = await fetch(`/api/cards/${cardId}`, {
      method: 'DELETE'
    });
    
    if (response.ok) {
      loadCardsData(); // Reload data
      showNotification('Card deleted successfully!', 'success');
    } else {
      throw new Error('Failed to delete card');
    }
  } catch (error) {
    console.error('Error deleting card:', error);
    showNotification('Failed to delete card. Please try again.', 'error');
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
