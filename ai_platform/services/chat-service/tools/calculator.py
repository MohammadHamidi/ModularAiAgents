"""
Calculator Tool - Perform mathematical calculations.
"""
from tools.registry import Tool
from dataclasses import dataclass, field
from typing import Dict, Any
import math
import re


@dataclass
class CalculatorTool(Tool):
    """Perform mathematical calculations."""
    
    name: str = "calculator"
    description: str = """Perform mathematical calculations.
    Use this when you need to calculate numbers, solve equations, or do math operations.
    Supports: +, -, *, /, ^, sqrt, sin, cos, tan, log, and more."""
    
    parameters: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Mathematical expression to evaluate (e.g., '2 + 2', 'sqrt(16)', '5^2')"
            }
        },
        "required": ["expression"]
    })
    
    async def execute(self, expression: str) -> str:
        """Execute mathematical calculation."""
        try:
            # Clean and prepare expression
            expr = expression.strip()
            
            # Convert common notations
            expr = expr.replace('^', '**')
            expr = expr.replace('×', '*')
            expr = expr.replace('÷', '/')
            
            # Add math functions
            safe_dict = {
                'sqrt': math.sqrt,
                'sin': math.sin,
                'cos': math.cos,
                'tan': math.tan,
                'log': math.log10,
                'ln': math.log,
                'abs': abs,
                'round': round,
                'pi': math.pi,
                'e': math.e,
                'pow': pow,
            }
            
            # Persian/Arabic digit conversion
            persian_digits = '۰۱۲۳۴۵۶۷۸۹'
            arabic_digits = '٠١٢٣٤٥٦٧٨٩'
            for i, (p, a) in enumerate(zip(persian_digits, arabic_digits)):
                expr = expr.replace(p, str(i))
                expr = expr.replace(a, str(i))
            
            # Validate expression (basic security)
            allowed_chars = set('0123456789+-*/().^ sqrtincoalgebdpow')
            expr_check = expr.lower().replace(' ', '')
            if not all(c in allowed_chars for c in expr_check):
                return f"[Calculator] Error: Invalid characters in expression"
            
            # Evaluate
            result = eval(expr, {"__builtins__": {}}, safe_dict)
            
            # Format result
            if isinstance(result, float):
                if result == int(result):
                    result = int(result)
                else:
                    result = round(result, 6)
            
            return f"[Calculator] {expression} = {result}"
            
        except ZeroDivisionError:
            return "[Calculator] Error: Division by zero"
        except Exception as e:
            return f"[Calculator] Error: Could not evaluate '{expression}' - {str(e)}"

