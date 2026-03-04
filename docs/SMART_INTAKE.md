# Smart CEO Intake Guide

## How It Works

The CEO agent analyzes your request and only asks questions about missing information. The questions are task-specific, so simple requests move faster.

## Examples

### Complete Request (No Questions)

"Maak een realistic afbeelding van een rode Ferrari in landscape format met dramatic mood"

CEO detects: style (realistic), subject (Ferrari), color (red), dimensions (landscape), mood (dramatic)
Result: No questions needed.

### Incomplete Request (Targeted Questions)

"Maak een afbeelding"

CEO asks:
- What should the image show?
- What style? (realistic, cartoon, abstract)
- What dimensions?

### Task-Specific Questions

Different task types get different questions:

Image Generation:
- Subject, style, dimensions, mood, colors

Code Writing:
- Language/framework, functionality, requirements, tests

Data Analysis:
- Data source, insights needed, presentation format

Translation:
- Languages (from/to), content type, volume

Copy Writing:
- Platform, audience, tone, call-to-action

Research:
- Topic, depth, citation needs

## Tips for Faster Processing

Include details in your request:
- Good: "Realistic afbeelding rode auto landscape"
- Less helpful: "Maak afbeelding"

Mention style/format:
- Good: "Python FastAPI code"
- Less helpful: "Code"

Be specific:
- Good: "Dark moody kasteel"
- Less helpful: "Kasteel"
