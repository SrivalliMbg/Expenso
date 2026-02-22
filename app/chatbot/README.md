# Chatbot and intent classifier

## NN intent classifier

The chatbot uses a small **neural intent classifier** (TF-IDF + MLP) so queries like "what are my expenses this month" or "how you doing" get the correct reply instead of the generic greeting.

- **Model**: `app/chatbot/models/intent_model.joblib` and `intent_vectorizer.joblib`
- **Training data**: `app/chatbot/intent_data.json` (intent → list of example phrases)

### Train the model (first time or after adding examples)

```bash
pip install scikit-learn joblib
python -m app.chatbot.intent_classifier
```

Run from the project root (`Expenso_final`). This saves the model under `app/chatbot/models/`. If the model is missing, the chatbot falls back to keyword-based routing (with fallbacks for "expences", "this month", etc.).

### Add more examples

Edit `intent_data.json`: add more phrases under the right intent (e.g. under `budget` add "show spending for January"). Then run the train command again.
