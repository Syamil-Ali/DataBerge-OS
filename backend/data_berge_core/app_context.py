"""Shared app context that helps agents understand UI references.

When users reference parts of the app (e.g. "the chart in Data Pulse"),
agents can map UI element names to their data meaning.
"""

APP_CONTEXT = """
## App UI Context — How the frontend maps to data

The Data-Berge OS app has three main pages. When users reference UI elements,
map them to the corresponding data concepts below.

### 1. Data Pulse (Profile View)
Shows the dataset profile with these sections:
- **Profile overview** — row count, column count, missing cells, duplicate rows
- **Dataset context panel** — description coverage, duplicate rows, top correlation
- **Analyst readiness panel** — data engineering summary, readiness score (0-10),
  semantic roles, warnings, recommended actions
- **Column Explorer (Univariate analysis)** — paginated column cards, each showing:
  - Column name, dtype, semantic_type (numeric/categorical/text)
  - Mini chart: histogram for numeric, top-value bar chart for categorical
  - Unique count, missing %, sample values
  - Engineering role (measure, category, outcome, time, identifier)
- **Relationships (Bivariate analysis)** — numeric-vs-numeric correlations,
  categorical-vs-categorical chi-square, numeric-vs-categorical ANOVA

When a user says "the Income chart in Data Pulse" → they mean the mini
histogram/bar chart shown on the Income column card in the Column Explorer.

When a user says "the engineering summary" → they mean the Analyst Readiness
panel showing readiness_score, summary, warnings, recommended_actions,
and semantic_roles.

### 2. Explorer (Chat)
Free-form chat with the AI agents. Users can attach column context from
Data Pulse. The chat shows agent responses with metadata badges
(Analyst/Engineer, skill used, mode).

### 3. Executive Report
Generates a structured report with:
- Executive summary
- Key findings (with confidence levels)
- Data story (narrative)
- Action plan
- Prognosis (risks and recommendations)
- Systems detail (governance review)

## Key data concepts to understand UI references:
- "chart" or "graph" on a column → the mini visualization in Column Explorer
- "readiness" or "engineering summary" → data engineering contract summary
- "quality flags" or "warnings" → profile quality_flags + contract warnings
- "correlations" or "relationships" → bivariate analysis section
- "column details" or "column info" → profile column metadata
- "distribution" → histogram data for that column
- "top values" → categorical frequency breakdown
"""