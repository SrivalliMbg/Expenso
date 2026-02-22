"""
Financial Chatbot for Expenso Application
Integrated with the main Flask app and database
"""

from flask import Blueprint, request, jsonify, current_app, g, session
import pandas as pd
import numpy as np
import yfinance as yf
import re
import os
import random
import requests
from datetime import datetime, timedelta
import json

try:
    from app.chatbot.intent_classifier import get_intent
except ImportError:
    try:
        from intent_classifier import get_intent
    except ImportError:
        get_intent = None

# Create blueprint
chatbot_bp = Blueprint('chatbot', __name__)

# --- Human-like conversation phrases (Turing-style naturalness) ---
ACKNOWLEDGMENTS = [
    "Good question! ",
    "So you're asking about that — ",
    "Yeah, so ",
    "Sure — ",
    "Okay, so ",
    "Right, so ",
    "So basically ",
    "Honestly? ",
    "The short answer is ",
    "Here's the thing: ",
    "",
]
CLOSINGS = [
    " Does that help?",
    " Want me to go deeper on any of this?",
    " Let me know if you want more detail.",
    " If you want to dig into something specific, just ask.",
    " Anything else on your mind about this?",
    "",
]
GREETING_VARIANTS = [
    "Hey! Good to see you. ",
    "Hi there! ",
    "Hello! ",
    "Hey — ",
]
HELP_OPENERS = [
    "So basically I'm here to help with your money — ",
    "I'm your finance buddy, basically. ",
    "Think of me as a friend who's good with numbers. ",
]
THANKS_RESPONSES = [
    "You're welcome! Happy to help.",
    "Anytime!",
    "No problem at all.",
    "Glad I could help!",
]
CLARIFY_OPENERS = [
    "I'd love to help — can you give me a bit more to go on? ",
    "Sure, just need a bit more detail. ",
    "Could you narrow it down a bit? ",
]

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

    def ollama_financial_agent(self, message, context_data):
        """Use local Ollama LLM for financial advice. Returns None if Ollama is offline or errors."""
        if not context_data:
            return "No financial context available to analyze."
        try:
            prompt = f"""
You are Expenso AI, a financial assistant.

STRICT RULES:
- Use ONLY the data provided in Context Data.
- DO NOT generate or assume missing balances.
- If data is missing, clearly state it.
- Never hallucinate financial numbers.

User Question:
{message}

Context Data:
{json.dumps(context_data, indent=2, default=str)}

If financial data is empty, respond that no data exists.
"""
            resp = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3",
                    "prompt": prompt,
                    "stream": False
                },
                timeout=60
            )
            resp.raise_for_status()
            out = resp.json()
            return out.get("response") or None
        except Exception:
            return None

    def get_gold_price(self):
        """Fetch current gold price (USD per oz) via yfinance."""
        try:
            gold = yf.Ticker("GC=F")
            data = gold.history(period="1d")
            if not data.empty:
                return float(data["Close"].iloc[-1])
        except Exception:
            pass
        return None

    def get_stock_price(self, symbol):
        """Fetch current stock price for symbol via yfinance."""
        if not symbol or not str(symbol).strip():
            return None
        try:
            stock = yf.Ticker(str(symbol).strip().upper())
            data = stock.history(period="1d")
            if not data.empty:
                return float(data["Close"].iloc[-1])
        except Exception:
            pass
        return None

    def get_user_financial_data(self, user_id):
        """Get user's comprehensive financial data from all database tables. Returns {} when no DB, no user_id, or no accounts. No demo or default data."""
        if not g.mysql or user_id is None or user_id == '':
            return {}
        
        cursor = None
        try:
            cursor = g.mysql.cursor(dictionary=True, buffered=True)
            
            # Only this user's data: get accounts for user_id first
            cursor.execute("""
                SELECT id, type, bank, branch, acc_no, balance, created_at 
                FROM accounts
                WHERE user_id = %s
            """, (user_id,))
            accounts = cursor.fetchall()
            account_ids = [a['id'] for a in accounts]
            
            if not account_ids:
                return {}
            
            placeholders = ','.join(['%s'] * len(account_ids))
            
            cursor.execute(f"""
                SELECT id, account_id, title, amount, type, date, created_at
                FROM transactions
                WHERE account_id IN ({placeholders})
                ORDER BY date DESC
            """, tuple(account_ids))
            transactions = cursor.fetchall()
            
            cursor.execute(f"""
                SELECT id, account_id, title, amount, category, date, created_at
                FROM expenses
                WHERE account_id IN ({placeholders})
                ORDER BY date DESC
            """, tuple(account_ids))
            expenses = cursor.fetchall()
            
            cursor.execute(f"""
                SELECT id, account_id, card_type, card_number, expiry_date, cvv, limit_amount, created_at
                FROM cards
                WHERE account_id IN ({placeholders})
            """, tuple(account_ids))
            cards = cursor.fetchall()
            
            cursor.execute(f"""
                SELECT id, account_id, investment_type, amount, start_date, maturity_date, created_at
                FROM investments
                WHERE account_id IN ({placeholders})
            """, tuple(account_ids))
            investments = cursor.fetchall()
            
            cursor.execute(f"""
                SELECT id, account_id, description, amount, interest_rate, due_date, created_at
                FROM loans
                WHERE account_id IN ({placeholders})
            """, tuple(account_ids))
            loans = cursor.fetchall()
            
            cursor.execute(f"""
                SELECT id, account_id, policy_name, premium_amount, coverage_amount, created_at
                FROM insurance
                WHERE account_id IN ({placeholders})
            """, tuple(account_ids))
            insurance = cursor.fetchall()
            
            cursor.execute(f"""
                SELECT id, account_id, amount, created_at
                FROM borrowings
                WHERE account_id IN ({placeholders})
            """, tuple(account_ids))
            borrowings = cursor.fetchall()
            
            cursor.execute(f"""
                SELECT category, SUM(amount) as total_amount, COUNT(*) as count
                FROM expenses
                WHERE account_id IN ({placeholders})
                AND MONTH(date) = MONTH(CURDATE())
                AND YEAR(date) = YEAR(CURDATE())
                GROUP BY category
                ORDER BY total_amount DESC
            """, tuple(account_ids))
            spending_by_category = cursor.fetchall()
            
            cursor.execute(f"""
                SELECT type, SUM(amount) as total_amount, COUNT(*) as count
                FROM transactions
                WHERE account_id IN ({placeholders})
                AND MONTH(date) = MONTH(CURDATE())
                AND YEAR(date) = YEAR(CURDATE())
                GROUP BY type
            """, tuple(account_ids))
            monthly_transaction_summary = cursor.fetchall()
            
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
            return {}
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
    
    def analyze_spending_patterns(self, financial_data, is_followup=False):
        """Analyze user's spending patterns from real database data. No demo or hardcoded numbers."""
        if not financial_data:
            return "No financial activity recorded yet."
        spending_data = financial_data.get('spending_by_category', []) or []
        expenses = financial_data.get('expenses', []) or []
        transactions = financial_data.get('transactions', []) or []
        
        total_spent = sum(item.get('total_amount', 0) for item in spending_data) if spending_data else 0
        if total_spent == 0 and not expenses:
            return "No financial activity recorded yet."
        
        recent_expenses = expenses[:10] if expenses else []
        
        # Lead with the direct answer from real data only
        if spending_data:
            top_category = max(spending_data, key=lambda x: x.get('total_amount', 0))
            lead = f"So you're spending about ₹{total_spent:,} this month — most of it goes to **{top_category.get('category', 'Other')}** (₹{top_category.get('total_amount', 0):,})."
        else:
            lead = f"You've got {len(expenses)} expenses logged; total around ₹{total_spent:,}."
        
        analysis = lead + "\n\n"
        analysis += f"**Quick numbers:** Monthly spending ₹{total_spent:,}, {len(expenses)} expenses, {len(transactions)} transactions.\n\n"
        
        if spending_data:
            analysis += "**By category:**\n"
            for item in spending_data[:5]:
                pct = (item['total_amount'] / total_spent) * 100 if total_spent > 0 else 0
                analysis += f"• {item['category']}: ₹{item['total_amount']:,} ({pct:.1f}%)\n"
        
        if recent_expenses:
            analysis += "\n**Recent stuff:**\n"
            for i, expense in enumerate(recent_expenses[:5], 1):
                analysis += f"{i}. {expense['title']} — ₹{expense['amount']:,} ({expense.get('category', 'Other')})\n"
        
        analysis += "\nI can suggest where to cut back or help with a budget plan if you want."
        return analysis.strip()
    
    def get_savings_recommendations(self, financial_data, is_followup=False):
        """Provide savings recommendations based on spending patterns. No demo data."""
        if not financial_data:
            return "No financial activity recorded yet."
        spending_data = financial_data.get('spending_by_category', []) or []
        accounts = financial_data.get('accounts', []) or []
        
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
        
        # Answer first: rate and net
        recommendations = f"So your savings rate is around {savings_rate:.1f}% — income ₹{total_income:,}, expenses ₹{total_expenses:,}, so you're left with about ₹{net_savings:,}.\n\n"
        
        if savings_rate < 20:
            recommendations += """**What I'd do:** Try to get to at least 20% savings. Track daily expenses so you see where it goes, automate a transfer to savings so you don't have to think about it, and cut back a bit on fun stuff if you can. Building 3–6 months of expenses as an emergency fund is a solid next step. Want tips on any of these?"""
        else:
            recommendations += """**You're doing well.** Next I'd think about putting that extra to work — investments, maybe a mix of equity and debt, and tax-saving stuff like ELSS. We can go through options for your profile if you want."""
        
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
            'budget': "",  # already ends with "I can suggest where to cut back or help with a budget plan"
            'savings': "\n\nWant to talk investments or building an emergency fund next?",
            'investment': "\n\nI can go into specific investment types or stocks, or look at your portfolio.",
            'stock': "\n\nI can give more detail on any of these or help with strategy.",
            'balance': "\n\nWe could look at savings next, or investments, or debt — up to you."
        }
        if topic in transitions:
            response += transitions[topic]
        return response

    def _humanize(self, response, topic=None, is_greeting=False, is_thanks=False, is_help=False, is_clarify=False):
        """Make the bot sound more human: varied openers, direct tone, natural closings."""
        if not response or len(response) < 10:
            return response
        # Don't double-wrap if we already have a strong opener
        first_lower = response[:60].lower()
        skip_opener = any(x in first_lower for x in [
            "good question", "so you're", "yeah so", "sure —", "okay so", "here's the thing",
            "honestly", "the short answer", "hey!", "hey ", "hi there", "hi ", "hello!", "you're welcome",
            "anytime", "no problem", "glad i could", "i'd love to help"
        ])
        if not skip_opener:
            opener = random.choice(ACKNOWLEDGMENTS)
            if is_greeting and GREETING_VARIANTS:
                opener = random.choice(GREETING_VARIANTS)
            elif is_thanks and THANKS_RESPONSES:
                return random.choice(THANKS_RESPONSES) + " " + response
            elif is_help and HELP_OPENERS:
                opener = random.choice(HELP_OPENERS)
            elif is_clarify and CLARIFY_OPENERS:
                opener = random.choice(CLARIFY_OPENERS)
            if opener:
                response = opener + response.lstrip()
        # Add a natural closing sometimes (not for very long or list-heavy replies)
        if topic and random.random() < 0.5 and response.count("\n") < 12:
            closing = random.choice(CLOSINGS)
            if closing and not response.strip().endswith("?"):
                response = response.rstrip() + closing
        return response
    
    def process_message(self, message, user_id, user_mode='professional', profile_data=None, chat_history=None):
        """Process user message and generate appropriate response with conversational flow"""
        message_lower = message.lower().strip()
        
        # Get conversation context
        context = self._get_conversation_context(user_id, chat_history)
        is_followup = self._detect_followup(message_lower, context, chat_history)
        
        # Get user's financial data
        financial_data = self.get_user_financial_data(user_id)

        data_values = [v for v in (financial_data or {}).values() if isinstance(v, (list, dict))]
        if not financial_data or (not data_values or all(not x for x in data_values)):
            return (
                "I couldn't find any financial data linked to your account yet. "
                "Please add accounts or transactions first so I can analyze your finances."
            )

        # Intent-based context: gold/stock get real-time data; else use financial_data
        context_data = dict(financial_data) if financial_data else {}
        if "gold" in message_lower:
            gold_price = self.get_gold_price()
            context_data["gold_price_usd"] = gold_price
            ollama_response = self.ollama_financial_agent(message, context_data)
            if ollama_response:
                return ollama_response
        elif "stock" in message_lower:
            symbol = None
            ticker_match = re.search(r"\b([A-Za-z]{2,5}(?:\.NS|\.BO)?)\b", message)
            if ticker_match:
                symbol = ticker_match.group(1).upper()
            if not symbol and any(t in message_lower for t in ["reliance", "tata", "infosys", "hdfc", "icici"]):
                mapping = {"reliance": "RELIANCE.NS", "tata": "TATASTEEL.NS", "infosys": "INFY.NS", "hdfc": "HDFCBANK.NS", "icici": "ICICIBANK.NS"}
                for name, sym in mapping.items():
                    if name in message_lower:
                        symbol = sym
                        break
            price = self.get_stock_price(symbol) if symbol else None
            context_data["stock_symbol"] = symbol
            context_data["stock_price"] = price
            ollama_response = self.ollama_financial_agent(message, context_data)
            if ollama_response:
                return ollama_response
        else:
            ollama_response = self.ollama_financial_agent(message, context_data)
            if ollama_response:
                return ollama_response

        # --- Keyword routing fallback (when Ollama is offline or returns None) ---
        # Don't treat "how much did I spend" as casual_how — only when message looks like small talk
        casual_phrases = [
            'how you doing', 'how are you', 'how do you do', "how's it going", "how r u",
            "what's up", 'whats up', 'how ya doing', 'you good', 'doing good', 'doing well',
            'how have you been', 'how is it going', ' wbu', 'and you', 'sup '
        ]
        finance_in_message = any(w in message_lower for w in ['spend', 'save', 'budget', 'expense', 'stock', 'balance', 'money', 'invest', 'loan', 'transaction'])
        casual_how = any(p in message_lower for p in casual_phrases) and not finance_in_message
        if casual_how:
            self._update_context(user_id, state='greeting')
            name = (profile_data.get('Name', '') or '').strip() if profile_data else ''
            first_name = name.split()[0] if name else ''
            short = random.choice(["I'm good, thanks! What can I help you with?", "Doing well! Need anything?", "All good here. What do you want to look at?"])
            return f"Hey {first_name}! {short}" if first_name else short

        # Greeting only when message is *just* a greeting (or short) — don't treat "hi show my budget" as greeting
        has_greeting_word = any(w in message_lower for w in ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening'])
        finance_words = ['budget', 'spending', 'expense', 'expenses', 'spend', 'save', 'savings', 'invest', 'stock', 'balance', 'transaction', 'loan', 'insurance', 'card', 'money', 'portfolio', 'help']
        has_finance_intent = any(w in message_lower for w in finance_words)
        short_greetings = ('hello', 'hi', 'hey', 'hiya', 'heya', 'good morning', 'good afternoon', 'good evening')
        is_just_greeting = message_lower.strip() in short_greetings or message_lower.strip().rstrip('!?.') in short_greetings
        treat_as_greeting = has_greeting_word and (is_just_greeting or (len(message_lower) <= 20 and not has_finance_intent))
        if treat_as_greeting:
            self._update_context(user_id, state='greeting')
            name = (profile_data.get('Name', '') or '').strip() if profile_data else ''
            first_name = name.split()[0] if name else ''
            if is_just_greeting:
                short = random.choice(["What can I help you with?", "Need anything?", "What do you want to look at?"])
                full = f"Hey {first_name}! {short}" if first_name else (random.choice(["Hey! ", "Hi! "]) + short)
            else:
                ask = "What do you want to look at? Budget, savings, stocks, loans — just ask."
                full = f"Hey {first_name}! I'm here to help with your money. {ask}" if first_name else (random.choice(["Hey! ", "Hi! "]) + f"I'm here to help with your money. {ask}")
            return self._humanize(full, is_greeting=True)

        if any(word in message_lower for word in ['thank', 'thanks', 'appreciate', 'grateful']):
            self._update_context(user_id, state='active')
            return random.choice(THANKS_RESPONSES) + " If you think of anything else, just ask."

        # --- NN intent disabled: use keyword routing only so intent is reliable ---
        intent = None  # get_intent(message) if get_intent else None
        if intent and intent not in ("clarify", "greeting", "casual_how", "thanks"):
            name = (profile_data.get('Name', '') or '').strip() if profile_data else ''
            first_name = name.split()[0] if name else ''
            if intent == "budget":
                self._update_context(user_id, topic='budget', response_type='analysis', state='active')
                response = self.analyze_spending_patterns(financial_data, is_followup)
                response = self._add_conversational_transition(response, 'budget', context)
                return self._humanize(response, topic='budget')
            if intent == "savings":
                self._update_context(user_id, topic='savings', response_type='recommendations', state='active')
                response = self.get_savings_recommendations(financial_data, is_followup)
                response = self._add_conversational_transition(response, 'savings', context)
                return self._humanize(response, topic='savings')
            if intent == "investment":
                self._update_context(user_id, topic='investment', response_type='advice', state='active')
                advice = self.get_investment_advice(user_mode)
                response = f"{advice}\n\nWant to see your current investments? Just ask me to look at your portfolio."
                return self._humanize(response, topic='investment')
            if intent == "stock":
                self._update_context(user_id, topic='stock', response_type='recommendations', state='active')
                price_match = re.search(r'under\s+(\d+)', message_lower)
                count_match = re.search(r'(\d+)\s+stocks?', message_lower)
                price_limit = int(price_match.group(1)) if price_match else 500
                count = int(count_match.group(1)) if count_match else 10
                response = self.get_stock_recommendations(price_limit, count)
                response = response + "\n\nI can go deeper on any of these or help with strategy if you want."
                return self._humanize(response, topic='stock')
            if intent == "transactions":
                self._update_context(user_id, topic='transactions', response_type='analysis', state='active')
                response = self.get_recent_transactions_analysis(financial_data, is_followup)
                response = response + "\n\nWant to dig into spending patterns? Just ask about your budget."
                return self._humanize(response, topic='budget')
            if intent == "balance":
                self._update_context(user_id, topic='balance', response_type='analysis', state='active')
                response = self.get_account_balance_analysis(financial_data)
                response = self._add_conversational_transition(response, 'balance', context)
                return self._humanize(response, topic='balance')
            if intent == "loans":
                self._update_context(user_id, topic='loans', response_type='analysis', state='active')
                response = self.get_loan_analysis(financial_data)
                response = response + "\n\nWant help with a payoff plan? I can suggest strategies."
                return self._humanize(response, topic='loans')
            if intent == "insurance":
                self._update_context(user_id, topic='insurance', response_type='analysis', state='active')
                response = self.get_insurance_analysis(financial_data)
                response = response + "\n\nQuestions about coverage or comparing policies? Just ask."
                return self._humanize(response, topic='insurance')
            if intent == "cards":
                self._update_context(user_id, topic='cards', response_type='analysis', state='active')
                response = self.get_card_analysis(financial_data)
                response = response + "\n\nI can help with utilization tips or rewards too."
                return self._humanize(response, topic='cards')
            if intent == "help":
                self._update_context(user_id, state='help')
                help_text = random.choice(HELP_OPENERS) + "I can help with: budget and spending, savings tips, investments, stocks under a price, loans, cards, insurance, balance. Just ask in your own words. What do you want to look at?"
                return self._humanize(help_text, is_help=True)
            if intent == "thanks":
                self._update_context(user_id, state='active')
                return random.choice(THANKS_RESPONSES) + " If you think of anything else, just ask."

        # Fallback: keyword-based routing (when NN not used or low confidence)
        # Handle follow-up questions
        if is_followup and context['current_topic']:
            if context['current_topic'] == 'budget':
                r = self.analyze_spending_patterns(financial_data, is_followup=True)
                return self._humanize(r, topic='budget')
            elif context['current_topic'] == 'savings':
                r = self.get_savings_recommendations(financial_data, is_followup=True)
                return self._humanize(r, topic='savings')
            elif context['current_topic'] == 'investment':
                advice = self.get_investment_advice(user_mode)
                r = f"Sure, so on investments — here's the deal:\n\n{advice}\n\nWant to talk specific types or your current portfolio?"
                return self._humanize(r, topic='investment')
            elif context['current_topic'] == 'stock':
                return random.choice([
                    "Sure — what price range are you thinking? Try something like 'Show me stocks under 500'.",
                    "Happy to. Just tell me the max price, e.g. 'stocks under 500'.",
                ])
        
        # Route to appropriate handler with context tracking (order matters: more specific first)
        if any(word in message_lower for word in ['budget', 'spending', 'expense', 'expenses', 'expences', 'spend', 'money spent', 'where did my money go', 'this month', 'monthly expense', 'how much did i spend', 'where is my money going', 'expense report', 'my spending']):
            self._update_context(user_id, topic='budget', response_type='analysis', state='active')
            response = self.analyze_spending_patterns(financial_data, is_followup)
            response = self._add_conversational_transition(response, 'budget', context)
            return self._humanize(response, topic='budget')
        
        elif any(word in message_lower for word in ['save', 'saving', 'savings', 'save money', 'how to save', 'improve savings']):
            self._update_context(user_id, topic='savings', response_type='recommendations', state='active')
            response = self.get_savings_recommendations(financial_data, is_followup)
            response = self._add_conversational_transition(response, 'savings', context)
            return self._humanize(response, topic='savings')
        
        elif any(word in message_lower for word in ['invest', 'investment', 'portfolio', 'mutual fund', 'sip', 'where should i invest']):
            self._update_context(user_id, topic='investment', response_type='advice', state='active')
            advice = self.get_investment_advice(user_mode)
            response = f"{advice}\n\nWant to see your current investments? Just ask me to look at your portfolio."
            return self._humanize(response, topic='investment')
        
        elif any(word in message_lower for word in ['stock', 'stocks', 'share', 'shares', 'equity']):
            self._update_context(user_id, topic='stock', response_type='recommendations', state='active')
            price_match = re.search(r'under\s+(\d+)', message_lower)
            count_match = re.search(r'(\d+)\s+stocks?', message_lower)
            price_limit = int(price_match.group(1)) if price_match else 500
            count = int(count_match.group(1)) if count_match else 10
            response = self.get_stock_recommendations(price_limit, count)
            response = response + "\n\nI can go deeper on any of these or help with strategy if you want."
            return self._humanize(response, topic='stock')
        
        elif any(word in message_lower for word in ['transaction', 'transactions', 'recent', 'history', 'activity', 'what did i buy']):
            self._update_context(user_id, topic='transactions', response_type='analysis', state='active')
            response = self.get_recent_transactions_analysis(financial_data, is_followup)
            response = response + "\n\nWant to dig into spending patterns? Just ask about your budget."
            return self._humanize(response, topic='budget')
        
        elif any(word in message_lower for word in ['balance', 'account', 'accounts', 'money', 'funds', 'how much do i have']):
            self._update_context(user_id, topic='balance', response_type='analysis', state='active')
            response = self.get_account_balance_analysis(financial_data)
            response = self._add_conversational_transition(response, 'balance', context)
            return self._humanize(response, topic='balance')
        
        elif any(word in message_lower for word in ['loan', 'loans', 'debt', 'borrow', 'how much do i owe']):
            self._update_context(user_id, topic='loans', response_type='analysis', state='active')
            response = self.get_loan_analysis(financial_data)
            response = response + "\n\nWant help with a payoff plan? I can suggest strategies."
            return self._humanize(response, topic='loans')
        
        elif any(word in message_lower for word in ['insurance', 'policy', 'premium', 'coverage']):
            self._update_context(user_id, topic='insurance', response_type='analysis', state='active')
            response = self.get_insurance_analysis(financial_data)
            response = response + "\n\nQuestions about coverage or comparing policies? Just ask."
            return self._humanize(response, topic='insurance')
        
        elif any(word in message_lower for word in ['card', 'cards', 'credit card', 'debit card']):
            self._update_context(user_id, topic='cards', response_type='analysis', state='active')
            response = self.get_card_analysis(financial_data)
            response = response + "\n\nI can help with utilization tips or rewards too."
            return self._humanize(response, topic='cards')
        
        elif any(word in message_lower for word in ['help', 'what can you do', 'what do you do', 'capabilities']):
            self._update_context(user_id, state='help')
            help_text = (
                random.choice(HELP_OPENERS)
                + "I can help with: budget and spending, savings tips, investments, stocks under a price, "
                "loans, cards, insurance, balance — stuff like that. "
                "Just ask in your own words, e.g. 'how can I save more?' or 'analyze my spending'. "
                "What do you want to look at?"
            )
            return self._humanize(help_text, is_help=True)
        
        elif any(word in message_lower for word in ['thank', 'thanks', 'appreciate', 'grateful']):
            self._update_context(user_id, state='active')
            return random.choice(THANKS_RESPONSES) + " If you think of anything else, just ask."
        
        else:
            self._update_context(user_id, state='active')
            clarify = (
                random.choice(CLARIFY_OPENERS)
                + "For example: 'Analyze my budget', 'How can I save more?', "
                "'Show me stocks under 500', 'What's my account balance?', or 'Investment advice'. "
                "What are you curious about?"
            )
            return self._humanize(clarify, is_clarify=True)

# Initialize chatbot instance
chatbot = FinancialChatbot()

# API Routes
@chatbot_bp.route('/api/chatbot', methods=['POST'])
def chatbot_response():
    """Main chatbot endpoint"""
    try:
        data = request.json
        user_message = data.get('message', '')
        
        # Use only session user_id so we never show data when there's no connection to this user
        user_id = session.get('user_id')
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
        try:
            from flask import current_app
            current_app.logger.error("Chatbot error: %s", e, exc_info=True)
        except Exception:
            pass
        return jsonify({"response": "Sorry, something went wrong on my side — can you try again in a sec?"}), 500


@chatbot_bp.route('/api/turing_rating', methods=['POST'])
def turing_rating():
    """Accept a Turing-test style rating: how human did the chatbot feel? (1-5)"""
    try:
        data = request.json or {}
        rating = data.get('rating')
        if rating is not None:
            rating = int(rating)
            if 1 <= rating <= 5:
                # Optional: log or store for improvement
                if current_app and getattr(current_app, 'logger', None):
                    current_app.logger.info("Turing rating: %s/5", rating)
        return jsonify({"message": "Thanks for your feedback!", "received": True}), 200
    except Exception:
        return jsonify({"message": "Thanks!", "received": True}), 200


@chatbot_bp.route('/api/insights', methods=['POST'])
def get_insights():
    """Get AI insights for dashboard. Only uses real user data tied to logged-in user (session)."""
    try:
        # Use only session user_id so we never show data when there's no connection to this user
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                "response": (
                    "No financial data found for your account. "
                    "Sign in and add accounts or import data via OCR (Import menu) so I can analyze your finances and show insights here."
                )
            }), 200
        data = request.json or {}
        user_mode = data.get('user_mode', 'professional')
        profile_data = data.get('profile_data', {})
        
        financial_data = chatbot.get_user_financial_data(user_id)
        data_values = [v for v in (financial_data or {}).values() if isinstance(v, (list, dict))]
        if not financial_data or not data_values or all(not x for x in data_values):
            return jsonify({"response": "No financial data available."}), 200
        # If total expenses = 0, do not show analysis with mock numbers
        total_expenses = sum(
            item.get('total_amount', 0) for item in financial_data.get('spending_by_category', [])
        ) if financial_data.get('spending_by_category') else 0
        if total_expenses == 0:
            return jsonify({"response": "No financial activity recorded yet."}), 200
        insights = chatbot.analyze_spending_patterns(financial_data)
        return jsonify({"response": insights}), 200
        
    except Exception as e:
        return jsonify({
            "response": "Unable to load insights right now. Please try again later."
        }), 500

@chatbot_bp.route('/api/budget', methods=['POST'])
def get_budget_analysis():
    """Get budget analysis. Only for logged-in user's data."""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                "response": "Sign in and add accounts or import data via OCR to see budget analysis."
            }), 200
        data = request.json or {}
        user_mode = data.get('user_mode', 'professional')
        
        financial_data = chatbot.get_user_financial_data(user_id)
        if not financial_data:
            return jsonify({
                "response": "No financial activity recorded yet.",
                "chart_data": [],
                "summary": "No financial activity recorded yet."
            }), 200
        
        # Generate budget analysis from real data only
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
        data = request.json or {}
        user_id = session.get('user_id') or data.get('user_id')
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
