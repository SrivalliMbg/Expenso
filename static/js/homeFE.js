// Home Frontend JavaScript with Chatbot Integration
document.addEventListener('DOMContentLoaded', function() {
    console.log('Home page loaded');
    
    // Initialize dashboard
    initDashboard();
    
    // Initialize chatbot
    initChatbot();
    
    // Load dashboard data
    loadDashboardData();
});

// Dashboard functionality
function initDashboard() {
    const user = JSON.parse(sessionStorage.getItem("user"));
    if (user) {
        // Update sidebar username
        const sidebarUsername = document.getElementById("sidebarUsername");
        if (sidebarUsername) {
            sidebarUsername.textContent = user.username;
        }
        
        // Load initial AI insights
        loadAIInsights();
        
        // Setup time selector functionality
        setupTimeSelector();
    } else {
        window.location.href = "/login_page";
    }
}

// Load all dashboard data from database
function loadDashboardData() {
    // Load financial summary
    loadFinancialSummary();
    
    // Load accounts summary
    loadAccountsSummary();
    
    // Load recent transactions
    loadRecentTransactions();
    
    // Load upcoming payments
    loadUpcomingPayments();
}

// Load financial summary data with time period selection
function loadFinancialSummary(period = 'this_month') {
    fetch(`/api/dashboard/summary/${period}`)
        .then(response => response.json())
        .then(data => {
            // Update inflow and outflow amounts
            const totalInflow = document.getElementById('totalInflow');
            const totalOutflow = document.getElementById('totalOutflow');
            const chartTotal = document.getElementById('chartTotal');
            
            if (totalInflow) {
                totalInflow.textContent = `₹${data.inflow.toLocaleString()}`;
            }
            if (totalOutflow) {
                totalOutflow.textContent = `₹${data.outflow.toLocaleString()}`;
            }
            if (chartTotal) {
                chartTotal.textContent = `₹${data.outflow.toLocaleString()}`;
            }
            
            // Update category list
            updateCategoryList(data.categories);
            
            // Update chart
            updateSpendingChart(data.categories);
            
            // Update time selector button text
            updateTimeSelectorText(period);
        })
        .catch(error => {
            console.error('Error loading financial summary:', error);
            // Show default values
            const totalInflow = document.getElementById('totalInflow');
            const totalOutflow = document.getElementById('totalOutflow');
            const chartTotal = document.getElementById('chartTotal');
            
            if (totalInflow) totalInflow.textContent = '₹0';
            if (totalOutflow) totalOutflow.textContent = '₹0';
            if (chartTotal) chartTotal.textContent = '₹0';
        });
}

// Update category list
function updateCategoryList(categories) {
    const categoryList = document.getElementById('categoryList');
    if (!categoryList) return;
    
    if (categories && categories.length > 0) {
        categoryList.innerHTML = categories.map(category => `
            <div class="category-item">
                <i class="fas ${getCategoryIcon(category.category)} category-icon"></i>
                <span class="category-name">${category.category || 'Uncategorized'}</span>
                <span class="category-amount">₹${parseFloat(category.total_amount).toLocaleString()}</span>
            </div>
        `).join('');
    } else {
        categoryList.innerHTML = `
            <div class="category-item">
                <i class="fas fa-info-circle category-icon"></i>
                <span class="category-name">No spending data</span>
                <span class="category-amount">₹0</span>
            </div>
        `;
    }
}

// Get category icon
function getCategoryIcon(category) {
    const icons = {
        'Food': 'fa-utensils',
        'Transport': 'fa-car',
        'Entertainment': 'fa-headphones',
        'Shopping': 'fa-shopping-cart',
        'Healthcare': 'fa-heartbeat',
        'Education': 'fa-graduation-cap',
        'Bills': 'fa-file-invoice',
        'Transfer': 'fa-exchange-alt',
        'Investment': 'fa-chart-line',
        'Insurance': 'fa-shield-alt',
        'default': 'fa-circle'
    };
    return icons[category] || icons.default;
}

