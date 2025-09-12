#!/usr/bin/env python3
"""
Test script for the financial chatbot
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.chatbot.financial_chatbot import FinancialChatbot

def test_chatbot():
    """Test the chatbot functionality"""
    print("🤖 Testing Financial Chatbot...")
    
    # Initialize chatbot
    chatbot = FinancialChatbot()
    
    # Test cases
    test_cases = [
        "Hello",
        "Analyze my budget",
        "How can I save more money?",
        "Show me stocks under 500",
        "Investment advice for students",
        "What can you help me with?"
    ]
    
    for i, message in enumerate(test_cases, 1):
        print(f"\n--- Test {i}: '{message}' ---")
        try:
            response = chatbot.process_message(message, "test_user", "professional")
            print(f"Response: {response[:200]}...")
        except Exception as e:
            print(f"Error: {e}")
    
    print("\n✅ Chatbot testing completed!")

if __name__ == "__main__":
    test_chatbot()
