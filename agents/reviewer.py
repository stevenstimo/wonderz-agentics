"""
Reviewer Agent
Controleert code op bugs, beveiligingslekken en stijl
"""

from anthropic import Anthropic
from config import AGENT_CONFIG

SYSTEM_PROMPT = """Je bent een senior code reviewer die code controleert op kwaliteit, security en best practices.

Je rol:
- Review code op bugs, logic errors, en edge cases
- Identificeer security vulnerabilities (OWASP Top 10, etc.)
- Check code style, readability, en maintainability
- Evalueer architectuur en design patterns
- Geef constructieve feedback met concrete verbetervoorstellen

Je output moet bevatten:
1. **Overall Assessment**: APPROVED / NEEDS_CHANGES / REJECTED
2. **Critical Issues**: Bugs en security problemen (blokkeren deployment)
3. **Major Issues**: Design problemen en code quality issues
4. **Minor Issues**: Style, naming, documentatie
5. **Positive Feedback**: Wat is er goed gedaan?
6. **Recommendations**: Concrete verbetervoorstellen

Wees streng maar fair. Security en correctheid zijn belangrijker dan perfecte style.
Geef altijd concrete voorbeelden en oplossingen bij feedback.
"""


class ReviewerAgent:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.config = AGENT_CONFIG["reviewer"]
    
    def review(self, code: str, requirements: str = None, focus_areas: list = None) -> dict:
        """
        Review code op kwaliteit en security
        
        Args:
            code: De te reviewen code
            requirements: Optioneel de requirements voor context
            focus_areas: Lijst van specifieke aspecten om op te focussen
            
        Returns:
            dict met review resultaten en metadata
        """
        req_context = f"\n\nREQUIREMENTS:\n{requirements}" if requirements else ""
        focus_context = f"\n\nFOCUS OP: {', '.join(focus_areas)}" if focus_areas else ""
        
        messages = [
            {
                "role": "user",
                "content": f"""Review de volgende code:

CODE:
{code}
{req_context}
{focus_context}

Geef een grondige code review met:
1. Overall assessment (APPROVED/NEEDS_CHANGES/REJECTED)
2. Critical issues (security, bugs)
3. Major issues (design, performance)
4. Minor issues (style, docs)
5. Positive feedback
6. Concrete recommendations

Wees specifiek en geef code voorbeelden bij je feedback.
"""
            }
        ]
        
        response = self.client.messages.create(
            model=self.config["model"],
            max_tokens=self.config["max_tokens"],
            temperature=self.config["temperature"],
            system=SYSTEM_PROMPT,
            messages=messages
        )
        
        review_text = response.content[0].text
        
        # Extract status uit review
        status = self._extract_status(review_text)
        
        return {
            "agent": "Reviewer",
            "review": review_text,
            "status": status,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    
    def security_audit(self, code: str) -> dict:
        """
        Specifieke security audit
        """
        messages = [
            {
                "role": "user",
                "content": f"""Voer een security audit uit op de volgende code:

{code}

Focus specifiek op:
- OWASP Top 10 vulnerabilities
- Input validation
- Authentication & Authorization
- SQL injection / NoSQL injection
- XSS, CSRF
- Sensitive data exposure
- Insecure dependencies
- Security misconfiguration

Geef een gedetailleerd security rapport met gevonden issues en fixes.
"""
            }
        ]
        
        response = self.client.messages.create(
            model=self.config["model"],
            max_tokens=self.config["max_tokens"],
            temperature=self.config["temperature"],
            system=SYSTEM_PROMPT,
            messages=messages
        )
        
        return {
            "agent": "Reviewer",
            "security_audit": response.content[0].text,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    
    def suggest_improvements(self, code: str, review_feedback: str) -> dict:
        """
        Genereer verbeterde versie van code op basis van review
        """
        messages = [
            {
                "role": "user",
                "content": f"""Hier is de originele code:

{code}

REVIEW FEEDBACK:
{review_feedback}

Geef een verbeterde versie van de code die alle review feedback addresseert.
"""
            }
        ]
        
        response = self.client.messages.create(
            model=self.config["model"],
            max_tokens=self.config["max_tokens"],
            temperature=self.config["temperature"],
            system=SYSTEM_PROMPT,
            messages=messages
        )
        
        return {
            "agent": "Reviewer",
            "improved_code": response.content[0].text,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    
    def _extract_status(self, review_text: str) -> str:
        """
        Extract assessment status uit review text
        """
        review_lower = review_text.lower()
        
        if "approved" in review_lower and "needs" not in review_lower:
            return "APPROVED"
        elif "rejected" in review_lower:
            return "REJECTED"
        else:
            return "NEEDS_CHANGES"
