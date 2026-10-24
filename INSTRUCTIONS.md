# How to Run

**You need:** Python 3.11 or newer.

## 1. Open a terminal in this folder

```
cd QuickCart_Case_Study
```

## 2. Create an environment and install packages

Windows:
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS / Linux:
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. (Optional) Add a Groq API key for the chatbot

The chatbot works without a key, using keyword matching. To use AI for understanding questions,
get a free key at https://console.groq.com, then create `.streamlit/secrets.toml` containing:

```
GROQ_API_KEY = "your-key-here"
```

## 4. Start the app

```
streamlit run dashboard.py
```

It opens at http://localhost:8501.

- **Admin View** (default): the leadership dashboard.
- **Customer View** (switch at top right): sign in with a demo customer and chat with the help assistant.

## Optional: re-run the data cleaning

The cleaned data is already included. To rebuild it from `data/raw/`:

```
python clean_data.py
python audit_cleaning_log.py
```

The second command checks that every number in the cleaning log matches the clean data.
