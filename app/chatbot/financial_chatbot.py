"""
Financial Chatbot for Expenso Application
Integrated with the main Flask app and database
"""

from flask import Blueprint, request, jsonify, current_app, session
import pandas as pd
import numpy as np
import yfinance as yf
import re
import os
from datetime import datetime, timedelta
import json

# Create blueprint
chatbot_bp = Blueprint('chatbot', __name__)

# Financial categories and their icons
FINANCIAL_CATEGORIES = {
    'Food': {'icon': 'fa-utensils', 'color': '#ff6b35'},
    'Transport': {'icon': 'fa-car', 'color': '#2c2f48'},
    'Entertainment': {'icon': 'fa-headphones', 'color': '#28a745'},
    'Shopping': {'icon': 'fa-shopping-cart', 'color': '#dc3545'},
    'Healthcare': {'icon': 'fa-heartbeat', 'color': '#007bff'},
    'Education': {'icon': 'fa-graduation-cap', 'color': '#6c757d'},
    'Bills': {'icon': 'fa-file-invoice', 'color': '#fd7e14'},
    'Transfer': {'icon': 'fa-exchange-alt', 'color': '#20c997'},
    'Investment': {'icon': 'fa-chart-line', 'color': '#17a2b8'},
    'Insurance': {'icon': 'fa-shield-alt', 'color': '#6f42c1'},
    'default': {'icon': 'fa-circle', 'color': '#6c757d'}
}

# Indian stock tickers for recommendations
INDIAN_STOCKS = [
    "YESBANK.NS", "SUZLON.NS", "IDEA.NS", "NHPC.NS", "IOC.NS",
    "PNB.NS", "SOUTHBANK.NS", "UCOBANK.NS", "SAIL.NS", "GAIL.NS",
    "ONGC.NS", "COALINDIA.NS", "BHEL.NS", "BANKBARODA.NS", "ZEEL.NS",
    "CANBK.NS", "UNIONBANK.NS", "IDFCFIRSTB.NS", "NLCINDIA.NS", "NBCC.NS",
    "TATASTEEL.NS", "HINDALCO.NS", "JSWSTEEL.NS", "ADANIPORTS.NS", "POWERGRID.NS"
]

