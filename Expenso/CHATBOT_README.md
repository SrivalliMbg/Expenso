# 🤖 Expenso Financial Chatbot

## Overview

The Expenso Financial Chatbot is an AI-powered assistant integrated into the Expenso financial management application. It provides personalized financial advice, budget analysis, investment recommendations, and stock suggestions based on user data and preferences.

## Features

### 💰 Financial Analysis
- **Budget Analysis**: Analyzes spending patterns and provides insights
- **Savings Recommendations**: Personalized tips to improve savings rate
- **Spending Insights**: Identifies top spending categories and trends
- **Financial Health**: Calculates savings rate and provides recommendations

### 📈 Investment Guidance
- **Investment Advice**: Tailored recommendations based on user profile (student/professional)
- **Stock Recommendations**: Finds Indian stocks under specific price limits
- **Portfolio Suggestions**: Asset allocation and diversification advice
- **Tax-Saving Investments**: ELSS, PPF, NPS recommendations

### 🎯 Personalized Assistance
- **User Context**: Considers user's financial data from database
- **Profile-Based**: Different advice for students vs professionals
- **Real-time Data**: Integrates with live financial data
- **Interactive Chat**: Natural conversation interface

## Architecture

### Backend Structure
```
app/chatbot/
├── __init__.py
└── financial_chatbot.py    # Main chatbot implementation
```

### Key Components

1. **FinancialChatbot Class**: Core chatbot logic
2. **Database Integration**: Fetches real user financial data
3. **API Endpoints**: RESTful endpoints for frontend integration
4. **Response Generation**: Intelligent response based on user queries

### API Endpoints

- `POST /api/chatbot` - Main chatbot conversation endpoint
- `POST /api/insights` - Get AI insights for dashboard
- `POST /api/budget` - Budget analysis with chart data
- `POST /api/guidance` - General financial guidance

## Usage

### Frontend Integration

The chatbot is integrated into the home dashboard with:

```javascript
// Initialize chatbot
initChatbot();

// Send message
fetch('/api/chatbot', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        user_id: user.id,
        message: userMessage,
        user_mode: user.status,
        profile_data: profileData
    })
});
```

### Backend Usage

```python
from app.chatbot.financial_chatbot import FinancialChatbot

# Initialize chatbot
chatbot = FinancialChatbot()

# Process message
response = chatbot.process_message(
    message="Analyze my budget",
    user_id="user123",
    user_mode="professional"
)
```

## Supported Queries

### Budget & Spending
- "Analyze my budget"
- "Show my spending patterns"
- "What are my top expenses?"
- "How much did I spend this month?"

### Savings & Investments
- "How can I save more money?"
- "Investment advice for students"
- "What should I invest in?"
- "Portfolio recommendations"

### Stock Market
- "Show me stocks under 500"
- "Find stocks under 1000"
- "Top 5 stocks under 200"
- "Stock recommendations"

### General Help
- "Hello" / "Hi"
- "What can you help me with?"
- "Help"
- "Financial guidance"

## Data Integration

### Database Tables Used
- `users` - User profile information
- `accounts` - Account balances and types
- `transactions` - Transaction history and categories

### Mock Data Fallback
When database is unavailable, the chatbot uses realistic mock data for demonstration purposes.

## Configuration

### Dependencies
- Flask - Web framework
- pandas - Data manipulation
- numpy - Numerical operations
- yfinance - Stock market data
- mysql-connector-python - Database connectivity

### Environment Variables
- Database connection settings in `config.py`
- User session management
- API rate limiting (if needed)

## Testing

Run the test script to verify chatbot functionality:

```bash
python test_chatbot.py
```

## Customization

### Adding New Features

1. **New Query Types**: Add pattern matching in `process_message()`
2. **New Data Sources**: Extend `get_user_financial_data()`
3. **New Response Types**: Add methods to `FinancialChatbot` class
4. **New API Endpoints**: Add routes to `chatbot_bp` blueprint

### Styling

Chatbot styling is defined in `static/CSS/home.css` under the "Chatbot Styling" section.

## Performance Considerations

- **Database Queries**: Optimized with proper indexing
- **Response Caching**: Consider implementing for frequently asked questions
- **Rate Limiting**: Implement if needed for production
- **Error Handling**: Graceful fallbacks for all operations

## Security

- **Input Validation**: All user inputs are validated
- **SQL Injection**: Protected with parameterized queries
- **User Data**: Respects user privacy and data protection
- **Session Management**: Secure user session handling

## Future Enhancements

1. **Machine Learning**: Implement ML models for better predictions
2. **Voice Interface**: Add speech-to-text capabilities
3. **Multi-language**: Support for multiple languages
4. **Advanced Analytics**: More sophisticated financial analysis
5. **Integration**: Connect with external financial APIs

## Troubleshooting

### Common Issues

1. **Database Connection**: Check MySQL connection settings
2. **Stock Data**: Verify yfinance API availability
3. **Frontend Integration**: Check JavaScript console for errors
4. **Response Formatting**: Verify message formatting functions

### Debug Mode

Enable debug mode in Flask app for detailed error logging:

```python
app.run(debug=True)
```

## Contributing

1. Follow the existing code structure
2. Add proper error handling
3. Include docstrings for new functions
4. Test new features thoroughly
5. Update this README for new features

## License

This chatbot is part of the Expenso application and follows the same licensing terms.
