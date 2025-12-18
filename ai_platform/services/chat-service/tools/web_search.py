"""
Web Search Tool - Search the web for information.
This is a MOCK implementation - replace with real search API later.
"""
from tools.registry import Tool
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class WebSearchTool(Tool):
    """Search the web for information."""
    
    name: str = "web_search"
    description: str = """Search the web for current information.
    Use this when you need up-to-date information from the internet,
    news, or information not in the knowledge base."""
    
    parameters: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default: 3)",
                "default": 3
            }
        },
        "required": ["query"]
    })
    
    async def execute(self, query: str, num_results: int = 3) -> str:
        """
        MOCK: Search the web.
        TODO: Replace with real search API (Google, Bing, DuckDuckGo, etc.)
        """
        # Mock search results
        mock_results = [
            {
                "title": f"Result 1 for '{query}'",
                "snippet": f"This is a mock search result about {query}. In a real implementation, this would contain actual web content.",
                "url": f"https://example.com/search?q={query.replace(' ', '+')}"
            },
            {
                "title": f"Wikipedia: {query.title()}",
                "snippet": f"Wikipedia article about {query}. Contains comprehensive information and references.",
                "url": f"https://en.wikipedia.org/wiki/{query.replace(' ', '_')}"
            },
            {
                "title": f"Latest news about {query}",
                "snippet": f"Recent news and updates related to {query}. This would show real news in production.",
                "url": f"https://news.example.com/topic/{query.replace(' ', '-')}"
            }
        ]
        
        results = mock_results[:num_results]
        
        formatted = f"[Web Search] Results for '{query}':\n\n"
        for i, result in enumerate(results, 1):
            formatted += f"{i}. **{result['title']}**\n"
            formatted += f"   {result['snippet']}\n"
            formatted += f"   🔗 {result['url']}\n\n"
        
        formatted += "⚠️ Note: These are mock results. Real web search API integration pending."
        
        return formatted


@dataclass
class GetCompanyInfoTool(Tool):
    """Get company information (for professional persona)."""
    
    name: str = "get_company_info"
    description: str = """Get information about a company or organization.
    Use this when users ask about company details, contacts, or business info."""
    
    parameters: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "company_name": {
                "type": "string",
                "description": "Name of the company to look up"
            },
            "info_type": {
                "type": "string",
                "description": "Type of information needed",
                "enum": ["overview", "contact", "products", "financials"]
            }
        },
        "required": ["company_name"]
    })
    
    async def execute(self, company_name: str, info_type: str = "overview") -> str:
        """MOCK: Get company information."""
        # Mock company database
        mock_companies = {
            "google": {
                "overview": "Google LLC is an American multinational technology company. Founded: 1998. Headquarters: Mountain View, CA.",
                "contact": "Email: support@google.com, Website: google.com",
                "products": "Search, Gmail, YouTube, Android, Cloud Services",
                "financials": "Revenue: $257B (2023), Employees: 180,000+"
            },
            "microsoft": {
                "overview": "Microsoft Corporation is an American multinational technology company. Founded: 1975. Headquarters: Redmond, WA.",
                "contact": "Email: support@microsoft.com, Website: microsoft.com",
                "products": "Windows, Office, Azure, Xbox, LinkedIn",
                "financials": "Revenue: $211B (2023), Employees: 220,000+"
            }
        }
        
        company_lower = company_name.lower().strip()
        company = mock_companies.get(company_lower)
        
        if company:
            info = company.get(info_type, company["overview"])
            return f"[Company Info: {company_name}]\n{info}"
        
        return f"""[Company Info: {company_name}]
Unable to find detailed information for '{company_name}' in our database.

For accurate information, please visit:
- LinkedIn: linkedin.com/company/{company_name.replace(' ', '-')}
- Official website: {company_name.lower().replace(' ', '')}.com

⚠️ Note: Mock data - real company API integration pending."""