class FinancialChatbot:
    """Main chatbot class for financial assistance"""
    
    def __init__(self):
        self.user_context = {}
        self.chat_history = []
    
    def get_user_financial_data(self, user_id):
        """Get user's comprehensive financial data from all database tables"""
        if not current_app.mysql:
            return self._get_mock_financial_data()
        
        try:
            cursor = current_app.mysql.cursor(dictionary=True)
            
            # Get all accounts data
            cursor.execute("""
                SELECT id, type, bank, branch, acc_no, balance, created_at 
                FROM accounts
            """)
            accounts = cursor.fetchall()
            
            # Get all transactions data
            cursor.execute("""
                SELECT id, account_id, title, amount, type, date, created_at
                FROM transactions
                ORDER BY date DESC
            """)
            transactions = cursor.fetchall()
            
            # Get all expenses data
            cursor.execute("""
                SELECT id, account_id, title, amount, category, date, created_at
                FROM expenses
                ORDER BY date DESC
            """)
            expenses = cursor.fetchall()
            
            # Get all cards data
            cursor.execute("""
                SELECT id, account_id, card_type, card_number, expiry_date, cvv, limit_amount, created_at
                FROM cards
            """)
            cards = cursor.fetchall()
            
            # Get all investments data
            cursor.execute("""
                SELECT id, account_id, investment_type, amount, start_date, maturity_date, created_at
                FROM investments
            """)
            investments = cursor.fetchall()
            
            # Get all loans data
            cursor.execute("""
                SELECT id, account_id, description, amount, interest_rate, due_date, created_at
                FROM loans
            """)
            loans = cursor.fetchall()
            
            # Get all insurance data
            cursor.execute("""
                SELECT id, account_id, policy_name, policy_type, premium_amount, coverage_amount, next_due_date, created_at
                FROM insurance
            """)
            insurance = cursor.fetchall()
            
            # Get all borrowings data
            cursor.execute("""
                SELECT id, account_id, borrower_name, amount, borrowed_date, expected_return_date, status, created_at
                FROM borrowings
            """)
            borrowings = cursor.fetchall()
            
            # Calculate spending by category from expenses
            cursor.execute("""
                SELECT category, SUM(amount) as total_amount, COUNT(*) as count
                FROM expenses
                WHERE MONTH(date) = MONTH(CURDATE())
                AND YEAR(date) = YEAR(CURDATE())
                GROUP BY category
                ORDER BY total_amount DESC
            """)
            spending_by_category = cursor.fetchall()
            
            # Calculate monthly transaction summary
            cursor.execute("""
                SELECT 
                    type,
                    SUM(amount) as total_amount,
                    COUNT(*) as count
                FROM transactions
                WHERE MONTH(date) = MONTH(CURDATE())
                AND YEAR(date) = YEAR(CURDATE())
                GROUP BY type
            """)
            monthly_transaction_summary = cursor.fetchall()
            
            cursor.close()
            
            return {
                'accounts': accounts,
                'transactions': transactions,
                'expenses': expenses,
                'cards': cards,
                'investments': investments,
                'loans': loans,
                'insurance': insurance,
                'borrowings': borrowings,
                'spending_by_category': spending_by_category,
                'monthly_transaction_summary': monthly_transaction_summary,
                'user_id': user_id
            }
        except Exception as e:
            print(f"Error fetching financial data: {e}")
            return self._get_mock_financial_data()
    
    def _get_mock_financial_data(self):
        """Return mock data when database is not available"""
        return {
            'accounts': [
                {'account_type': 'Savings', 'balance': 50000},
                {'account_type': 'Credit', 'balance': -15000}
            ],
            'transactions': [
                {'description': 'Grocery Shopping', 'amount': 2500, 'type': 'Debit', 'category': 'Food', 'date': datetime.now()},
                {'description': 'Salary Credit', 'amount': 75000, 'type': 'Credit', 'category': 'Income', 'date': datetime.now()},
                {'description': 'Uber Ride', 'amount': 350, 'type': 'Debit', 'category': 'Transport', 'date': datetime.now()},
                {'description': 'Netflix Subscription', 'amount': 499, 'type': 'Debit', 'category': 'Entertainment', 'date': datetime.now()}
            ],
            'spending_by_category': [
                {'category': 'Shopping', 'total_amount': 12000, 'count': 8},
                {'category': 'Food', 'total_amount': 8000, 'count': 12},
                {'category': 'Transport', 'total_amount': 6000, 'count': 15},
                {'category': 'Entertainment', 'total_amount': 4000, 'count': 6},
                {'category': 'Bills', 'total_amount': 10000, 'count': 4}
            ],
            'user_id': 'demo_user'
        }
    
    def analyze_spending_patterns(self, financial_data):
        """Analyze user's spending patterns from real database data"""
        spending_data = financial_data.get('spending_by_category', [])
        expenses = financial_data.get('expenses', [])
        transactions = financial_data.get('transactions', [])
        
        if not spending_data and not expenses:
            return "No spending data available for analysis. Start adding expenses to get insights!"
        
        # Calculate total spending from expenses
        total_spent = sum(item['total_amount'] for item in spending_data) if spending_data else 0
        
        # Get recent expenses for detailed analysis
        recent_expenses = expenses[:10] if expenses else []
        
        analysis = f"""**📊 Spending Analysis Summary:**

💰 **Monthly Spending:** ₹{total_spent:,}
📈 **Total Expenses:** {len(expenses)} transactions
💳 **Total Transactions:** {len(transactions)} transactions

"""
        
        if spending_data:
            top_category = max(spending_data, key=lambda x: x['total_amount'])
            analysis += f"🏆 **Top Spending Category:** {top_category['category']} (₹{top_category['total_amount']:,})\n\n"
            
            analysis += "**📋 Category Breakdown:**\n"
            for item in spending_data[:5]:
                percentage = (item['total_amount'] / total_spent) * 100 if total_spent > 0 else 0
                analysis += f"• {item['category']}: ₹{item['total_amount']:,} ({percentage:.1f}%)\n"
        
        if recent_expenses:
            analysis += f"\n**📝 Recent Expenses:**\n"
            for i, expense in enumerate(recent_expenses[:5], 1):
                analysis += f"{i}. {expense['title']} - ₹{expense['amount']:,} ({expense.get('category', 'Other')})\n"
        
        return analysis.strip()
    
    def get_savings_recommendations(self, financial_data):
        """Provide savings recommendations based on spending patterns"""
        spending_data = financial_data.get('spending_by_category', [])
        accounts = financial_data.get('accounts', [])
        
        # Calculate total income and expenses
        total_income = 0
        total_expenses = 0
        
        for account in accounts:
            if account['account_type'] == 'Savings':
                total_income += account['balance']
        
        for item in spending_data:
            total_expenses += item['total_amount']
        
        savings_rate = ((total_income - total_expenses) / total_income * 100) if total_income > 0 else 0
        
        recommendations = f"""
**Savings Analysis:**
• Current Savings Rate: {savings_rate:.1f}%
• Monthly Income: ₹{total_income:,}
• Monthly Expenses: ₹{total_expenses:,}
• Net Savings: ₹{total_income - total_expenses:,}

**Recommendations:**
"""
        
        if savings_rate < 20:
            recommendations += """
1. **Increase Savings Rate** - Aim for at least 20% of income
2. **Track Daily Expenses** - Use our expense tracker
3. **Set Up Automatic Transfers** - Automate savings
4. **Reduce Discretionary Spending** - Cut back on entertainment/shopping
5. **Create Emergency Fund** - Save 3-6 months of expenses
"""
        else:
            recommendations += """
1. **Great Job!** - You're saving well
2. **Consider Investments** - Put excess savings to work
3. **Diversify Portfolio** - Mix of equity, debt, and gold
4. **Tax-Saving Investments** - ELSS funds for tax benefits
5. **Long-term Goals** - Plan for retirement and major purchases
"""
        
        return recommendations.strip()
    
    def get_investment_advice(self, user_mode='professional'):
        """Provide investment advice based on user profile"""
        if user_mode == 'student':
            return """
**Investment Advice for Students:**

1. **Start Small** - Begin with ₹500-1000 per month
2. **Emergency Fund First** - Save ₹10,000-25,000
3. **SIP in Index Funds** - Low-cost, diversified approach
4. **Avoid High-Risk Investments** - Focus on learning
5. **Use Apps** - Zerodha, Groww for easy investing

**Recommended Options:**
• Nifty 50 Index Fund (SIP)
• Liquid Funds for emergency fund
• PPF for long-term savings
• ELSS for tax benefits (if earning)
"""
        else:
            return """
**Investment Advice for Professionals:**

1. **Asset Allocation** - 60% Equity, 30% Debt, 10% Gold
2. **Emergency Fund** - 6 months of expenses
3. **Tax-Saving Investments** - ELSS, PPF, NPS
4. **Diversification** - Don't put all eggs in one basket
5. **Regular Review** - Rebalance portfolio quarterly

**Recommended Portfolio:**
• Large Cap Funds (40%)
• Mid Cap Funds (20%)
• Debt Funds (30%)
• Gold ETF (10%)
• ELSS for tax benefits
"""
    
    def get_stock_recommendations(self, price_limit=500, count=10):
        """Get stock recommendations under specified price"""
        recommendations = []
        
        for ticker in INDIAN_STOCKS[:count*2]:  # Check more stocks to find enough under limit
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="1d")
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
                    if current_price <= price_limit:
                        info = stock.info
                        recommendations.append({
                            'ticker': ticker,
                            'price': round(current_price, 2),
                            'name': info.get('longName', ticker),
                            'sector': info.get('sector', 'Unknown')
                        })
                        if len(recommendations) >= count:
                            break
            except Exception as e:
                continue
        
        if not recommendations:
            return f"Sorry, I couldn't find any stocks under ₹{price_limit} at the moment."
        
        response = f"**Stocks under ₹{price_limit}:**\n\n"
        for i, stock in enumerate(recommendations, 1):
            response += f"{i}. **{stock['ticker']}** - ₹{stock['price']}\n"
            response += f"   {stock['name']} ({stock['sector']})\n\n"
        
        return response.strip()
    
    def get_recent_transactions_analysis(self, financial_data):
        """Analyze recent transactions"""
        transactions = financial_data.get('transactions', [])
        if not transactions:
            return "No recent transactions found. Start by adding some transactions to get insights!"
        
        # Analyze recent transactions
        total_credits = sum(t['amount'] for t in transactions if t['type'] == 'Credit')
        total_debits = sum(t['amount'] for t in transactions if t['type'] == 'Debit')
        
        # Get top spending categories
        debit_transactions = [t for t in transactions if t['type'] == 'Debit']
        category_spending = {}
        for t in debit_transactions:
            category = t.get('category', 'Other')
            category_spending[category] = category_spending.get(category, 0) + t['amount']
        
        top_category = max(category_spending.items(), key=lambda x: x[1]) if category_spending else None
        
        analysis = f"""**Recent Transactions Analysis:**
        
📊 **Summary:**
• Total Credits: ₹{total_credits:,}
• Total Debits: ₹{total_debits:,}
• Net Flow: ₹{total_credits - total_debits:,}
• Number of Transactions: {len(transactions)}

"""
        
        if top_category:
            analysis += f"💸 **Top Spending Category:** {top_category[0]} (₹{top_category[1]:,})\n\n"
        
        analysis += "📋 **Recent Activity:**\n"
        for i, t in enumerate(transactions[:5], 1):
            icon = "💰" if t['type'] == 'Credit' else "💸"
            analysis += f"{i}. {icon} {t['description']} - ₹{t['amount']:,} ({t.get('category', 'Other')})\n"
        
        if len(transactions) > 5:
            analysis += f"\n... and {len(transactions) - 5} more transactions"
        
        return analysis.strip()
    
    def get_account_balance_analysis(self, financial_data):
        """Analyze account balances from real database data"""
        accounts = financial_data.get('accounts', [])
        loans = financial_data.get('loans', [])
        investments = financial_data.get('investments', [])
        cards = financial_data.get('cards', [])
        
        if not accounts:
            return "No account information available. Please add your accounts to get balance insights!"
        
        total_savings = 0
        total_debt = 0
        total_investments = 0
        account_details = []
        
        # Analyze accounts
        for account in accounts:
            balance = account.get('balance', 0)
            account_type = account.get('type', 'Unknown')
            bank = account.get('bank', 'Unknown Bank')
            
            if account_type.lower() in ['savings', 'checking', 'current']:
                total_savings += balance
                account_details.append(f"🏦 {bank} {account_type}: ₹{balance:,}")
            elif account_type.lower() in ['credit', 'loan']:
                total_debt += abs(balance)
                account_details.append(f"💳 {bank} {account_type}: ₹{abs(balance):,} (debt)")
            else:
                account_details.append(f"💳 {bank} {account_type}: ₹{balance:,}")
        
        # Add loan debt
        for loan in loans:
            loan_amount = loan.get('amount', 0)
            total_debt += loan_amount
            account_details.append(f"🏦 Loan: ₹{loan_amount:,} (Interest: {loan.get('interest_rate', 0)}%)")
        
        # Add investments
        for investment in investments:
            investment_amount = investment.get('amount', 0)
            total_investments += investment_amount
            account_details.append(f"📈 {investment.get('investment_type', 'Investment')}: ₹{investment_amount:,}")
        
        # Add credit card limits
        for card in cards:
            limit_amount = card.get('limit_amount', 0)
            account_details.append(f"💳 {card.get('card_type', 'Card')}: Limit ₹{limit_amount:,}")
        
        net_worth = total_savings + total_investments - total_debt
        
        analysis = f"""**💰 Account Balance Analysis:**

🏦 **Total Savings:** ₹{total_savings:,}
📈 **Total Investments:** ₹{total_investments:,}
💸 **Total Debt:** ₹{total_debt:,}
📊 **Net Worth:** ₹{net_worth:,}

**📋 Account Details:**
"""
        for detail in account_details:
            analysis += f"• {detail}\n"
        
        # Add recommendations based on balance
        if total_debt > total_savings:
            analysis += f"""
⚠️ **Recommendation:** You have more debt than savings. Consider:
• Paying off high-interest debt first
• Building an emergency fund
• Reducing unnecessary expenses
• Consolidating loans if possible
"""
        elif net_worth > 0:
            analysis += f"""
✅ **Good News:** You have a positive net worth! Consider:
• Investing excess savings
• Building an emergency fund (3-6 months expenses)
• Diversifying your investments
• Reviewing your investment portfolio
"""
        
        return analysis.strip()
    
    def get_investment_analysis(self, financial_data):
        """Analyze investments from real database data"""
        investments = financial_data.get('investments', [])
        
        if not investments:
            return "No investment data available. Consider starting with mutual funds or fixed deposits!"
        
        total_investment = sum(inv.get('amount', 0) for inv in investments)
        
        analysis = f"""**📈 Investment Analysis:**

💰 **Total Investment:** ₹{total_investment:,}
📊 **Number of Investments:** {len(investments)}

**📋 Investment Details:**
"""
        
        for i, investment in enumerate(investments, 1):
            inv_type = investment.get('investment_type', 'Unknown')
            amount = investment.get('amount', 0)
            start_date = investment.get('start_date', 'N/A')
            maturity_date = investment.get('maturity_date', 'N/A')
            
            analysis += f"{i}. **{inv_type}**: ₹{amount:,}\n"
            analysis += f"   Start: {start_date} | Maturity: {maturity_date}\n"
        
        # Add recommendations
        analysis += f"""
**💡 Investment Recommendations:**
• Diversify across different asset classes
• Consider SIPs for regular investing
• Review and rebalance quarterly
• Keep emergency fund separate from investments
• Consider tax-saving investments (ELSS, PPF)
"""
        
        return analysis.strip()
    
    def get_loan_analysis(self, financial_data):
        """Analyze loans from real database data"""
        loans = financial_data.get('loans', [])
        
        if not loans:
            return "No loan data available. Great job on being debt-free!"
        
        total_loan_amount = sum(loan.get('amount', 0) for loan in loans)
        avg_interest_rate = sum(loan.get('interest_rate', 0) for loan in loans) / len(loans) if loans else 0
        
        analysis = f"""**🏦 Loan Analysis:**

💸 **Total Loan Amount:** ₹{total_loan_amount:,}
📊 **Number of Loans:** {len(loans)}
📈 **Average Interest Rate:** {avg_interest_rate:.2f}%

**📋 Loan Details:**
"""
        
        for i, loan in enumerate(loans, 1):
            description = loan.get('description', 'Unknown Loan')
            amount = loan.get('amount', 0)
            interest_rate = loan.get('interest_rate', 0)
            due_date = loan.get('due_date', 'N/A')
            
            analysis += f"{i}. **{description}**: ₹{amount:,}\n"
            analysis += f"   Interest: {interest_rate}% | Due: {due_date}\n"
        
        # Add recommendations
        analysis += f"""
**💡 Loan Management Tips:**
• Pay off high-interest loans first
• Consider loan consolidation if rates are high
• Make extra payments when possible
• Set up automatic payments to avoid late fees
• Review loan terms and refinance if beneficial
"""
        
        return analysis.strip()
    
    def get_insurance_analysis(self, financial_data):
        """Analyze insurance from real database data"""
        insurance = financial_data.get('insurance', [])
        
        if not insurance:
            return "No insurance data available. Consider getting health and life insurance for financial security!"
        
        total_premium = sum(policy.get('premium_amount', 0) for policy in insurance)
        total_coverage = sum(policy.get('coverage_amount', 0) for policy in insurance)
        
        analysis = f"""**🛡️ Insurance Analysis:**

💰 **Total Premium:** ₹{total_premium:,}
📊 **Total Coverage:** ₹{total_coverage:,}
📈 **Number of Policies:** {len(insurance)}

**📋 Policy Details:**
"""
        
        for i, policy in enumerate(insurance, 1):
            policy_name = policy.get('policy_name', 'Unknown Policy')
            policy_type = policy.get('policy_type', 'Unknown')
            premium = policy.get('premium_amount', 0)
            coverage = policy.get('coverage_amount', 0)
            next_due = policy.get('next_due_date', 'N/A')
            
            analysis += f"{i}. **{policy_name}** ({policy_type})\n"
            analysis += f"   Premium: ₹{premium:,} | Coverage: ₹{coverage:,}\n"
            analysis += f"   Next Due: {next_due}\n"
        
        # Add recommendations
        analysis += f"""
**💡 Insurance Recommendations:**
• Ensure adequate life insurance coverage (10-15x annual income)
• Health insurance is essential for medical emergencies
• Review policies annually for coverage adequacy
• Consider term insurance for better coverage at lower cost
• Keep policy documents safe and accessible
"""
        
        return analysis.strip()
    
    def get_card_analysis(self, financial_data):
        """Analyze cards from real database data"""
        cards = financial_data.get('cards', [])
        
        if not cards:
            return "No card data available. Consider getting a credit card for building credit history!"
        
        total_limit = sum(card.get('limit_amount', 0) for card in cards)
        
        analysis = f"""**💳 Card Analysis:**

💳 **Total Credit Limit:** ₹{total_limit:,}
📊 **Number of Cards:** {len(cards)}

**📋 Card Details:**
"""
        
        for i, card in enumerate(cards, 1):
            card_type = card.get('card_type', 'Unknown')
            limit_amount = card.get('limit_amount', 0)
            expiry_date = card.get('expiry_date', 'N/A')
            
            analysis += f"{i}. **{card_type}**: Limit ₹{limit_amount:,}\n"
            analysis += f"   Expires: {expiry_date}\n"
        
        # Add recommendations
        analysis += f"""
**💡 Card Management Tips:**
• Pay full balance monthly to avoid interest
• Keep credit utilization under 30%
• Monitor statements regularly for fraud
• Use cards for rewards and cashback
• Don't apply for too many cards at once
"""
        
        return analysis.strip()
    
    def process_message(self, message, user_id, user_mode='professional', profile_data=None):
        """Process user message and generate appropriate response"""
        message_lower = message.lower()
        
        # Store in chat history
        self.chat_history.append({
            'user': message,
            'timestamp': datetime.now().isoformat()
        })
        
        # Get user's financial data
        financial_data = self.get_user_financial_data(user_id)
        
        # Route to appropriate handler
        if any(word in message_lower for word in ['budget', 'spending', 'expense', 'expenses', 'spend', 'money spent']):
            return self.analyze_spending_patterns(financial_data)
        
        elif any(word in message_lower for word in ['save', 'saving', 'savings', 'save money', 'how to save']):
            return self.get_savings_recommendations(financial_data)
        
        elif any(word in message_lower for word in ['invest', 'investment', 'portfolio', 'mutual fund', 'sip']):
            return self.get_investment_advice(user_mode)
        
        elif any(word in message_lower for word in ['stock', 'stocks', 'share', 'shares', 'equity']):
            # Extract price limit and count from message
            price_match = re.search(r'under\s+(\d+)', message_lower)
            count_match = re.search(r'(\d+)\s+stocks?', message_lower)
            
            price_limit = int(price_match.group(1)) if price_match else 500
            count = int(count_match.group(1)) if count_match else 10
            
            return self.get_stock_recommendations(price_limit, count)
        
        elif any(word in message_lower for word in ['transaction', 'transactions', 'recent', 'history', 'activity']):
            return self.get_recent_transactions_analysis(financial_data)
        
        elif any(word in message_lower for word in ['balance', 'account', 'accounts', 'money', 'funds']):
            return self.get_account_balance_analysis(financial_data)
        
        elif any(word in message_lower for word in ['investment', 'investments', 'portfolio', 'mutual fund', 'fd', 'fixed deposit']):
            return self.get_investment_analysis(financial_data)
        
        elif any(word in message_lower for word in ['loan', 'loans', 'debt', 'borrow']):
            return self.get_loan_analysis(financial_data)
        
        elif any(word in message_lower for word in ['insurance', 'policy', 'premium', 'coverage']):
            return self.get_insurance_analysis(financial_data)
        
        elif any(word in message_lower for word in ['card', 'cards', 'credit card', 'debit card']):
            return self.get_card_analysis(financial_data)
        
        elif any(word in message_lower for word in ['hello', 'hi', 'hey']):
            return f"""Hello! I'm your AI financial assistant. I can help you with:

💰 **Budget Analysis** - Review your spending patterns
💡 **Savings Tips** - Get personalized savings advice  
📈 **Investment Guidance** - Learn about investment options
📊 **Stock Recommendations** - Find stocks under specific prices
💳 **Debt Management** - Get debt reduction strategies

What would you like to know about your finances?"""
        
        elif any(word in message_lower for word in ['help', 'what can you do']):
            return """I can help you with various financial topics:

**Budget & Spending:**
• Analyze your spending patterns
• Identify top spending categories
• Provide budget recommendations

**Savings & Investments:**
• Calculate your savings rate
• Suggest investment strategies
• Recommend mutual funds and stocks

**Financial Planning:**
• Emergency fund planning
• Tax-saving investments
• Retirement planning basics

**Stock Market:**
• Find stocks under specific prices
• Get basic stock information
• Market insights

Just ask me about any of these topics!"""
        
        else:
            return """I'm here to help with your financial questions! You can ask me about:

• Your budget and spending analysis
• Savings tips and strategies
• Investment recommendations
• Stock suggestions under specific prices
• Debt management advice

Try asking something like:
- "Analyze my budget"
- "How can I save more money?"
- "Show me stocks under 500"
- "Investment advice for students"

What would you like to know?"""

