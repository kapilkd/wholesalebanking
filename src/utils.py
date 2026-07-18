"""
Utility functions for the wholesale banking application
"""
import pandas as pd
import numpy as np

def validate_client_code(client_code: str) -> tuple[bool, str]:
    """
    Validate APR_CLIENT_CODE or RM_CODE format
    
    Args:
        client_code: The client code to validate (APR_CLIENT_CODE or RM_CODE)
    
    Returns:
        tuple: (is_valid: bool, code_type: str)
        - RM_CODE: 6 or 7 characters
        - APR_CLIENT_CODE: 8 to 14 characters
        - Invalid: less than 6 characters
    """
    if not client_code or not isinstance(client_code, str):
        return False, ""
    
    code_len = len(client_code.strip())
    
    # Invalid if less than 6 characters
    if code_len < 6:
        return False, ""
    
    # RM_CODE: 6 or 7 characters
    if code_len == 6 or code_len == 7:
        return True, "RM_CODE"
    
    # APR_CLIENT_CODE: 6 to 14 characters
    if code_len >= 8 and code_len <= 14:
        return True, "APR_CLIENT_CODE"
    
    # Invalid if more than 14 characters
    return False, ""

def format_client_code(client_code: str) -> str:
    """
    Format client code for display
    
    Args:
        client_code: The client code to format
    
    Returns:
        str: Formatted client code
    """
    return client_code.strip().upper()
