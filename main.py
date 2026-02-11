#!/usr/bin/env python3
"""
Multi-Agent Development System
Main entry point
"""

import sys
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

from orchestrator import DevelopmentOrchestrator
from config import ANTHROPIC_API_KEY

console = Console()


def print_welcome():
    """Print welcome message"""
    welcome_text = """
[bold cyan]Multi-Agent Development System[/bold cyan]

Dit systeem gebruikt 4 gespecialiseerde AI agents:
  🎯 Product Owner  - Requirements analyse
  💻 Developer      - Code implementatie
  🔍 Reviewer       - Code review & security
  🐳 DevOps         - Deployment setup

Laten we je project bouwen!
    """
    console.print(Panel(welcome_text, border_style="cyan"))


def get_project_input() -> dict:
    """Get project information from user"""
    console.print("\n[bold]Project Configuratie[/bold]\n")
    
    # Project idea
    project_idea = Prompt.ask(
        "[cyan]Beschrijf je project idee[/cyan]",
        default="Een RESTful API voor een todo-lijst app met gebruikers authenticatie"
    )
    
    # Programming language
    language = Prompt.ask(
        "[cyan]Voorkeurs programmeertaal[/cyan] (optioneel)",
        default="Python"
    )
    
    # Deployment platform
    platform = Prompt.ask(
        "[cyan]Deployment platform[/cyan]",
        choices=["docker", "kubernetes", "aws", "gcp", "azure"],
        default="docker"
    )
    
    # Review iterations
    max_iterations = Prompt.ask(
        "[cyan]Max code review iteraties[/cyan]",
        default="2"
    )
    
    return {
        "project_idea": project_idea,
        "language": language if language else None,
        "platform": platform,
        "max_review_iterations": int(max_iterations)
    }


def confirm_start(config: dict) -> bool:
    """Confirm before starting"""
    console.print("\n[bold yellow]Project Configuratie:[/bold yellow]")
    console.print(f"  Project: {config['project_idea']}")
    console.print(f"  Taal: {config['language'] or 'Auto-detect'}")
    console.print(f"  Platform: {config['platform']}")
    console.print(f"  Max review iteraties: {config['max_review_iterations']}")
    
    return Confirm.ask("\n[cyan]Start workflow?[/cyan]", default=True)


def main():
    """Main entry point"""
    try:
        # Check API key
        if not ANTHROPIC_API_KEY:
            console.print(
                "[bold red]❌ Geen API key gevonden![/bold red]\n"
                "Maak een .env file met je ANTHROPIC_API_KEY.\n"
                "Zie .env.example voor een voorbeeld.\n"
            )
            sys.exit(1)
        
        # Welcome
        print_welcome()
        
        # Get input
        config = get_project_input()
        
        # Confirm
        if not confirm_start(config):
            console.print("\n[yellow]Workflow geannuleerd.[/yellow]")
            sys.exit(0)
        
        # Run workflow
        orchestrator = DevelopmentOrchestrator()
        
        results = orchestrator.run_full_workflow(
            project_idea=config["project_idea"],
            language=config["language"],
            platform=config["platform"],
            max_review_iterations=config["max_review_iterations"]
        )
        
        # Success
        console.print("\n[bold green]✅ Workflow succesvol afgerond![/bold green]")
        
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Workflow onderbroken door gebruiker.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {str(e)}[/bold red]")
        import traceback
        console.print("\n[dim]" + traceback.format_exc() + "[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    main()
