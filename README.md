# Wholesale Banking Chatbot Application

A Streamlit-based chatbot application for wholesale banking services, powered by LangChain, LangGraph, and OpenAI.

## Features

- **Client Code Input**: Submit APR_CLIENT_CODE via input box in the left panel
- **Wholesale Banking Information**: Display AI-generated summary about wholesale banking
- **Interactive Chatbot**: Powered by LangChain and OpenAI GPT models

## Technologies Used

- **Streamlit**: Web application framework
- **LangChain**: LLM application framework
- **LangGraph**: State management for LangChain
- **LangSmith**: Monitoring and observability
- **Plotly**: Interactive visualizations
- **Pandas & NumPy**: Data manipulation
- **OpenAI**: GPT models for chatbot functionality
- **Python-dotenv**: Environment variable management

## Setup Instructions

1. **Clone or navigate to the project directory**
   ```bash
   cd Wholesale_banking
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   - Copy `.env.example` to `.env`
   - Add your OpenAI API key to `.env`
   ```bash
   cp .env.example .env
   # Then edit .env and add your OPENAI_API_KEY
   ```

4. **Run the application**
   ```bash
   streamlit run app.py
   ```

## Project Structure

```
Wholesale_banking/
├── app.py                 # Main Streamlit application
├── config/
│   └── langchain_config.py  # LangChain configuration
├── src/
│   ├── chatbot.py        # Chatbot logic using LangChain/LangGraph
│   └── utils.py          # Utility functions
├── .env                  # Environment variables (not in git)
├── .env.example          # Example environment file
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Usage

1. Launch the application using `streamlit run app.py`
2. Enter an APR_CLIENT_CODE in the left panel input box
3. View wholesale banking information and interact with the chatbot in the right panel