# Initialize chatbot instance
chatbot = FinancialChatbot()

# API Routes
@chatbot_bp.route('/api/chatbot', methods=['POST'])
def chatbot_response():
    """Main chatbot endpoint"""
    try:
        data = request.json
        user_message = data.get('message', '')
        
        # Get user_id from session if available, otherwise use provided or default
        user_id = session.get('user_id') or data.get('user_id', 'demo_user')
        user_mode = data.get('user_mode', 'professional')
        profile_data = data.get('profile_data', {})
        
        if not user_message:
            return jsonify({"response": "Please provide a message."}), 400
        
        # Get response from chatbot
        response = chatbot.process_message(user_message, user_id, user_mode, profile_data)
        
        return jsonify({"response": response}), 200
        
    except Exception as e:
        return jsonify({"response": f"Sorry, I encountered an error: {str(e)}"}), 500

@chatbot_bp.route('/api/insights', methods=['POST'])
def get_insights():
    """Get AI insights for dashboard"""
    try:
        data = request.json
        user_id = data.get('user_id', 'demo_user')
        user_mode = data.get('user_mode', 'professional')
        profile_data = data.get('profile_data', {})
        
        # Get financial data and generate insights
        financial_data = chatbot.get_user_financial_data(user_id)
        insights = chatbot.analyze_spending_patterns(financial_data)
        
        return jsonify({"response": insights}), 200
        
    except Exception as e:
        return jsonify({"response": "Analyzing your financial data to provide personalized insights..."}), 500

