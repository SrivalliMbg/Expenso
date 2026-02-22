"""
Neural intent classifier for the financial chatbot.
Uses TF-IDF + MLP (multi-layer perceptron) to map user messages to intents.
Train with: python -m app.chatbot.intent_classifier
"""

import os
import json
import re

# Optional: scikit-learn for NN intent classification
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.neural_network import MLPClassifier
    from sklearn.model_selection import train_test_split
    import joblib
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

# Directory for saved model (next to this file)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODEL_DIR = os.path.join(_THIS_DIR, "models")
_MODEL_PATH = os.path.join(_MODEL_DIR, "intent_model.joblib")
_VECTORIZER_PATH = os.path.join(_MODEL_DIR, "intent_vectorizer.joblib")
_DATA_PATH = os.path.join(_THIS_DIR, "intent_data.json")

# Only use NN intent when max probability >= this (otherwise fall back to keyword routing)
CONFIDENCE_THRESHOLD = 0.55

# Intents we support (must match keys in intent_data.json)
INTENTS = [
    "greeting", "casual_how", "budget", "savings", "investment", "stock",
    "transactions", "balance", "loans", "insurance", "cards", "help", "thanks", "clarify"
]


def _normalize(text):
    """Normalize for training and prediction."""
    if not text:
        return ""
    t = text.lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t


def _load_training_data():
    """Load (texts, labels) from intent_data.json. Expand with simple variations."""
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    texts, labels = [], []
    for intent, examples in data.items():
        for ex in examples:
            ex = _normalize(ex)
            if ex:
                texts.append(ex)
                labels.append(intent)
    return texts, labels


def train(save=True):
    """Build TF-IDF + MLP on intent_data.json and optionally save."""
    if not HAS_SKLEARN:
        raise RuntimeError("Install scikit-learn to train: pip install scikit-learn")
    texts, labels = _load_training_data()
    if not texts:
        raise ValueError("No training data in intent_data.json")
    X_train, X_test, y_train, y_test = train_test_split(texts, labels, test_size=0.15, random_state=42)
    vectorizer = TfidfVectorizer(max_features=2000, ngram_range=(1, 2), min_df=1)
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)
    clf = MLPClassifier(hidden_layer_sizes=(128, 64), max_iter=500, random_state=42)
    clf.fit(X_train_vec, y_train)
    if save:
        os.makedirs(_MODEL_DIR, exist_ok=True)
        joblib.dump(clf, _MODEL_PATH)
        joblib.dump(vectorizer, _VECTORIZER_PATH)
    acc = (clf.predict(X_test_vec) == y_test).mean()
    return float(acc)


class IntentClassifier:
    """Predict intent from user message. Falls back to None if model missing or sklearn not installed."""

    def __init__(self):
        self._clf = None
        self._vectorizer = None
        if HAS_SKLEARN and os.path.isfile(_MODEL_PATH) and os.path.isfile(_VECTORIZER_PATH):
            try:
                self._clf = joblib.load(_MODEL_PATH)
                self._vectorizer = joblib.load(_VECTORIZER_PATH)
            except Exception:
                pass

    def predict(self, message):
        """
        Return intent string or None if no model / low confidence.
        When confidence is below threshold, returns None so chatbot uses keyword routing.
        """
        if self._clf is None or self._vectorizer is None:
            return None
        text = _normalize(message)
        if not text:
            return None
        try:
            X = self._vectorizer.transform([text])
            proba = self._clf.predict_proba(X)[0]
            max_prob = float(proba.max())
            if max_prob < CONFIDENCE_THRESHOLD:
                return None
            intent = self._clf.predict(X)[0]
            return str(intent)
        except Exception:
            return None


# Singleton for the app
_classifier = None


def get_intent(message):
    """Return predicted intent for message, or None."""
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier.predict(message)


if __name__ == "__main__":
    if not HAS_SKLEARN:
        print("Install scikit-learn: pip install scikit-learn")
        exit(1)
    acc = train(save=True)
    print(f"Intent model trained and saved. Test accuracy: {acc:.2%}")
    # Quick test
    ic = IntentClassifier()
    for q in ["what are my expenses this month", "hi", "how you doing", "stocks under 500"]:
        print(f"  {q!r} -> {ic.predict(q)}")