// Update spending chart
function updateSpendingChart(categories) {
    const ctx = document.getElementById('spendingChart');
    if (!ctx) return;
    
    if (categories && categories.length > 0) {
        const chartData = {
            labels: categories.map(cat => cat.category || 'Uncategorized'),
            datasets: [{
                data: categories.map(cat => parseFloat(cat.total_amount)),
                backgroundColor: [
                    '#ff6b35',
                    '#2c2f48',
                    '#28a745',
                    '#dc3545',
                    '#007bff',
                    '#6c757d',
                    '#fd7e14',
                    '#20c997'
                ],
                borderWidth: 0,
                cutout: '60%'
            }]
        };
        
        const config = {
            type: 'doughnut',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${label}: ₹${value.toLocaleString()} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        };
        
        // Destroy existing chart if it exists
        if (window.spendingChart) {
            window.spendingChart.destroy();
        }
        
        window.spendingChart = new Chart(ctx, config);
    } else {
        // Show empty chart
        const chartData = {
            labels: ['No Data'],
            datasets: [{
                data: [1],
                backgroundColor: ['#e9ecef'],
                borderWidth: 0,
                cutout: '60%'
            }]
        };
        
        const config = {
            type: 'doughnut',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        enabled: false
                    }
                }
            }
        };
        
        if (window.spendingChart) {
            window.spendingChart.destroy();
        }
        
        window.spendingChart = new Chart(ctx, config);
    }
}

