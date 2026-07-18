"""
LangChain configuration and setup
"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# Load environment variables
load_dotenv()

def get_llm(temperature=0.7, model_name="gpt-4"):
    """
    Initialize and return OpenAI LLM instance
    
    Args:
        temperature: Sampling temperature (0-2)
        model_name: Name of the OpenAI model to use
    
    Returns:
        ChatOpenAI instance
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables. Please check your .env file.")
    
    return ChatOpenAI(
        temperature=temperature,
        model_name=model_name,
        openai_api_key=api_key
    )

def generate_wholesale_banking_summary():
    """
    Generate AI-powered summary about wholesale banking
    
    Returns:
        str: Summary text about wholesale banking
    """
    llm = get_llm(temperature=0.7)
    
    system_prompt = """You are a financial expert specializing in wholesale banking. 
    Provide a comprehensive but concise summary (3-4 paragraphs) explaining what wholesale banking is, 
    its key services, and its importance in the financial ecosystem. Make it professional and informative."""
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Please provide a summary of wholesale banking.")
    ]
    
    response = llm.invoke(messages)
    return response.content
