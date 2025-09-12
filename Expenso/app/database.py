import pandas as pd

# Mock user data storage
user_data_store = {}

def get_user_data(user_id):
    """Get user's financial data"""
    return user_data_store.get(user_id, {})

def add_user_data(user_id, data_type, data):
    """Add user's financial data"""
    if user_id not in user_data_store:
        user_data_store[user_id] = {}
    user_data_store[user_id][data_type] = data
    return True