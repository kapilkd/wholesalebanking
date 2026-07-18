"""
Chatbot implementation using LangChain and LangGraph
"""
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from config.langchain_config import get_llm

class WholesaleBankingChatbot:
    """
    Chatbot class for wholesale banking queries
    """
    
    def __init__(self, client_code: str = None):
        """
        Initialize the chatbot
        
        Args:
            client_code: Optional APR_CLIENT_CODE for context
        """
        self.client_code = client_code
        self.llm = get_llm(temperature=0.7)
        self.conversation_history: List[Dict[str, str]] = []
        
        # System prompt for wholesale banking context
        self.system_prompt = """You are an AI assistant specialized in ABC Bank Wholesale Banking services.
        You help clients understand ABC Bank wholesale banking products, services, and solutions.
        Provide accurate, professional, and helpful information about:
        - ABC Bank corporate banking services
        - ABC Bank trade finance
        - ABC Bank cash management
        - ABC Bank foreign exchange services
        - ABC Bank credit facilities
        - ABC Bank investment banking services
        
        Always use Indian Rupees (INR) with ₹ symbol for any monetary values.
        Be concise, clear, and professional in your responses."""
        
        if client_code:
            self.system_prompt += f"\n\nCurrent client context: APR_CLIENT_CODE = {client_code}"
    
    def get_response(self, user_input: str) -> str:
        """
        Get chatbot response for user input
        
        Args:
            user_input: User's message/query
        
        Returns:
            str: Chatbot's response
        """
        # Build messages list
        messages = [SystemMessage(content=self.system_prompt)]
        
        # Add conversation history
        for entry in self.conversation_history[-5:]:  # Keep last 5 exchanges for context
            messages.append(HumanMessage(content=entry["user"]))
            messages.append(AIMessage(content=entry["assistant"]))
        
        # Add current user message
        messages.append(HumanMessage(content=user_input))
        
        # Get response from LLM
        response = self.llm.invoke(messages)
        response_text = response.content
        
        # Update conversation history
        self.conversation_history.append({
            "user": user_input,
            "assistant": response_text
        })
        
        return response_text
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
    
    def update_client_code(self, client_code: str):
        """
        Update the client code context
        
        Args:
            client_code: New APR_CLIENT_CODE
        """
        self.client_code = client_code
        self.system_prompt = """You are an AI assistant specialized in ABC Bank Wholesale Banking services.
        You help clients understand ABC Bank wholesale banking products, services, and solutions.
        Provide accurate, professional, and helpful information about:
        - ABC Bank corporate banking services
        - ABC Bank trade finance
        - ABC Bank cash management
        - ABC Bank foreign exchange services
        - ABC Bank credit facilities
        - ABC Bank investment banking services
        
        Always use Indian Rupees (INR) with ₹ symbol for any monetary values.
        Be concise, clear, and professional in your responses."""
        
        if client_code:
            self.system_prompt += f"\n\nCurrent client context: APR_CLIENT_CODE = {client_code}"
