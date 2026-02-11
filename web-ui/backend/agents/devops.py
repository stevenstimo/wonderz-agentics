"""
DevOps Agent
Beheert deployment en schrijft Dockerfiles, CI/CD pipelines
"""

from anthropic import Anthropic
from config import AGENT_CONFIG

SYSTEM_PROMPT = """Je bent een DevOps engineer die deployment en infrastructure beheert.

Je rol:
- Maak Dockerfiles voor containerization
- Schrijf CI/CD pipelines (GitHub Actions, GitLab CI, etc.)
- Configureer deployment (Kubernetes, Docker Compose, cloud platforms)
- Zorg voor monitoring, logging, en observability
- Implementeer security best practices in infrastructure

Je output moet bevatten:
1. **Dockerfile**: Production-ready container image
2. **Docker Compose**: Voor lokale development (indien relevant)
3. **CI/CD Pipeline**: Geautomatiseerde testing en deployment
4. **Deployment Configuratie**: K8s manifests of cloud configs
5. **Setup Instructies**: Hoe deploy je dit?
6. **Monitoring**: Logging en health checks

Denk aan:
- Multi-stage builds voor kleine images
- Security scanning
- Environment variabelen
- Health checks en readiness probes
- Rollback strategieën
- Secrets management
"""


class DevOpsAgent:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.config = AGENT_CONFIG["devops"]
    
    def create_deployment(self, code: str, requirements: str, platform: str = "docker") -> dict:
        """
        Maak deployment configuratie
        
        Args:
            code: De applicatie code
            requirements: Project requirements voor context
            platform: Deployment platform (docker, kubernetes, aws, gcp, azure)
            
        Returns:
            dict met deployment files en instructies
        """
        messages = [
            {
                "role": "user",
                "content": f"""Maak deployment configuratie voor de volgende applicatie:

CODE OVERVIEW:
{code[:2000]}...  (getrunceerd voor context)

REQUIREMENTS:
{requirements}

TARGET PLATFORM: {platform}

Genereer complete deployment setup met:
1. Dockerfile (multi-stage, optimized)
2. Docker Compose (voor local dev)
3. CI/CD pipeline (GitHub Actions of GitLab CI)
4. Environment variabelen template (.env.example)
5. Deployment instructies
6. Health checks en monitoring

Format elk bestand als:
```filename: path/to/file.ext
content hier
```

Zorg voor production-ready configuratie met security best practices.
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
        
        deployment_output = response.content[0].text
        deployment_files = self._parse_deployment_files(deployment_output)
        
        return {
            "agent": "DevOps",
            "full_output": deployment_output,
            "deployment_files": deployment_files,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    
    def create_cicd_pipeline(self, project_type: str, test_command: str = None) -> dict:
        """
        Maak CI/CD pipeline configuratie
        """
        test_info = f"\nTest command: {test_command}" if test_command else ""
        
        messages = [
            {
                "role": "user",
                "content": f"""Maak een complete CI/CD pipeline voor een {project_type} project.
{test_info}

Inclusief:
- Linting en code quality checks
- Automated testing
- Security scanning
- Build en deployment
- Environment-based deployment (dev, staging, prod)

Genereer zowel GitHub Actions als GitLab CI configuraties.
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
            "agent": "DevOps",
            "cicd_config": response.content[0].text,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    
    def optimize_dockerfile(self, dockerfile: str) -> dict:
        """
        Optimaliseer bestaande Dockerfile
        """
        messages = [
            {
                "role": "user",
                "content": f"""Optimaliseer de volgende Dockerfile:

{dockerfile}

Focus op:
- Kleinere image size (multi-stage builds)
- Snellere builds (layer caching)
- Security (non-root user, minimal base image)
- Best practices

Geef de geoptimaliseerde Dockerfile met uitleg van de changes.
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
            "agent": "DevOps",
            "optimized_dockerfile": response.content[0].text,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    
    def create_monitoring_setup(self, application_type: str) -> dict:
        """
        Maak monitoring en observability setup
        """
        messages = [
            {
                "role": "user",
                "content": f"""Maak een monitoring setup voor een {application_type} applicatie.

Inclusief:
- Health check endpoints
- Logging configuratie (structured logging)
- Metrics (Prometheus/OpenTelemetry)
- Alerting regels
- Dashboard configuratie (Grafana)

Geef concrete implementatie met code voorbeelden.
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
            "agent": "DevOps",
            "monitoring_setup": response.content[0].text,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
    
    def _parse_deployment_files(self, text: str) -> dict:
        """
        Parse deployment files uit markdown text
        """
        files = {}
        lines = text.split('\n')
        current_file = None
        current_content = []
        in_code_block = False
        
        for line in lines:
            if line.startswith('```') and 'filename:' in line:
                if current_file and current_content:
                    files[current_file] = '\n'.join(current_content)
                
                current_file = line.split('filename:')[1].strip()
                current_content = []
                in_code_block = True
            elif line.startswith('```') and in_code_block:
                if current_file and current_content:
                    files[current_file] = '\n'.join(current_content)
                current_file = None
                current_content = []
                in_code_block = False
            elif in_code_block and current_file:
                current_content.append(line)
        
        if current_file and current_content:
            files[current_file] = '\n'.join(current_content)
        
        return files
