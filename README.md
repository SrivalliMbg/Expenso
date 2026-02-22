# Expenso - AI Financial Assistant

A comprehensive financial management application with integrated AI chatbot for personalized financial guidance.

## Features

- **Dashboard**: Overview of financial status with charts and statistics
- **Accounts Management**: Track multiple bank accounts, credit cards, and digital wallets
- **Expense Tracking**: Categorize and analyze spending patterns
- **Transaction History**: View recent financial activities
- **AI Financial Assistant**: Get personalized financial advice and insights
- **Stock Analysis**: Get real-time stock recommendations
- **Budget Analysis**: AI-powered budget insights and recommendations

## AI Chatbot Features

- **Personalized Financial Guidance**: Get advice based on your financial data
- **Budget Analysis**: AI-powered insights into spending patterns
- **Stock Recommendations**: Real-time stock suggestions under specified price limits
- **Quick Actions**: Pre-built questions for common financial queries
- **Chat History**: Persistent conversation history
- **Professional/Student Modes**: Tailored responses based on user expertise level

## Installation

### Prerequisites

- Python 3.8 or higher
- MySQL database
- Hugging Face account (for AI model access)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Expenso
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   - Copy `config.py.example` to `config.py`
   - Update database credentials and Hugging Face token

4. **Set up database**
   ```sql
   CREATE DATABASE expenso;
   USE expenso;
   -- Run the SQL schema provided in the database folder
   ```

5. **Run the application**
   ```bash
   python run.py
   ```

## AI Model Setup

The chatbot uses Google's Gemma-2B-IT model for financial advice. To use the AI features:

1. **Get Hugging Face Token**
   - Sign up at [Hugging Face](https://huggingface.co/)
   - Accept the Gemma model terms
   - Generate an access token

2. **Update Configuration**
   - Add your Hugging Face token to `config.py`
   - The model will be downloaded automatically on first use

## Usage

### Dashboard
- View financial overview and statistics
- Access AI insights in the bottom section
- Use the chatbot for personalized advice

### Chatbot
- Click the chat button (💬) to open the AI assistant
- Ask questions about your finances, budgeting, or investments
- Use quick action buttons for common queries
- Get real-time stock recommendations

### Quick Actions
- **💡 Savings Tips**: Get personalized savings advice
- **📈 Stock Ideas**: Find stocks under specific price limits
- **💰 Budget Analysis**: Get AI-powered budget insights

## API Endpoints

### Chatbot APIs
- `POST /api/chatbot` - Main chatbot interface
- `POST /api/guidance` - Get financial guidance
- `POST /api/budget` - Budget analysis
- `POST /api/insights` - Financial insights

### Example Usage
```javascript
// Send a message to the chatbot
fetch('/api/chatbot', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        user_id: 'user123',
        message: 'How can I improve my savings?',
        user_mode: 'professional'
    })
})
.then(response => response.json())
.then(data => console.log(data.response));
```

## Deployment (Render + GitHub Actions)

### How automation works

1. **Push to `main`** triggers the GitHub Actions workflow (`.github/workflows/deploy.yml`).
2. The workflow **validates** the project: installs dependencies, runs `python -c "import app"`, and builds the Docker image to ensure the Dockerfile is valid.
3. If all steps pass, it **calls the Render deploy hook** (POST request to the URL you configure). Render then builds and deploys from the connected GitHub repo.
4. No manual steps are required after the initial setup (connect repo on Render, add the deploy hook secret in GitHub).

### GitHub Secrets

1. In your GitHub repo go to **Settings → Secrets and variables → Actions**.
2. Add a **Repository secret**:
   - **Name:** `RENDER_DEPLOY_HOOK`
   - **Value:** the full deploy hook URL from Render (see below).

Without this secret, the workflow still runs validation but skips the deploy trigger.

### Render deploy hook

1. In [Render](https://render.com), open your **Web Service** (or create one connected to this repo).
2. Go to **Settings → Deploy Hook**.
3. Copy the **Deploy Hook URL** (e.g. `https://api.render.com/deploy/srv/...?key=...`).
4. Paste this URL as the value of the `RENDER_DEPLOY_HOOK` secret in GitHub (see above).

On each push to `main`, GitHub Actions will POST to this URL so Render starts a new deploy.

### Environment variables on Render

Set these in the Render service **Environment** tab:

- **Required:** `DATABASE_URL` (MySQL connection URL, e.g. `mysql://user:pass@host:3306/db`) or use `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`.
- **Required:** `SECRET_KEY` (Flask secret key; use a long random string in production).
- **Optional:** `DEMO_MODE` — set to `True` to allow copying synthetic transaction data between users in demo setups; default is `False`.
- **Production defaults** (can override): `FLASK_ENV=production`, `DEBUG=False`.

Render sets `PORT` at runtime; the Dockerfile uses it for gunicorn.

---

## Configuration

### Environment Variables
- `MYSQL_HOST` - Database host (or use `DATABASE_URL`)
- `MYSQL_USER` - Database username
- `MYSQL_PASSWORD` - Database password
- `MYSQL_DB` - Database name
- `DATABASE_URL` - Full MySQL URL (overrides MYSQL_* when set; used on Render)
- `SECRET_KEY` - Flask secret key (required in production)
- `DEMO_MODE` - Optional; `True`/`False` for demo seed behavior
- `HF_TOKEN` - Hugging Face access token

### Model Configuration
The AI model uses 8-bit quantization for efficient inference. You can modify the model settings in `app/chatbot.py`:

```python
bnb_config = BitsAndBytesConfig(
    load_in_8bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16
)
```

## Troubleshooting

### Common Issues

1. **Model Loading Error**
   - Ensure you have sufficient RAM (8GB+ recommended)
   - Check your Hugging Face token is valid
   - Verify internet connection for model download

2. **Database Connection**
   - Verify MySQL is running
   - Check database credentials in config.py
   - Ensure database schema is properly set up

3. **Stock Data Issues**
   - yfinance requires internet connection
   - Some stock symbols may be temporarily unavailable

### Performance Optimization

- The AI model is loaded lazily (only when first used)
- Chat history is limited to 20 messages to prevent memory issues
- Stock data is cached to reduce API calls

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review the API documentation
