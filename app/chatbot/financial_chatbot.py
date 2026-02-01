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
        # Per-user conversation context: {user_id: {current_topic, last_response_type, conversation_state}}
        self.user_context = {}
        # Global chat history for fallback
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
    
    def analyze_spending_patterns(self, financial_data, is_followup=False):
        """Analyze user's spending patterns from real database data"""
        spending_data = financial_data.get('spending_by_category', [])
        expenses = financial_data.get('expenses', [])
        transactions = financial_data.get('transactions', [])
        
        if not spending_data and not expenses:
            greeting = "I'd love to help you analyze your spending, but " if not is_followup else "Unfortunately, "
            return f"""{greeting}I don't see any spending data available yet. 

To get started, try adding some expenses in the Expenses section. Once you have some data, I can help you:
• Identify your top spending categories
• Track monthly spending trends
• Suggest areas to cut back
• Create a personalized budget

Would you like tips on how to track expenses effectively?"""
        
        # Calculate total spending from expenses
        total_spent = sum(item['total_amount'] for item in spending_data) if spending_data else 0
        
        # Get recent expenses for detailed analysis
        recent_expenses = expenses[:10] if expenses else []
        
        greeting = "Great! Let me analyze your spending patterns. " if not is_followup else "Looking at your spending data, "
        
        analysis = f"""{greeting}Here's what I found:

**📊 Spending Overview:**
💰 Monthly Spending: ₹{total_spent:,}
📈 Total Expenses: {len(expenses)} transactions
💳 Total Transactions: {len(transactions)} transactions

"""
        
        if spending_data:
            top_category = max(spending_data, key=lambda x: x['total_amount'])
            analysis += f"🏆 **Your top spending category is {top_category['category']}** at ₹{top_category['total_amount']:,}.\n\n"
            
            analysis += "**📋 Category Breakdown:**\n"
            for item in spending_data[:5]:
                percentage = (item['total_amount'] / total_spent) * 100 if total_spent > 0 else 0
                analysis += f"• {item['category']}: ₹{item['total_amount']:,} ({percentage:.1f}%)\n"
        
        if recent_expenses:
            analysis += f"\n**📝 Your Recent Expenses:**\n"
            for i, expense in enumerate(recent_expenses[:5], 1):
                analysis += f"{i}. {expense['title']} - ₹{expense['amount']:,} ({expense.get('category', 'Other')})\n"
        
        # Add follow-up suggestions
        analysis += "\n\n💡 **What would you like to know more about?**\n"
        analysis += "• How to reduce spending in specific categories\n"
        analysis += "• Tips to improve your savings rate\n"
        analysis += "• Creating a monthly budget plan"
        
        return analysis.strip()
    
    def get_savings_recommendations(self, financial_data, is_followup=False):
        """Provide savings recommendations based on spending patterns"""
        spending_data = financial_data.get('spending_by_category', [])
        accounts = financial_data.get('accounts', [])
        
        # Calculate total income and expenses
        total_income = 0
        total_expenses = 0
        
        for account in accounts:
            account_type = account.get('type', account.get('account_type', '')).lower()
            if 'savings' in account_type or 'checking' in account_type or 'current' in account_type:
                total_income += account.get('balance', 0)
        
        for item in spending_data:
            total_expenses += item.get('total_amount', 0)
        
        savings_rate = ((total_income - total_expenses) / total_income * 100) if total_income > 0 else 0
        net_savings = total_income - total_expenses
        
        greeting = "Let me analyze your savings situation. " if not is_followup else "Based on your financial data, "
        
        recommendations = f"""{greeting}Here's your savings analysis:

**💰 Current Financial Status:**
• Savings Rate: {savings_rate:.1f}%
• Monthly Income: ₹{total_income:,}
• Monthly Expenses: ₹{total_expenses:,}
• Net Savings: ₹{net_savings:,}

"""
        
        if savings_rate < 20:
            recommendations += """**💡 Recommendations to Improve Your Savings:**

1. **Aim for 20% Savings Rate** - Start by saving at least 20% of your income
2. **Track Daily Expenses** - Use our expense tracker to identify unnecessary spending
3. **Automate Savings** - Set up automatic transfers to a separate savings account
4. **Reduce Discretionary Spending** - Look for ways to cut back on entertainment and shopping
5. **Build Emergency Fund** - Save 3-6 months of expenses for unexpected situations

Would you like specific tips on any of these areas?"""
        else:
            recommendations += """**🎉 Great job on your savings!** You're doing well. Here's how to take it further:

1. **Consider Investments** - Put your excess savings to work and grow your wealth
2. **Diversify Your Portfolio** - Mix of equity, debt, and gold for balanced growth
3. **Tax-Saving Investments** - Explore ELSS funds for tax benefits
4. **Plan Long-term Goals** - Think about retirement and major life purchases
5. **Review Regularly** - Check your progress monthly and adjust as needed

Would you like investment recommendations tailored to your profile?"""
        
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
    
    def get_recent_transactions_analysis(self, financial_data, is_followup=False):
        """Analyze recent transactions"""
        transactions = financial_data.get('transactions', [])
        if not transactions:
            greeting = "I'd like to show you your recent transactions, but " if not is_followup else "Unfortunately, "
            return f"""{greeting}I don't see any transactions in your account yet.

To get started, try adding some transactions in the Transactions section. Once you have some data, I can help you:
• Track your income and expenses
• Identify spending patterns
• Monitor your financial activity
• Analyze cash flow

Would you like help getting started with tracking transactions?"""
        
        # Analyze recent transactions
        total_credits = sum(t.get('amount', 0) for t in transactions if t.get('type', '').lower() == 'credit')
        total_debits = sum(t.get('amount', 0) for t in transactions if t.get('type', '').lower() == 'debit')
        
        # Get top spending categories
        debit_transactions = [t for t in transactions if t.get('type', '').lower() == 'debit']
        category_spending = {}
        for t in debit_transactions:
            category = t.get('category', 'Other')
            category_spending[category] = category_spending.get(category, 0) + t.get('amount', 0)
        
        top_category = max(category_spending.items(), key=lambda x: x[1]) if category_spending else None
        
        greeting = "Here's a look at your recent transactions. " if not is_followup else "Looking at your transaction history, "
        
        analysis = f"""{greeting}Here's what I found:

📊 **Transaction Summary:**
• Total Credits: ₹{total_credits:,}
• Total Debits: ₹{total_debits:,}
• Net Flow: ₹{total_credits - total_debits:,}
• Total Transactions: {len(transactions)}

"""
        
        if top_category:
            analysis += f"💸 **Your top spending category is {top_category[0]}** at ₹{top_category[1]:,}.\n\n"
        
        analysis += "📋 **Your Recent Activity:**\n"
        for i, t in enumerate(transactions[:5], 1):
            icon = "💰" if t.get('type', '').lower() == 'credit' else "💸"
            title = t.get('title', t.get('description', 'Transaction'))
            amount = t.get('amount', 0)
            category = t.get('category', 'Other')
            analysis += f"{i}. {icon} {title} - ₹{amount:,} ({category})\n"
        
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
    
    def _get_conversation_context(self, user_id, chat_history=None):
        """Get or initialize conversation context for a user"""
        if user_id not in self.user_context:
            self.user_context[user_id] = {
                'current_topic': None,
                'last_response_type': None,
                'conversation_state': 'greeting',  # greeting, active, followup
                'mentioned_topics': []
            }
        return self.user_context[user_id]
    
    def _update_context(self, user_id, topic=None, response_type=None, state=None):
        """Update conversation context"""
        context = self._get_conversation_context(user_id)
        if topic:
            context['current_topic'] = topic
            if topic not in context['mentioned_topics']:
                context['mentioned_topics'].append(topic)
        if response_type:
            context['last_response_type'] = response_type
        if state:
            context['conversation_state'] = state
    
    def _detect_followup(self, message_lower, context, chat_history=None):
        """Detect if the message is a follow-up to previous conversation"""
        followup_indicators = [
            'tell me more', 'more about', 'what about', 'how about', 'can you explain',
            'elaborate', 'details', 'more details', 'go on', 'continue', 'and', 'also',
            'what else', 'anything else', 'other', 'another', 'yes', 'sure', 'okay', 'ok',
            'yeah', 'yep', 'please', 'thanks', 'thank you', 'cool', 'nice', 'good',
            'that\'s helpful', 'helpful', 'what', 'how', 'why', 'when', 'where'
        ]
        
        # Check if it's a very short message (likely follow-up)
        if len(message_lower.split()) <= 3:
            if any(indicator in message_lower for indicator in followup_indicators):
                return True
        
        # Check if previous topic exists and message is related
        if context['current_topic']:
            topic_keywords = {
                'budget': ['spending', 'expense', 'money', 'category', 'reduce', 'cut'],
                'savings': ['save', 'saving', 'improve', 'increase', 'tips', 'advice'],
                'investment': ['invest', 'portfolio', 'mutual', 'fund', 'sip', 'stock'],
                'stock': ['stock', 'share', 'price', 'buy', 'recommend'],
                'balance': ['account', 'money', 'fund', 'balance', 'total']
            }
            
            if context['current_topic'] in topic_keywords:
                if any(keyword in message_lower for keyword in topic_keywords[context['current_topic']]):
                    return True
        
        # Check chat history for context
        if chat_history and len(chat_history) > 0:
            # If last message was from bot and current is short, likely follow-up
            last_msg = chat_history[-1] if isinstance(chat_history[-1], dict) else None
            if last_msg and last_msg.get('sender') == 'bot' and len(message_lower.split()) <= 5:
                return True
        
        return False
    
    def _add_conversational_transition(self, response, topic, context):
        """Add natural conversational transitions to responses"""
        transitions = {
            'budget': "\n\n💬 **Want to dive deeper?** I can help you create a budget plan or suggest ways to reduce spending in specific categories.",
            'savings': "\n\n💬 **Next steps?** Would you like investment recommendations or tips on building an emergency fund?",
            'investment': "\n\n💬 **Want to know more?** I can help you with specific investment types, stock recommendations, or portfolio planning.",
            'stock': "\n\n💬 **Interested in more?** I can provide details on any stock, help with investment strategies, or analyze your portfolio.",
            'balance': "\n\n💬 **What's next?** I can help you with savings strategies, investment planning, or debt management based on your current balance."
        }
        
        if topic in transitions:
            response += transitions[topic]
        
        return response
    
    def process_message(self, message, user_id, user_mode='professional', profile_data=None, chat_history=None):
        """Process user message and generate appropriate response with conversational flow"""
        message_lower = message.lower().strip()
        
        # Get conversation context
        context = self._get_conversation_context(user_id, chat_history)
        is_followup = self._detect_followup(message_lower, context, chat_history)
        
        # Get user's financial data
        financial_data = self.get_user_financial_data(user_id)
        
        # Handle greetings and small talk
        if any(word in message_lower for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening']):
            self._update_context(user_id, state='greeting')
            name = profile_data.get('Name', '') if profile_data else ''
            greeting = f"Hi{(' ' + name.split()[0]) if name else ''}! " if name else "Hello! "
            return f"""{greeting}I'm your AI financial assistant. 👋

I'm here to help you understand and improve your finances. I can help you with:

💰 **Budget & Spending** - Analyze where your money goes
💡 **Savings Strategies** - Tips to save more effectively  
📈 **Investment Guidance** - Personalized investment advice
📊 **Stock Recommendations** - Find investment opportunities
💳 **Financial Planning** - Debt management and planning

What would you like to explore today?"""
        
        # Handle follow-up questions
        if is_followup and context['current_topic']:
            if context['current_topic'] == 'budget':
                return self.analyze_spending_patterns(financial_data, is_followup=True)
            elif context['current_topic'] == 'savings':
                return self.get_savings_recommendations(financial_data, is_followup=True)
            elif context['current_topic'] == 'investment':
                advice = self.get_investment_advice(user_mode)
                return f"Let me share more about investments:\n\n{advice}\n\nWould you like to know about specific investment types or see your current portfolio?"
            elif context['current_topic'] == 'stock':
                return "I'd be happy to help with stocks! What price range are you interested in? For example, you can ask 'Show me stocks under 500'."
        
        # Route to appropriate handler with context tracking
        if any(word in message_lower for word in ['budget', 'spending', 'expense', 'expenses', 'spend', 'money spent', 'where did my money go']):
            self._update_context(user_id, topic='budget', response_type='analysis', state='active')
            response = self.analyze_spending_patterns(financial_data, is_followup)
            return self._add_conversational_transition(response, 'budget', context)
        
        elif any(word in message_lower for word in ['save', 'saving', 'savings', 'save money', 'how to save', 'improve savings']):
            self._update_context(user_id, topic='savings', response_type='recommendations', state='active')
            response = self.get_savings_recommendations(financial_data, is_followup)
            return self._add_conversational_transition(response, 'savings', context)
        
        elif any(word in message_lower for word in ['invest', 'investment', 'portfolio', 'mutual fund', 'sip', 'where should i invest']):
            self._update_context(user_id, topic='investment', response_type='advice', state='active')
            advice = self.get_investment_advice(user_mode)
            response = f"{advice}\n\n💬 **Want to see your current investments?** Just ask me to analyze your portfolio!"
            return response
        
        elif any(word in message_lower for word in ['stock', 'stocks', 'share', 'shares', 'equity']):
            self._update_context(user_id, topic='stock', response_type='recommendations', state='active')
            # Extract price limit and count from message
            price_match = re.search(r'under\s+(\d+)', message_lower)
            count_match = re.search(r'(\d+)\s+stocks?', message_lower)
            
            price_limit = int(price_match.group(1)) if price_match else 500
            count = int(count_match.group(1)) if count_match else 10
            
            response = self.get_stock_recommendations(price_limit, count)
            return f"{response}\n\n💬 **Need more help?** I can provide details on any stock or help with investment strategies!"
        
        elif any(word in message_lower for word in ['transaction', 'transactions', 'recent', 'history', 'activity', 'what did i buy']):
            self._update_context(user_id, topic='transactions', response_type='analysis', state='active')
            response = self.get_recent_transactions_analysis(financial_data, is_followup)
            return f"{response}\n\n💬 **Want to analyze your spending patterns?** Just ask me about your budget!"
        
        elif any(word in message_lower for word in ['balance', 'account', 'accounts', 'money', 'funds', 'how much do i have']):
            self._update_context(user_id, topic='balance', response_type='analysis', state='active')
            response = self.get_account_balance_analysis(financial_data)
            return self._add_conversational_transition(response, 'balance', context)
        
        elif any(word in message_lower for word in ['loan', 'loans', 'debt', 'borrow', 'how much do i owe']):
            self._update_context(user_id, topic='loans', response_type='analysis', state='active')
            response = self.get_loan_analysis(financial_data)
            return f"{response}\n\n💬 **Want help managing debt?** I can suggest strategies to pay off loans faster!"
        
        elif any(word in message_lower for word in ['insurance', 'policy', 'premium', 'coverage']):
            self._update_context(user_id, topic='insurance', response_type='analysis', state='active')
            response = self.get_insurance_analysis(financial_data)
            return f"{response}\n\n💬 **Have questions about insurance?** I can help you understand coverage needs or compare policies!"
        
        elif any(word in message_lower for word in ['card', 'cards', 'credit card', 'debit card']):
            self._update_context(user_id, topic='cards', response_type='analysis', state='active')
            response = self.get_card_analysis(financial_data)
            return f"{response}\n\n💬 **Want credit card tips?** I can help with managing credit utilization and maximizing rewards!"
        
        elif any(word in message_lower for word in ['help', 'what can you do', 'what do you do', 'capabilities']):
            self._update_context(user_id, state='help')
            return """I'm your financial assistant, and I'm here to help you make better financial decisions! 💪

**Here's what I can help with:**

📊 **Budget & Spending Analysis**
• Analyze where your money goes
• Identify top spending categories
• Suggest areas to cut back

💰 **Savings & Financial Health**
• Calculate your savings rate
• Provide personalized savings tips
• Help build emergency funds

📈 **Investment Guidance**
• Investment strategies for your profile
• Portfolio recommendations
• Stock suggestions under specific prices

💳 **Financial Planning**
• Debt management strategies
• Account balance analysis
• Insurance and card management

**Just ask naturally!** For example:
• "How can I save more money?"
• "Analyze my spending"
• "Show me stocks under 500"
• "What's my account balance?"

What would you like to explore?"""
        
        elif any(word in message_lower for word in ['thank', 'thanks', 'appreciate', 'grateful']):
            self._update_context(user_id, state='active')
            return """You're very welcome! 😊

I'm always here to help with your financial questions. Feel free to ask me anything about:
• Your budget and spending
• Savings strategies
• Investment advice
• Stock recommendations
• Or any other financial topic!

Is there anything else you'd like to know?"""
        
        else:
            # Handle ambiguous queries with clarifying questions
            self._update_context(user_id, state='active')
            return """I'd love to help! Could you tell me a bit more about what you're looking for? 🤔

For example, you could ask:
• **"Analyze my budget"** - to see your spending patterns
• **"How can I save more?"** - for savings tips
• **"Show me stocks under 500"** - for stock recommendations
• **"What's my account balance?"** - to check your finances
• **"Investment advice"** - for investment guidance

Or just tell me what financial topic you're interested in, and I'll help you out!"""

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
        
        # Get chat history from request
        chat_history = data.get('chat_history', [])
        
        # Get response from chatbot with conversation context
        response = chatbot.process_message(
            user_message, 
            user_id, 
            user_mode, 
            profile_data,
            chat_history=chat_history
        )
        
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
