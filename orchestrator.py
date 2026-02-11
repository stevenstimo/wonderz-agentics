"""
Orchestrator
Beheert de workflow tussen de verschillende agents
"""

import os
from datetime import datetime
from typing import Optional, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from agents import ProductOwnerAgent, DeveloperAgent, ReviewerAgent, DevOpsAgent
from config import ANTHROPIC_API_KEY, REQUIREMENTS_DIR, CODE_DIR, REVIEW_DIR, DEVOPS_DIR

console = Console()


class DevelopmentOrchestrator:
    """
    Orchestreert de samenwerking tussen agents
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialiseer de orchestrator met alle agents
        """
        self.api_key = api_key or ANTHROPIC_API_KEY
        
        if not self.api_key:
            raise ValueError(
                "Geen API key gevonden. Zet ANTHROPIC_API_KEY in je .env file."
            )
        
        # Initialiseer agents
        self.product_owner = ProductOwnerAgent(self.api_key)
        self.developer = DeveloperAgent(self.api_key)
        self.reviewer = ReviewerAgent(self.api_key)
        self.devops = DevOpsAgent(self.api_key)
        
        # Workflow state
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.context = {}
        
    def run_full_workflow(
        self, 
        project_idea: str,
        language: Optional[str] = None,
        platform: str = "docker",
        max_review_iterations: int = 2
    ) -> Dict[str, Any]:
        """
        Voer de complete workflow uit van idee naar deployment-ready code
        
        Args:
            project_idea: Beschrijving van het project
            language: Voorkeurs programmeertaal
            platform: Deployment platform
            max_review_iterations: Max aantal review/fix iteraties
            
        Returns:
            Dict met alle outputs en metadata
        """
        console.print("\n[bold cyan]🚀 Multi-Agent Development Workflow Started[/bold cyan]\n")
        
        results = {
            "session_id": self.session_id,
            "project_idea": project_idea,
            "stages": {},
            "total_tokens": 0
        }
        
        # Stage 1: Product Owner - Requirements
        console.print("[bold yellow]Stage 1: Product Owner - Analyzing Requirements[/bold yellow]")
        po_result = self._run_product_owner(project_idea)
        results["stages"]["requirements"] = po_result
        results["total_tokens"] += po_result["input_tokens"] + po_result["output_tokens"]
        
        self._save_output(
            "requirements.md",
            po_result["requirements"],
            REQUIREMENTS_DIR
        )
        
        # Stage 2: Developer - Code Implementation
        console.print("\n[bold yellow]Stage 2: Developer - Writing Code[/bold yellow]")
        dev_result = self._run_developer(
            po_result["requirements"],
            language
        )
        results["stages"]["development"] = dev_result
        results["total_tokens"] += dev_result["input_tokens"] + dev_result["output_tokens"]
        
        # Save all code files
        for filename, code in dev_result["code_files"].items():
            self._save_output(filename, code, CODE_DIR)
        
        # Save full development output
        self._save_output(
            "development_full.md",
            dev_result["full_output"],
            CODE_DIR
        )
        
        # Stage 3: Reviewer - Code Review (with iteration)
        console.print("\n[bold yellow]Stage 3: Reviewer - Code Review[/bold yellow]")
        review_iteration = 0
        current_code = dev_result["full_output"]
        
        while review_iteration < max_review_iterations:
            review_result = self._run_reviewer(
                current_code,
                po_result["requirements"]
            )
            results["stages"][f"review_iteration_{review_iteration + 1}"] = review_result
            results["total_tokens"] += review_result["input_tokens"] + review_result["output_tokens"]
            
            self._save_output(
                f"review_iteration_{review_iteration + 1}.md",
                review_result["review"],
                REVIEW_DIR
            )
            
            # Check status
            if review_result["status"] == "APPROVED":
                console.print("[bold green]✅ Code review approved![/bold green]")
                break
            elif review_result["status"] == "REJECTED":
                console.print("[bold red]❌ Code review rejected. Consider major changes.[/bold red]")
                break
            else:
                console.print(f"[yellow]🔄 Review needs changes. Iteration {review_iteration + 1}/{max_review_iterations}[/yellow]")
                
                # Let developer fix issues (simplified - in practice zou je hier de reviewer's suggestions kunnen implementeren)
                if review_iteration < max_review_iterations - 1:
                    console.print("[dim]Note: In production, developer would fix issues here[/dim]")
            
            review_iteration += 1
        
        # Stage 4: DevOps - Deployment Setup
        console.print("\n[bold yellow]Stage 4: DevOps - Creating Deployment Configuration[/bold yellow]")
        devops_result = self._run_devops(
            dev_result["full_output"],
            po_result["requirements"],
            platform
        )
        results["stages"]["devops"] = devops_result
        results["total_tokens"] += devops_result["input_tokens"] + devops_result["output_tokens"]
        
        # Save deployment files
        for filename, content in devops_result["deployment_files"].items():
            self._save_output(filename, content, DEVOPS_DIR)
        
        self._save_output(
            "deployment_full.md",
            devops_result["full_output"],
            DEVOPS_DIR
        )
        
        # Summary
        self._print_summary(results)
        
        return results
    
    def _run_product_owner(self, project_idea: str) -> Dict[str, Any]:
        """Run Product Owner agent"""
        console.print("  📋 Analyzing project requirements...")
        result = self.product_owner.analyze(project_idea)
        
        # Show preview
        preview = result["requirements"][:300] + "..." if len(result["requirements"]) > 300 else result["requirements"]
        console.print(Panel(preview, title="[bold]Requirements Preview[/bold]", border_style="blue"))
        
        return result
    
    def _run_developer(self, requirements: str, language: Optional[str]) -> Dict[str, Any]:
        """Run Developer agent"""
        console.print(f"  💻 Writing code{f' in {language}' if language else ''}...")
        result = self.developer.develop(requirements, language)
        
        # Show files created
        if result["code_files"]:
            console.print(f"  [green]✓ Created {len(result['code_files'])} code file(s)[/green]")
            for filename in result["code_files"].keys():
                console.print(f"    - {filename}")
        
        return result
    
    def _run_reviewer(self, code: str, requirements: str) -> Dict[str, Any]:
        """Run Reviewer agent"""
        console.print("  🔍 Reviewing code quality and security...")
        result = self.reviewer.review(code, requirements)
        
        # Show status
        status_color = {
            "APPROVED": "green",
            "NEEDS_CHANGES": "yellow",
            "REJECTED": "red"
        }.get(result["status"], "white")
        
        console.print(f"  Status: [{status_color}]{result['status']}[/{status_color}]")
        
        return result
    
    def _run_devops(self, code: str, requirements: str, platform: str) -> Dict[str, Any]:
        """Run DevOps agent"""
        console.print(f"  🐳 Creating deployment configuration for {platform}...")
        result = self.devops.create_deployment(code, requirements, platform)
        
        # Show files created
        if result["deployment_files"]:
            console.print(f"  [green]✓ Created {len(result['deployment_files'])} deployment file(s)[/green]")
            for filename in result["deployment_files"].keys():
                console.print(f"    - {filename}")
        
        return result
    
    def _save_output(self, filename: str, content: str, directory: str):
        """Save output to file"""
        filepath = os.path.join(directory, f"{self.session_id}_{filename}")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        console.print(f"  [dim]💾 Saved: {filepath}[/dim]")
    
    def _print_summary(self, results: Dict[str, Any]):
        """Print workflow summary"""
        console.print("\n" + "="*60)
        console.print("[bold green]✨ Workflow Completed![/bold green]")
        console.print("="*60)
        
        console.print(f"\n[bold]Session ID:[/bold] {results['session_id']}")
        console.print(f"[bold]Total Tokens Used:[/bold] {results['total_tokens']:,}")
        
        console.print("\n[bold]Output Locations:[/bold]")
        console.print(f"  📋 Requirements: {REQUIREMENTS_DIR}/{results['session_id']}_requirements.md")
        console.print(f"  💻 Code: {CODE_DIR}/{results['session_id']}_*")
        console.print(f"  🔍 Reviews: {REVIEW_DIR}/{results['session_id']}_*")
        console.print(f"  🐳 DevOps: {DEVOPS_DIR}/{results['session_id']}_*")
        
        console.print("\n[bold cyan]Next Steps:[/bold cyan]")
        console.print("  1. Review de gegenereerde code in de output/ directory")
        console.print("  2. Test de applicatie lokaal")
        console.print("  3. Voer de deployment instructies uit")
        console.print("  4. Geef feedback voor iteraties\n")
