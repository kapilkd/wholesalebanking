"""
Multi-Agent LangGraph system for generating client summaries
"""
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from config.langchain_config import get_llm


class SummaryState(TypedDict):
    """State for the multi-agent summary generation"""
    client_code: str
    rm_summary: str
    asset_summary: str
    liability_summary: str
    product_holding_summary: str
    rm_discussion_summary: str


class MultiAgentSummaryGenerator:
    """Multi-agent system using LangGraph to generate client summaries"""
    
    def __init__(self):
        self.llm = get_llm(temperature=0.7)
    
    def generate_rm_summary(self, state: SummaryState) -> SummaryState:
        """Generate RM details and interactions summary"""
        client_code = state["client_code"]
        
        prompt = f"""Generate a comprehensive dummy summary about Relationship Manager (RM) details and interactions 
        for client code {client_code} at ABC Bank Wholesale Banking Department. Include:
        - RM name, designation, and contact details (ABC Bank employee)
        - Complete RM interaction history with ABC Bank Wholesale Banking context
        - CRM contents showing when the client was called and approached by ABC Bank
        - Meeting dates, call logs, and interaction notes
        - Relationship timeline with ABC Bank
        
        IMPORTANT REQUIREMENTS:
        - All monetary values must be in Indian Rupees (INR) and displayed in Crores (CR) format
        - Use format: ₹**XX.XX CR** (even values less than 1 crore should be in decimal, e.g., ₹**0.85 CR**)
        - All numbers, dates, and amounts must be formatted as **bold** using markdown (**number**)
        - Context must be ABC Bank Wholesale Banking Department
        - Make it detailed, realistic, and professional
        - Format as paragraphs with specific dates, times, and interaction details"""
        
        messages = [
            SystemMessage(content="You are a CRM data analyst at ABC Bank Wholesale Banking Department. Generate realistic dummy data for banking client interactions. Always use Indian Rupees (INR) in Crores (CR) format. Format all numbers as bold using **number** markdown syntax. Example: ₹**2.5 CR**"),
            HumanMessage(content=prompt)
        ]
        
        response = self.llm.invoke(messages)
        state["rm_summary"] = response.content
        return state
    
    def generate_asset_summary(self, state: SummaryState) -> SummaryState:
        """Generate asset base summary"""
        client_code = state["client_code"]
        
        prompt = f"""Generate a comprehensive dummy summary about asset base         for client code {client_code} at ABC Bank Wholesale Banking Department. Include:
        - Total asset value and breakdown (in Indian Rupees)
        - Asset categories (loans, investments, securities, etc.) with ABC Bank Wholesale Banking products
        - Asset quality metrics
        - Historical asset trends
        - Portfolio composition with ABC Bank context
        
        IMPORTANT REQUIREMENTS:
        - All monetary values must be in Indian Rupees (INR) and displayed in Crores (CR) format
        - Use format: ₹**XX.XX CR** (even values less than 1 crore should be in decimal, e.g., ₹**0.85 CR**)
        - All numbers, percentages, amounts, and dates must be formatted as **bold** using markdown (**number**)
        - Context must be ABC Bank Wholesale Banking Department
        - Make it detailed with specific numbers, percentages, and professional financial terminology"""
        
        messages = [
            SystemMessage(content="You are a financial analyst at ABC Bank Wholesale Banking Department specializing in asset management. Generate realistic dummy asset data. Always use Indian Rupees (INR) in Crores (CR) format. Format all numbers, percentages, and amounts as bold using **number** markdown syntax. Example: ₹**125.75 CR**"),
            HumanMessage(content=prompt)
        ]
        
        response = self.llm.invoke(messages)
        state["asset_summary"] = response.content
        return state
    
    def generate_liability_summary(self, state: SummaryState) -> SummaryState:
        """Generate liability base summary"""
        client_code = state["client_code"]
        
        prompt = f"""Generate a comprehensive dummy summary about liability base         for client code {client_code} at ABC Bank Wholesale Banking Department. Include:
        - Total liability value and breakdown (in Indian Rupees)
        - Liability categories (deposits, borrowings, bonds, etc.) with ABC Bank Wholesale Banking products
        - Liability structure and maturity profiles
        - Interest rate exposure
        - Risk metrics
        
        IMPORTANT REQUIREMENTS:
        - All monetary values must be in Indian Rupees (INR) and displayed in Crores (CR) format
        - Use format: ₹**XX.XX CR** (even values less than 1 crore should be in decimal, e.g., ₹**0.85 CR**)
        - All numbers, percentages, amounts, and dates must be formatted as **bold** using markdown (**number**)
        - Context must be ABC Bank Wholesale Banking Department
        - Make it detailed with specific numbers, percentages, and professional financial terminology"""
        
        messages = [
            SystemMessage(content="You are a financial analyst at ABC Bank Wholesale Banking Department specializing in liability management. Generate realistic dummy liability data. Always use Indian Rupees (INR) in Crores (CR) format. Format all numbers, percentages, and amounts as bold using **number** markdown syntax. Example: ₹**95.25 CR**"),
            HumanMessage(content=prompt)
        ]
        
        response = self.llm.invoke(messages)
        state["liability_summary"] = response.content
        return state
    
    def generate_product_holding_summary(self, state: SummaryState) -> SummaryState:
        """Generate overall banking and product holding summary"""
        client_code = state["client_code"]
        
        prompt = f"""Generate a comprehensive dummy summary about overall banking relationship and product holdings 
        for client code {client_code} at ABC Bank Wholesale Banking Department. Include:
        - Complete product portfolio (ABC Bank current accounts, credit facilities, trade finance, treasury products, etc.)
        - Product-wise holdings and values (in Indian Rupees - Crores)
        - Product utilization rates
        - Cross-selling opportunities with ABC Bank Wholesale Banking products
        - Banking relationship depth and breadth with ABC Bank
        
        IMPORTANT REQUIREMENTS:
        - All monetary values must be in Indian Rupees (INR) and displayed in Crores (CR) format
        - Use format: ₹**XX.XX CR** (even values less than 1 crore should be in decimal, e.g., ₹**0.85 CR**)
        - All numbers, percentages, amounts, and dates must be formatted as **bold** using markdown (**number**)
        - Context must be ABC Bank Wholesale Banking Department
        - Use ABC Bank product names where relevant
        - Make it detailed with specific product names, values, and utilization metrics"""
        
        messages = [
            SystemMessage(content="You are a product manager at ABC Bank Wholesale Banking Department analyzing client product holdings. Generate realistic dummy product data. Always use Indian Rupees (INR) in Crores (CR) format. Format all numbers, percentages, and amounts as bold using **number** markdown syntax. Example: ₹**45.50 CR**"),
            HumanMessage(content=prompt)
        ]
        
        response = self.llm.invoke(messages)
        state["product_holding_summary"] = response.content
        return state
    
    def generate_rm_discussion_summary(self, state: SummaryState) -> SummaryState:
        """Generate RM-client discussion summary"""
        client_code = state["client_code"]
        
        prompt = f"""Generate a comprehensive dummy summary of discussions between ABC Bank Relationship Manager and client {client_code} from ABC Bank Wholesale Banking Department. Include:
        - Recent conversation topics related to ABC Bank Wholesale Banking services
        - Client needs and requirements discussed
        - Proposed ABC Bank solutions and recommendations
        - Follow-up actions and commitments
        - Meeting minutes style discussion points
        - Any monetary discussions in Indian Rupees
        
        IMPORTANT REQUIREMENTS:
        - All monetary values must be in Indian Rupees (INR) with ₹ symbol
        - All numbers, percentages, amounts, and dates must be formatted as **bold** using markdown (**number**)
        - Context must be ABC Bank Wholesale Banking Department
        - Make it conversational, detailed, and realistic with specific discussion points and outcomes"""
        
        messages = [
            SystemMessage(content="You are a relationship manager at ABC Bank Wholesale Banking Department documenting client discussions. Generate realistic dummy discussion notes. Always use Indian Rupees (INR) in Crores (CR) format. Format all numbers, percentages, and amounts as bold using **number** markdown syntax. Example: ₹**12.30 CR**"),
            HumanMessage(content=prompt)
        ]
        
        response = self.llm.invoke(messages)
        state["rm_discussion_summary"] = response.content
        return state
    
    def generate_all_summaries(self, client_code: str) -> dict:
        """
        Generate all 5 summaries using LangGraph multi-agent system
        
        Args:
            client_code: APR_CLIENT_CODE to generate summaries for
        
        Returns:
            dict: Dictionary containing all 5 summaries
        """
        # Initialize state
        initial_state: SummaryState = {
            "client_code": client_code,
            "rm_summary": "",
            "asset_summary": "",
            "liability_summary": "",
            "product_holding_summary": "",
            "rm_discussion_summary": ""
        }
        
        # Create LangGraph workflow
        workflow = StateGraph(SummaryState)
        
        # Add nodes for each agent
        workflow.add_node("rm_agent", self.generate_rm_summary)
        workflow.add_node("asset_agent", self.generate_asset_summary)
        workflow.add_node("liability_agent", self.generate_liability_summary)
        workflow.add_node("product_agent", self.generate_product_holding_summary)
        workflow.add_node("discussion_agent", self.generate_rm_discussion_summary)
        
        # Define the workflow sequence (parallel execution of independent agents)
        workflow.set_entry_point("rm_agent")
        workflow.add_edge("rm_agent", "asset_agent")
        workflow.add_edge("asset_agent", "liability_agent")
        workflow.add_edge("liability_agent", "product_agent")
        workflow.add_edge("product_agent", "discussion_agent")
        workflow.add_edge("discussion_agent", END)
        
        # Compile and run the graph
        app = workflow.compile()
        final_state = app.invoke(initial_state)
        
        return {
            "rm_summary": final_state["rm_summary"],
            "asset_summary": final_state["asset_summary"],
            "liability_summary": final_state["liability_summary"],
            "product_holding_summary": final_state["product_holding_summary"],
            "rm_discussion_summary": final_state["rm_discussion_summary"]
        }
