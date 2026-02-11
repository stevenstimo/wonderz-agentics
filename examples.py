#!/usr/bin/env python3
"""
Advanced Examples
Toont hoe je custom workflows kunt maken met de agents
"""

from rich.console import Console
from orchestrator import DevelopmentOrchestrator
from agents import ProductOwnerAgent, DeveloperAgent, ReviewerAgent, DevOpsAgent
from config import ANTHROPIC_API_KEY

console = Console()


def example_1_custom_workflow():
    """
    Voorbeeld: Custom workflow waarbij je alleen specifieke agents gebruikt
    """
    console.print("\n[bold cyan]Example 1: Custom Workflow - Alleen Code Review[/bold cyan]\n")
    
    # Alleen reviewer gebruiken voor bestaande code
    reviewer = ReviewerAgent(ANTHROPIC_API_KEY)
    
    existing_code = """
def calculate_total(items):
    total = 0
    for item in items:
        total = total + item['price']
    return total
"""
    
    console.print("Reviewing existing code...")
    result = reviewer.review(existing_code)
    
    console.print(f"\n[bold]Review Status:[/bold] {result['status']}")
    console.print(f"\n{result['review']}")


def example_2_security_audit():
    """
    Voorbeeld: Security audit van bestaande code
    """
    console.print("\n[bold cyan]Example 2: Security Audit[/bold cyan]\n")
    
    reviewer = ReviewerAgent(ANTHROPIC_API_KEY)
    
    # Code met potentiële security issues
    code_to_audit = """
from flask import Flask, request
import sqlite3

app = Flask(__name__)

@app.route('/user')
def get_user():
    user_id = request.args.get('id')
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    return cursor.fetchone()
"""
    
    console.print("Running security audit...")
    result = reviewer.security_audit(code_to_audit)
    
    console.print(f"\n{result['security_audit']}")


def example_3_feature_addition():
    """
    Voorbeeld: Voeg feature toe aan bestaande code
    """
    console.print("\n[bold cyan]Example 3: Feature Addition[/bold cyan]\n")
    
    developer = DeveloperAgent(ANTHROPIC_API_KEY)
    
    existing_code = """
class TodoList:
    def __init__(self):
        self.items = []
    
    def add_item(self, item):
        self.items.append(item)
    
    def get_items(self):
        return self.items
"""
    
    feature_request = "Add ability to mark items as completed and filter by completion status"
    
    console.print("Adding new feature...")
    result = developer.implement_feature(existing_code, feature_request)
    
    console.print(f"\n{result['updated_code']}")


def example_4_iterative_refinement():
    """
    Voorbeeld: Iteratieve verbetering met feedback loop
    """
    console.print("\n[bold cyan]Example 4: Iterative Refinement[/bold cyan]\n")
    
    po = ProductOwnerAgent(ANTHROPIC_API_KEY)
    developer = DeveloperAgent(ANTHROPIC_API_KEY)
    reviewer = ReviewerAgent(ANTHROPIC_API_KEY)
    
    # Start met vage requirements
    console.print("[dim]Step 1: Initial requirements...[/dim]")
    requirements = po.analyze("Build a URL shortener")
    
    # Ontwikkel code
    console.print("[dim]Step 2: Developing code...[/dim]")
    code = developer.develop(requirements["requirements"], "Python")
    
    # Review
    console.print("[dim]Step 3: Reviewing...[/dim]")
    review = reviewer.review(code["full_output"], requirements["requirements"])
    
    # Als er issues zijn, laat reviewer verbeteringen suggereren
    if review["status"] != "APPROVED":
        console.print("[dim]Step 4: Getting improvements...[/dim]")
        improvements = reviewer.suggest_improvements(
            code["full_output"],
            review["review"]
        )
        console.print("\n[bold green]Improved Code:[/bold green]")
        console.print(improvements["improved_code"][:500] + "...")


def example_5_minimal_mvp():
    """
    Voorbeeld: Snel een minimal MVP bouwen
    """
    console.print("\n[bold cyan]Example 5: Quick MVP[/bold cyan]\n")
    
    orchestrator = DevelopmentOrchestrator()
    
    # Simpele MVP in één keer
    result = orchestrator.run_full_workflow(
        project_idea="A simple API endpoint that returns a random quote",
        language="Python",
        platform="docker",
        max_review_iterations=1
    )
    
    console.print(f"\n[bold green]MVP Created![/bold green]")
    console.print(f"Session ID: {result['session_id']}")
    console.print(f"Total tokens: {result['total_tokens']:,}")


def example_6_dockerfile_optimization():
    """
    Voorbeeld: Optimaliseer bestaande Dockerfile
    """
    console.print("\n[bold cyan]Example 6: Dockerfile Optimization[/bold cyan]\n")
    
    devops = DevOpsAgent(ANTHROPIC_API_KEY)
    
    existing_dockerfile = """
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "app.py"]
"""
    
    console.print("Optimizing Dockerfile...")
    result = devops.optimize_dockerfile(existing_dockerfile)
    
    console.print(f"\n{result['optimized_dockerfile']}")


def example_7_monitoring_setup():
    """
    Voorbeeld: Maak monitoring setup
    """
    console.print("\n[bold cyan]Example 7: Monitoring Setup[/bold cyan]\n")
    
    devops = DevOpsAgent(ANTHROPIC_API_KEY)
    
    console.print("Creating monitoring setup for FastAPI app...")
    result = devops.create_monitoring_setup("FastAPI REST API")
    
    console.print(f"\n{result['monitoring_setup']}")


def main():
    """
    Run examples
    """
    if not ANTHROPIC_API_KEY:
        console.print("[bold red]Error: Geen API key gevonden in .env[/bold red]")
        return
    
    console.print("[bold]Multi-Agent Development System - Advanced Examples[/bold]")
    console.print("\nKies een voorbeeld om uit te voeren:\n")
    
    examples = {
        "1": ("Custom Workflow - Code Review", example_1_custom_workflow),
        "2": ("Security Audit", example_2_security_audit),
        "3": ("Feature Addition", example_3_feature_addition),
        "4": ("Iterative Refinement", example_4_iterative_refinement),
        "5": ("Quick MVP", example_5_minimal_mvp),
        "6": ("Dockerfile Optimization", example_6_dockerfile_optimization),
        "7": ("Monitoring Setup", example_7_monitoring_setup),
    }
    
    for key, (name, _) in examples.items():
        console.print(f"  {key}. {name}")
    
    choice = input("\nKies een nummer (of 'all' voor alles): ").strip()
    
    if choice.lower() == 'all':
        for _, func in examples.values():
            func()
            console.print("\n" + "="*60 + "\n")
    elif choice in examples:
        _, func = examples[choice]
        func()
    else:
        console.print("[yellow]Ongeldige keuze[/yellow]")


if __name__ == "__main__":
    main()