// Load recent transactions
function loadRecentTransactions() {
    fetch('/api/dashboard/transactions')
        .then(response => response.json())
        .then(data => {
            const transactionList = document.getElementById('transactionList');
            if (!transactionList) return;
            
            if (data.transactions && data.transactions.length > 0) {
                transactionList.innerHTML = data.transactions.map(transaction => `
                    <div class="transaction-item">
                        <div class="transaction-icon">
                            <i class="fas ${getTransactionIcon(transaction.category)}"></i>
                        </div>
                        <div class="transaction-details">
                            <div class="transaction-description">${transaction.description || 'Transaction'}</div>
                            <div class="transaction-date">${transaction.formatted_date}</div>
                        </div>
                        <div class="transaction-amount ${transaction.type.toLowerCase()}">
                            ₹${parseFloat(transaction.amount).toLocaleString()}
                            <i class="fas ${transaction.type.toLowerCase() === 'credit' ? 'fa-check' : 'fa-arrow-up'}"></i>
                        </div>
                    </div>
                `).join('');
            } else {
                transactionList.innerHTML = `
                    <div class="transaction-item">
                        <div class="transaction-icon">
                            <i class="fas fa-info-circle"></i>
                        </div>
                        <div class="transaction-details">
                            <div class="transaction-description">No transactions yet</div>
                            <div class="transaction-date">Start using your accounts</div>
                        </div>
                        <div class="transaction-amount">
                            ₹0
                        </div>
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error loading transactions:', error);
            const transactionList = document.getElementById('transactionList');
            if (transactionList) {
                transactionList.innerHTML = `
                    <div class="transaction-item">
                        <div class="transaction-icon">
                            <i class="fas fa-exclamation-triangle"></i>
                        </div>
                        <div class="transaction-details">
                            <div class="transaction-description">Error loading transactions</div>
                            <div class="transaction-date">Please try again later</div>
                        </div>
                        <div class="transaction-amount">
                            ₹0
                        </div>
                    </div>
                `;
            }
        });
}

// Load accounts summary
function loadAccountsSummary() {
    fetch('/api/dashboard/accounts')
        .then(response => response.json())
        .then(data => {
            // Update account balances
            const savingsBalance = document.getElementById('savingsBalance');
            const creditBalance = document.getElementById('creditBalance');
            const cardsAmount = document.getElementById('cardsAmount');
            const loansAmount = document.getElementById('loansAmount');
            
            if (savingsBalance) {
                savingsBalance.textContent = `₹${data.savings_balance.toLocaleString()}`;
            }
            if (creditBalance) {
                creditBalance.textContent = `₹${data.credit_balance.toLocaleString()}`;
            }
            if (cardsAmount) {
                cardsAmount.textContent = `₹${data.cards_amount.toLocaleString()}`;
            }
            if (loansAmount) {
                loansAmount.textContent = `₹${data.loans_amount.toLocaleString()}`;
            }
        })
        .catch(error => {
            console.error('Error loading accounts summary:', error);
            // Show default values
            const savingsBalance = document.getElementById('savingsBalance');
            const creditBalance = document.getElementById('creditBalance');
            const cardsAmount = document.getElementById('cardsAmount');
            const loansAmount = document.getElementById('loansAmount');
            
            if (savingsBalance) savingsBalance.textContent = '₹0';
            if (creditBalance) creditBalance.textContent = '₹0';
            if (cardsAmount) cardsAmount.textContent = '₹0';
            if (loansAmount) loansAmount.textContent = '₹0';
        });
}

// Load upcoming payments
function loadUpcomingPayments() {
    fetch('/api/dashboard/upcoming')
        .then(response => response.json())
        .then(data => {
            const upcomingCount = document.getElementById('upcomingCount');
            if (upcomingCount) {
                upcomingCount.textContent = data.upcoming_count || 0;
            }
        })
        .catch(error => {
            console.error('Error loading upcoming payments:', error);
            const upcomingCount = document.getElementById('upcomingCount');
            if (upcomingCount) {
                upcomingCount.textContent = '0';
            }
        });
}

// Get transaction icon based on category
function getTransactionIcon(category) {
    const icons = {
        'Transfer': 'fa-exchange-alt',
        'Investment': 'fa-chart-line',
        'Insurance': 'fa-shield-alt',
        'Shopping': 'fa-shopping-cart',
        'Food': 'fa-utensils',
        'Transport': 'fa-car',
        'Entertainment': 'fa-headphones',
        'Healthcare': 'fa-heartbeat',
        'Education': 'fa-graduation-cap',
        'Bills': 'fa-file-invoice',
        'default': 'fa-circle'
    };
    return icons[category] || icons.default;
}

// Load AI insights
function loadAIInsights() {
    const user = JSON.parse(sessionStorage.getItem("user"));
    const profileData = {
        "Name": user.username,
        "Status": user.status || "professional",
        "Profession": user.profession || "Not specified"
    };
    
    fetch('/api/insights', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            user_id: user.id || 'demo_user',
            user_mode: user.status || 'professional',
            profile_data: profileData,
            chat_history: []
        })
    })
    .then(response => response.json())
    .then(data => {
        const insightElement = document.getElementById('ai-insight');
        if (insightElement) {
            // Format the response with better styling
            const formattedResponse = data.response
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\n/g, '<br>')
                .replace(/•/g, '&bull;');
            insightElement.innerHTML = formattedResponse;
        }
    })
    .catch(error => {
        console.error('Error loading AI insights:', error);
        const insightElement = document.getElementById('ai-insight');
        if (insightElement) {
            insightElement.innerHTML = 'Your AI financial assistant is analyzing your spending patterns to provide personalized insights.<br><br><strong>Quick Tips:</strong><br>&bull; Track your daily expenses<br>&bull; Set a monthly budget<br>&bull; Save at least 20% of your income<br>&bull; Review your spending weekly';
        }
    });
}

// Chatbot functionality
function initChatbot() {
    const chatbotContainer = document.getElementById('floating-chatbot-container');
    if (!chatbotContainer) return;
    
    chatbotContainer.innerHTML = `
        <div class="chatbot-widget" id="chatbot-widget">
            <div class="chatbot-header" onclick="expandChatbot()">
                <h4>🤖 AI Financial Assistant</h4>
                <div style="position: relative;">
                    <button class="chatbot-toggle" onclick="toggleChatbot(event)" id="chatbot-toggle-btn">💬</button>
                    <div class="chatbot-notification" id="chatbot-notification" style="display: none;">!</div>
                </div>
            </div>
            <div class="chatbot-body" id="chatbot-body" style="display: none;">
                <div class="chat-messages" id="chat-messages">
                    <div class="message bot-message">
                        <div class="message-content">
                            <strong>Hello! I'm your AI financial assistant.</strong><br><br>
                            I can help you with:<br>
                            • Budget analysis and spending insights<br>
                            • Savings tips and strategies<br>
                            • Investment recommendations<br>
                            • Stock suggestions under specific prices<br>
                            • Debt management advice<br><br>
                            What would you like to know about your finances?
                        </div>
                    </div>
                </div>
                <div class="chat-input-container">
                    <input type="text" id="chat-input" placeholder="Chat with Expenso..." onkeypress="handleChatKeyPress(event)">
                    <button onclick="sendMessage()" class="send-btn">Send</button>
                </div>
                <div class="quick-actions">
                    <button onclick="askQuickQuestion('Analyze my budget')" class="quick-btn">💰 Budget Analysis</button>
                    <button onclick="askQuickQuestion('How can I improve my savings?')" class="quick-btn">💡 Savings Tips</button>
                    <button onclick="askQuickQuestion('Show me stocks under 500')" class="quick-btn">📈 Stock Ideas</button>
                    <button onclick="askQuickQuestion('Investment advice')" class="quick-btn">📊 Investments</button>
                </div>
            </div>
        </div>
    `;
    
    // Initialize chatbot in minimized state
    const chatbotWidget = document.getElementById('chatbot-widget');
    const chatbotBody = document.getElementById('chatbot-body');
    if (chatbotWidget && chatbotBody) {
        chatbotWidget.classList.add('minimized');
        chatbotBody.style.display = 'none';
        
        // Show notification after 3 seconds to draw attention
        setTimeout(() => {
            showChatbotNotification();
        }, 3000);
    }
}

// Show notification badge
function showChatbotNotification() {
    const notification = document.getElementById('chatbot-notification');
    if (notification) {
        notification.style.display = 'flex';
    }
}

// Hide notification badge
function hideChatbotNotification() {
    const notification = document.getElementById('chatbot-notification');
    if (notification) {
        notification.style.display = 'none';
    }
}

// Expand chatbot when header is clicked
function expandChatbot() {
    const chatbotBody = document.getElementById('chatbot-body');
    const chatbotWidget = document.getElementById('chatbot-widget');
    
    if (chatbotBody.style.display === 'none') {
        chatbotBody.style.display = 'block';
        chatbotWidget.classList.remove('minimized');
        hideChatbotNotification();
        document.getElementById('chat-input').focus();
    }
}

// Toggle chatbot visibility
function toggleChatbot(event) {
    if (event) {
        event.stopPropagation();
    }
    
    const chatbotBody = document.getElementById('chatbot-body');
    const toggleBtn = document.getElementById('chatbot-toggle-btn');
    const chatbotWidget = document.getElementById('chatbot-widget');
    
    if (chatbotBody.style.display === 'none') {
        chatbotBody.style.display = 'block';
        toggleBtn.textContent = '✕';
        chatbotWidget.classList.remove('minimized');
        hideChatbotNotification();
        document.getElementById('chat-input').focus();
    } else {
        chatbotBody.style.display = 'none';
        toggleBtn.textContent = '💬';
        chatbotWidget.classList.add('minimized');
    }
}

// Handle Enter key in chat input
function handleChatKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

// Send message to chatbot
function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Add user message to chat
    addMessage(message, 'user');
    input.value = '';
    
    // Show typing indicator
    addTypingIndicator();
    
    // Send to API
    const user = JSON.parse(sessionStorage.getItem("user"));
    const profileData = {
        "Name": user.username,
        "Status": user.status || "professional",
        "Profession": user.profession || "Not specified"
    };
    
    fetch('/api/chatbot', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            user_id: user.id || 'demo_user',
            message: message,
            user_mode: user.status || 'professional',
            profile_data: profileData,
            chat_history: getChatHistory()
        })
    })
    .then(response => response.json())
    .then(data => {
        removeTypingIndicator();
        addMessage(data.response, 'bot');
    })
    .catch(error => {
        console.error('Error sending message:', error);
        removeTypingIndicator();
        addMessage('Sorry, I\'m having trouble connecting right now. Please try again.', 'bot');
    });
}

// Add message to chat
function addMessage(text, sender) {
    const messagesContainer = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // Format the message with better styling
    let formattedText = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>')
        .replace(/•/g, '&bull;')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>'); // Double check for bold formatting
    
    contentDiv.innerHTML = formattedText;
    
    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    // Store in chat history
    addToChatHistory(sender, text);
}

// Add typing indicator
function addTypingIndicator() {
    const messagesContainer = document.getElementById('chat-messages');
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message bot-message typing-indicator';
    typingDiv.id = 'typing-indicator';
    typingDiv.innerHTML = '<div class="message-content">🤖 AI is thinking...</div>';
    messagesContainer.appendChild(typingDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Remove typing indicator
function removeTypingIndicator() {
    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

// Quick question function
function askQuickQuestion(question) {
    const input = document.getElementById('chat-input');
    input.value = question;
    sendMessage();
}

// Chat history management
function addToChatHistory(sender, text) {
    let history = JSON.parse(sessionStorage.getItem('chatHistory') || '[]');
    history.push({
        sender: sender,
        text: text,
        timestamp: new Date().toISOString()
    });
    
    // Keep only last 20 messages
    if (history.length > 20) {
        history = history.slice(-20);
    }
    
    sessionStorage.setItem('chatHistory', JSON.stringify(history));
}

function getChatHistory() {
    return JSON.parse(sessionStorage.getItem('chatHistory') || '[]');
}

// Time selector functionality
function setupTimeSelector() {
    const timeBtn = document.querySelector('.time-btn');
    if (timeBtn) {
        timeBtn.addEventListener('click', function() {
            showTimeSelector();
        });
    }
}

function showTimeSelector() {
    const timeSelector = document.createElement('div');
    timeSelector.className = 'time-selector-dropdown';
    timeSelector.innerHTML = `
        <div class="time-option" onclick="selectTimePeriod('this_month')">This Month</div>
        <div class="time-option" onclick="selectTimePeriod('last_month')">Last Month</div>
        <div class="time-option" onclick="selectTimePeriod('this_year')">This Year</div>
        <div class="time-option" onclick="selectTimePeriod('all_time')">All Time</div>
    `;
    
    // Remove existing dropdown if any
    const existing = document.querySelector('.time-selector-dropdown');
    if (existing) {
        existing.remove();
    }
    
    // Add dropdown
    const timeBtn = document.querySelector('.time-btn');
    timeBtn.parentNode.appendChild(timeSelector);
    
    // Close dropdown when clicking outside
    setTimeout(() => {
        document.addEventListener('click', function closeDropdown(e) {
            if (!timeSelector.contains(e.target) && !timeBtn.contains(e.target)) {
                timeSelector.remove();
                document.removeEventListener('click', closeDropdown);
            }
        });
    }, 100);
}

function selectTimePeriod(period) {
    loadFinancialSummary(period);
    
    // Remove dropdown
    const dropdown = document.querySelector('.time-selector-dropdown');
    if (dropdown) {
        dropdown.remove();
    }
}

function updateTimeSelectorText(period) {
    const timeBtn = document.querySelector('.time-btn');
    if (timeBtn) {
        const periodTexts = {
            'this_month': 'This Month',
            'last_month': 'Last Month', 
            'this_year': 'This Year',
            'all_time': 'All Time'
        };
        timeBtn.innerHTML = `${periodTexts[period]} <i class="fas fa-chevron-down"></i>`;
    }
}

// Logout confirmation
function confirmLogout() {
    return confirm("Are you sure you want to logout?");
}