@chatbot_bp.route('/api/budget', methods=['POST'])
def get_budget_analysis():
    """Get budget analysis"""
    try:
        data = request.json
        user_id = data.get('user_id', 'demo_user')
        user_mode = data.get('user_mode', 'professional')
        
        # Get financial data
        financial_data = chatbot.get_user_financial_data(user_id)
        
        # Generate budget analysis
        spending_analysis = chatbot.analyze_spending_patterns(financial_data)
        savings_recommendations = chatbot.get_savings_recommendations(financial_data)
        
        # Prepare chart data
        spending_data = financial_data.get('spending_by_category', [])
        chart_data = []
        for item in spending_data:
            chart_data.append({
                'Category': item['category'],
                'Amount': float(item['total_amount']),
                'Percentage': round((item['total_amount'] / sum(i['total_amount'] for i in spending_data)) * 100, 1) if spending_data else 0
            })
        
        return jsonify({
            "response": f"{spending_analysis}\n\n{savings_recommendations}",
            "chart_data": chart_data,
            "summary": spending_analysis
        }), 200
        
    except Exception as e:
        return jsonify({"response": "Generating your budget analysis..."}), 500

@chatbot_bp.route('/api/guidance', methods=['POST'])
def get_guidance():
    """Get general financial guidance"""
    try:
        data = request.json
        user_id = data.get('user_id', 'demo_user')
        user_mode = data.get('user_mode', 'professional')
        profile_data = data.get('profile_data', {})
        
        # Get personalized guidance based on user mode
        if user_mode == 'student':
            guidance = """**Financial Guidance for Students:**

1. **Start Early** - Time is your biggest advantage
2. **Learn First** - Understand basics before investing
3. **Emergency Fund** - Save ₹10,000-25,000 first
4. **Low-Cost Investing** - Use SIPs in index funds
5. **Avoid Debt** - Don't take unnecessary loans

**Quick Actions:**
• Open a savings account with good interest
• Start a ₹500/month SIP in Nifty 50
• Track your expenses using our app
• Learn about compound interest
• Set financial goals for after graduation"""
        else:
            guidance = """**Financial Guidance for Professionals:**

1. **Emergency Fund** - 6 months of expenses
2. **Insurance** - Health and term life insurance
3. **Tax Planning** - Use ELSS, PPF, NPS
4. **Asset Allocation** - Diversify across asset classes
5. **Regular Review** - Monitor and rebalance quarterly

**Quick Actions:**
• Increase your savings rate to 20%+
• Start SIPs in diversified mutual funds
• Review and optimize your insurance
• Plan for major life goals
• Consider tax-saving investments"""
        
        return jsonify({"response": guidance}), 200
        
    except Exception as e:
        return jsonify({"response": "Providing personalized financial guidance..."}), 500
