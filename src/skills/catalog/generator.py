"""Skill catalog generator — produces 100+ canonical Skill.md files.

Each skill is a complete, production-quality specification.
Run this module directly to regenerate the catalog.
"""

from __future__ import annotations

from pathlib import Path

SKILL_DEFINITIONS: list[dict] = [
    # === CODING (20 skills) ===
    {"slug": "code-review", "name": "Code Review", "cat": "coding", "det": "generative",
     "purpose": "Analyze code for quality, bugs, security issues, and style violations",
     "tools": ["github", "gitlab"], "tags": ["review", "quality", "bugs"]},
    {"slug": "code-generation", "name": "Code Generation", "cat": "coding", "det": "generative",
     "purpose": "Generate production-ready code from natural language specifications",
     "tools": [], "tags": ["generate", "write", "implement"]},
    {"slug": "code-refactor", "name": "Code Refactoring", "cat": "coding", "det": "generative",
     "purpose": "Restructure existing code to improve readability, performance, and maintainability without changing behavior",
     "tools": [], "tags": ["refactor", "clean", "improve"]},
    {"slug": "code-explain", "name": "Code Explanation", "cat": "coding", "det": "generative",
     "purpose": "Explain code logic, patterns, and design decisions in plain language",
     "tools": [], "tags": ["explain", "understand", "learn"]},
    {"slug": "test-generation", "name": "Test Generation", "cat": "coding", "det": "generative",
     "purpose": "Generate comprehensive test suites (unit, integration, e2e) for existing code",
     "tools": [], "tags": ["test", "coverage", "quality"]},
    {"slug": "debug-assist", "name": "Debug Assistant", "cat": "coding", "det": "generative",
     "purpose": "Systematically identify and fix bugs using stack traces, logs, and code analysis",
     "tools": [], "tags": ["debug", "fix", "troubleshoot"]},
    {"slug": "api-design", "name": "API Design", "cat": "coding", "det": "generative",
     "purpose": "Design RESTful, GraphQL, or gRPC APIs with OpenAPI specifications",
     "tools": [], "tags": ["api", "rest", "graphql", "openapi"]},
    {"slug": "database-design", "name": "Database Design", "cat": "coding", "det": "generative",
     "purpose": "Design database schemas, migrations, and query optimization strategies",
     "tools": [], "tags": ["database", "schema", "sql", "migration"]},
    {"slug": "code-translate", "name": "Code Translation", "cat": "coding", "det": "generative",
     "purpose": "Translate code between programming languages while preserving logic and idioms",
     "tools": [], "tags": ["translate", "convert", "port"]},
    {"slug": "regex-builder", "name": "Regex Builder", "cat": "coding", "det": "deterministic",
     "purpose": "Build, explain, and validate regular expressions with test cases",
     "tools": [], "tags": ["regex", "pattern", "validation"]},
    {"slug": "type-annotation", "name": "Type Annotation", "cat": "coding", "det": "quasi_deterministic",
     "purpose": "Add or improve type annotations and generate type stubs",
     "tools": [], "tags": ["types", "typing", "mypy"]},
    {"slug": "dependency-audit", "name": "Dependency Audit", "cat": "coding", "det": "deterministic",
     "purpose": "Audit project dependencies for vulnerabilities, licenses, and update paths",
     "tools": ["npm-registry", "pypi"], "tags": ["dependencies", "security", "audit"]},
    {"slug": "code-compress", "name": "Code Compression", "cat": "coding", "det": "generative",
     "purpose": "Reduce code size while preserving functionality through minification and dead code elimination",
     "tools": [], "tags": ["minify", "compress", "optimize"]},
    {"slug": "error-handling", "name": "Error Handling Design", "cat": "coding", "det": "generative",
     "purpose": "Design robust error handling strategies with custom exceptions and recovery patterns",
     "tools": [], "tags": ["errors", "exceptions", "resilience"]},
    {"slug": "performance-profile", "name": "Performance Profiling", "cat": "coding", "det": "quasi_deterministic",
     "purpose": "Identify performance bottlenecks and suggest optimization strategies",
     "tools": [], "tags": ["performance", "profiling", "optimization"]},
    {"slug": "code-documentation", "name": "Code Documentation", "cat": "coding", "det": "generative",
     "purpose": "Generate comprehensive docstrings, inline comments, and API documentation",
     "tools": [], "tags": ["docs", "docstrings", "comments"]},
    {"slug": "git-workflow", "name": "Git Workflow", "cat": "coding", "det": "deterministic",
     "purpose": "Generate commits, manage branches, resolve conflicts, and automate git operations",
     "tools": ["github", "gitlab"], "tags": ["git", "commits", "branches"]},
    {"slug": "ci-cd-pipeline", "name": "CI/CD Pipeline", "cat": "coding", "det": "quasi_deterministic",
     "purpose": "Design and generate CI/CD pipeline configurations for major platforms",
     "tools": ["github-actions", "gitlab-ci"], "tags": ["ci", "cd", "pipeline", "automation"]},
    {"slug": "code-search", "name": "Code Search", "cat": "coding", "det": "deterministic",
     "purpose": "Search codebases for patterns, usages, definitions, and references",
     "tools": ["github", "sourcegraph"], "tags": ["search", "find", "grep"]},
    {"slug": "architecture-review", "name": "Architecture Review", "cat": "coding", "det": "generative",
     "purpose": "Review system architecture for scalability, maintainability, and adherence to patterns",
     "tools": [], "tags": ["architecture", "design", "review"]},

    # === WRITING (15 skills) ===
    {"slug": "technical-writing", "name": "Technical Writing", "cat": "writing", "det": "generative",
     "purpose": "Write clear technical documentation, guides, and specifications",
     "tools": ["notion", "google-docs"], "tags": ["docs", "technical", "writing"]},
    {"slug": "blog-post", "name": "Blog Post Writer", "cat": "writing", "det": "generative",
     "purpose": "Write engaging blog posts with proper structure, SEO, and formatting",
     "tools": ["notion", "wordpress"], "tags": ["blog", "content", "seo"]},
    {"slug": "email-compose", "name": "Email Composer", "cat": "writing", "det": "generative",
     "purpose": "Compose professional emails with appropriate tone, structure, and call-to-action",
     "tools": ["gmail"], "tags": ["email", "communication"]},
    {"slug": "readme-generator", "name": "README Generator", "cat": "writing", "det": "generative",
     "purpose": "Generate comprehensive README.md files with badges, setup instructions, and examples",
     "tools": ["github"], "tags": ["readme", "docs", "project"]},
    {"slug": "changelog-writer", "name": "Changelog Writer", "cat": "writing", "det": "quasi_deterministic",
     "purpose": "Generate changelogs from git history following Keep a Changelog conventions",
     "tools": ["github"], "tags": ["changelog", "release", "versioning"]},
    {"slug": "proposal-writer", "name": "Proposal Writer", "cat": "writing", "det": "generative",
     "purpose": "Write project proposals, RFCs, and design documents",
     "tools": ["notion", "google-docs"], "tags": ["proposal", "rfc", "design"]},
    {"slug": "copy-editor", "name": "Copy Editor", "cat": "writing", "det": "generative",
     "purpose": "Edit text for grammar, clarity, conciseness, and tone consistency",
     "tools": [], "tags": ["edit", "grammar", "style"]},
    {"slug": "api-docs-writer", "name": "API Docs Writer", "cat": "writing", "det": "quasi_deterministic",
     "purpose": "Generate API documentation from code, OpenAPI specs, or usage examples",
     "tools": [], "tags": ["api", "docs", "openapi"]},
    {"slug": "report-generator", "name": "Report Generator", "cat": "writing", "det": "generative",
     "purpose": "Generate structured reports from data with visualizations and insights",
     "tools": ["notion"], "tags": ["report", "analysis", "summary"]},
    {"slug": "tutorial-writer", "name": "Tutorial Writer", "cat": "writing", "det": "generative",
     "purpose": "Write step-by-step tutorials with code examples and explanations",
     "tools": [], "tags": ["tutorial", "guide", "learning"]},
    {"slug": "content-summarizer", "name": "Content Summarizer", "cat": "writing", "det": "generative",
     "purpose": "Summarize long documents, articles, or conversations into concise briefs",
     "tools": [], "tags": ["summary", "brief", "condense"]},
    {"slug": "creative-writing", "name": "Creative Writing", "cat": "writing", "det": "generative",
     "purpose": "Generate creative fiction, poetry, and narrative content",
     "tools": [], "tags": ["creative", "fiction", "narrative"]},
    {"slug": "meeting-notes", "name": "Meeting Notes", "cat": "writing", "det": "generative",
     "purpose": "Generate structured meeting notes with action items and decisions",
     "tools": ["notion", "google-docs"], "tags": ["meeting", "notes", "actions"]},
    {"slug": "release-notes", "name": "Release Notes Writer", "cat": "writing", "det": "quasi_deterministic",
     "purpose": "Generate user-facing release notes from technical changelogs",
     "tools": ["github"], "tags": ["release", "notes", "changelog"]},
    {"slug": "spec-writer", "name": "Specification Writer", "cat": "writing", "det": "generative",
     "purpose": "Write detailed technical specifications and requirements documents",
     "tools": ["notion"], "tags": ["spec", "requirements", "prd"]},

    # === ANALYSIS (12 skills) ===
    {"slug": "data-analysis", "name": "Data Analysis", "cat": "analysis", "det": "quasi_deterministic",
     "purpose": "Analyze datasets to extract insights, patterns, and statistical summaries",
     "tools": [], "tags": ["data", "statistics", "insights"]},
    {"slug": "sentiment-analysis", "name": "Sentiment Analysis", "cat": "analysis", "det": "generative",
     "purpose": "Analyze text sentiment, emotion, and tone across documents",
     "tools": [], "tags": ["sentiment", "emotion", "nlp"]},
    {"slug": "competitor-analysis", "name": "Competitor Analysis", "cat": "analysis", "det": "generative",
     "purpose": "Research and compare competitor products, features, and market positioning",
     "tools": ["web-search"], "tags": ["competitor", "market", "research"]},
    {"slug": "log-analysis", "name": "Log Analysis", "cat": "analysis", "det": "quasi_deterministic",
     "purpose": "Parse, analyze, and extract patterns from application logs",
     "tools": [], "tags": ["logs", "debugging", "patterns"]},
    {"slug": "security-audit", "name": "Security Audit", "cat": "analysis", "det": "quasi_deterministic",
     "purpose": "Audit code and infrastructure for security vulnerabilities (OWASP, CWE)",
     "tools": ["github"], "tags": ["security", "audit", "vulnerabilities"]},
    {"slug": "cost-analysis", "name": "Cost Analysis", "cat": "analysis", "det": "quasi_deterministic",
     "purpose": "Analyze cloud infrastructure costs and suggest optimization strategies",
     "tools": [], "tags": ["cost", "cloud", "optimization"]},
    {"slug": "trend-analysis", "name": "Trend Analysis", "cat": "analysis", "det": "generative",
     "purpose": "Identify and analyze trends in data over time",
     "tools": [], "tags": ["trends", "time-series", "forecasting"]},
    {"slug": "risk-assessment", "name": "Risk Assessment", "cat": "analysis", "det": "generative",
     "purpose": "Evaluate project risks, dependencies, and mitigation strategies",
     "tools": [], "tags": ["risk", "assessment", "mitigation"]},
    {"slug": "code-metrics", "name": "Code Metrics", "cat": "analysis", "det": "deterministic",
     "purpose": "Calculate code complexity, coverage, duplication, and quality metrics",
     "tools": [], "tags": ["metrics", "complexity", "quality"]},
    {"slug": "impact-analysis", "name": "Impact Analysis", "cat": "analysis", "det": "quasi_deterministic",
     "purpose": "Analyze the impact of proposed changes across the codebase",
     "tools": [], "tags": ["impact", "changes", "dependencies"]},
    {"slug": "accessibility-audit", "name": "Accessibility Audit", "cat": "analysis", "det": "quasi_deterministic",
     "purpose": "Audit web content for WCAG compliance and accessibility issues",
     "tools": [], "tags": ["accessibility", "wcag", "a11y"]},
    {"slug": "license-audit", "name": "License Audit", "cat": "analysis", "det": "deterministic",
     "purpose": "Audit software licenses for compatibility and compliance",
     "tools": [], "tags": ["license", "compliance", "legal"]},

    # === DATA (8 skills) ===
    {"slug": "data-transform", "name": "Data Transformation", "cat": "data", "det": "deterministic",
     "purpose": "Transform data between formats (JSON, CSV, XML, YAML, Parquet)",
     "tools": [], "tags": ["transform", "convert", "etl"]},
    {"slug": "data-validation", "name": "Data Validation", "cat": "data", "det": "deterministic",
     "purpose": "Validate data against schemas, business rules, and constraints",
     "tools": [], "tags": ["validate", "schema", "constraints"]},
    {"slug": "data-generation", "name": "Data Generation", "cat": "data", "det": "quasi_deterministic",
     "purpose": "Generate realistic test data, fixtures, and seed data",
     "tools": [], "tags": ["generate", "fixtures", "mock"]},
    {"slug": "data-cleaning", "name": "Data Cleaning", "cat": "data", "det": "quasi_deterministic",
     "purpose": "Clean, normalize, and deduplicate messy datasets",
     "tools": [], "tags": ["clean", "normalize", "deduplicate"]},
    {"slug": "csv-processor", "name": "CSV Processor", "cat": "data", "det": "deterministic",
     "purpose": "Process, filter, aggregate, and transform CSV files",
     "tools": [], "tags": ["csv", "process", "aggregate"]},
    {"slug": "json-processor", "name": "JSON Processor", "cat": "data", "det": "deterministic",
     "purpose": "Query, transform, and validate JSON documents using JMESPath/JSONPath",
     "tools": [], "tags": ["json", "query", "jmespath"]},
    {"slug": "schema-generator", "name": "Schema Generator", "cat": "data", "det": "deterministic",
     "purpose": "Generate JSON Schema, Pydantic models, or TypeScript interfaces from sample data",
     "tools": [], "tags": ["schema", "types", "generate"]},
    {"slug": "data-pipeline", "name": "Data Pipeline Builder", "cat": "data", "det": "quasi_deterministic",
     "purpose": "Design and generate data pipeline configurations (Airflow, dbt, Prefect)",
     "tools": [], "tags": ["pipeline", "etl", "airflow"]},

    # === DEVOPS (10 skills) ===
    {"slug": "docker-compose", "name": "Docker Compose Builder", "cat": "devops", "det": "quasi_deterministic",
     "purpose": "Generate production-grade Docker and docker-compose configurations",
     "tools": ["docker-hub"], "tags": ["docker", "containers", "compose"]},
    {"slug": "kubernetes-config", "name": "Kubernetes Config", "cat": "devops", "det": "quasi_deterministic",
     "purpose": "Generate Kubernetes manifests, Helm charts, and Kustomize overlays",
     "tools": [], "tags": ["kubernetes", "k8s", "helm"]},
    {"slug": "terraform-module", "name": "Terraform Module", "cat": "devops", "det": "quasi_deterministic",
     "purpose": "Write Terraform modules for cloud infrastructure provisioning",
     "tools": ["terraform-registry"], "tags": ["terraform", "iac", "cloud"]},
    {"slug": "nginx-config", "name": "Nginx Configuration", "cat": "devops", "det": "deterministic",
     "purpose": "Generate Nginx configurations for proxying, caching, and load balancing",
     "tools": [], "tags": ["nginx", "proxy", "loadbalancer"]},
    {"slug": "monitoring-setup", "name": "Monitoring Setup", "cat": "devops", "det": "quasi_deterministic",
     "purpose": "Configure monitoring, alerting, and dashboards (Prometheus, Grafana, DataDog)",
     "tools": [], "tags": ["monitoring", "alerting", "prometheus"]},
    {"slug": "log-aggregation", "name": "Log Aggregation Setup", "cat": "devops", "det": "quasi_deterministic",
     "purpose": "Configure centralized logging (ELK, Loki, Fluentd)",
     "tools": [], "tags": ["logging", "elk", "aggregation"]},
    {"slug": "ssl-certificate", "name": "SSL Certificate Manager", "cat": "devops", "det": "deterministic",
     "purpose": "Generate and manage SSL/TLS certificates (Let's Encrypt, self-signed)",
     "tools": [], "tags": ["ssl", "tls", "certificate"]},
    {"slug": "backup-strategy", "name": "Backup Strategy", "cat": "devops", "det": "quasi_deterministic",
     "purpose": "Design backup and disaster recovery strategies for databases and systems",
     "tools": [], "tags": ["backup", "disaster-recovery", "strategy"]},
    {"slug": "environment-config", "name": "Environment Config", "cat": "devops", "det": "deterministic",
     "purpose": "Generate environment configurations, .env files, and secret management setups",
     "tools": [], "tags": ["env", "config", "secrets"]},
    {"slug": "deploy-script", "name": "Deployment Script", "cat": "devops", "det": "quasi_deterministic",
     "purpose": "Generate deployment scripts for various platforms and strategies (blue-green, canary)",
     "tools": [], "tags": ["deploy", "script", "automation"]},

    # === SECURITY (8 skills) ===
    {"slug": "threat-model", "name": "Threat Modeling", "cat": "security", "det": "generative",
     "purpose": "Create STRIDE-based threat models for applications and systems",
     "tools": [], "tags": ["threat", "stride", "model"]},
    {"slug": "secret-scanner", "name": "Secret Scanner", "cat": "security", "det": "deterministic",
     "purpose": "Scan code and configs for accidentally committed secrets and credentials",
     "tools": ["github"], "tags": ["secrets", "scan", "credentials"]},
    {"slug": "cve-lookup", "name": "CVE Lookup", "cat": "security", "det": "deterministic",
     "purpose": "Look up CVE details and assess vulnerability impact on dependencies",
     "tools": ["nvd-api"], "tags": ["cve", "vulnerability", "security"]},
    {"slug": "auth-design", "name": "Auth Design", "cat": "security", "det": "generative",
     "purpose": "Design authentication and authorization systems (OAuth, JWT, RBAC)",
     "tools": [], "tags": ["auth", "oauth", "jwt", "rbac"]},
    {"slug": "input-validation", "name": "Input Validation", "cat": "security", "det": "quasi_deterministic",
     "purpose": "Generate input validation and sanitization logic for web applications",
     "tools": [], "tags": ["validation", "sanitization", "xss"]},
    {"slug": "security-headers", "name": "Security Headers", "cat": "security", "det": "deterministic",
     "purpose": "Generate and audit HTTP security headers (CSP, HSTS, CORS)",
     "tools": [], "tags": ["headers", "csp", "hsts", "cors"]},
    {"slug": "encryption-helper", "name": "Encryption Helper", "cat": "security", "det": "deterministic",
     "purpose": "Implement encryption, hashing, and key management patterns",
     "tools": [], "tags": ["encryption", "hashing", "crypto"]},
    {"slug": "penetration-guide", "name": "Penetration Test Guide", "cat": "security", "det": "generative",
     "purpose": "Generate authorized penetration testing checklists and methodologies",
     "tools": [], "tags": ["pentest", "checklist", "methodology"]},

    # === AUTOMATION (8 skills) ===
    {"slug": "workflow-builder", "name": "Workflow Builder", "cat": "automation", "det": "generative",
     "purpose": "Design and generate automated workflows for business processes",
     "tools": ["zapier", "n8n"], "tags": ["workflow", "automation", "process"]},
    {"slug": "cron-scheduler", "name": "Cron Scheduler", "cat": "automation", "det": "deterministic",
     "purpose": "Build and explain cron expressions for scheduled tasks",
     "tools": [], "tags": ["cron", "schedule", "timer"]},
    {"slug": "web-scraper", "name": "Web Scraper Builder", "cat": "automation", "det": "quasi_deterministic",
     "purpose": "Generate web scraping scripts with proper rate limiting and error handling",
     "tools": [], "tags": ["scraper", "web", "extraction"]},
    {"slug": "notification-system", "name": "Notification System", "cat": "automation", "det": "quasi_deterministic",
     "purpose": "Design and implement notification systems (email, Slack, webhook)",
     "tools": ["slack", "sendgrid"], "tags": ["notifications", "email", "slack"]},
    {"slug": "file-organizer", "name": "File Organizer", "cat": "automation", "det": "deterministic",
     "purpose": "Organize, rename, and sort files based on configurable rules",
     "tools": [], "tags": ["files", "organize", "sort"]},
    {"slug": "batch-processor", "name": "Batch Processor", "cat": "automation", "det": "deterministic",
     "purpose": "Process files or data in batches with parallel execution and error recovery",
     "tools": [], "tags": ["batch", "parallel", "process"]},
    {"slug": "integration-connector", "name": "Integration Connector", "cat": "automation", "det": "generative",
     "purpose": "Build integrations between services and APIs",
     "tools": [], "tags": ["integration", "api", "connector"]},
    {"slug": "task-orchestrator", "name": "Task Orchestrator", "cat": "automation", "det": "quasi_deterministic",
     "purpose": "Orchestrate complex multi-step tasks with dependency management",
     "tools": [], "tags": ["orchestration", "tasks", "workflow"]},

    # === RESEARCH (6 skills) ===
    {"slug": "web-research", "name": "Web Research", "cat": "research", "det": "generative",
     "purpose": "Conduct structured web research with source verification and citation",
     "tools": ["web-search", "web-fetch"], "tags": ["research", "search", "cite"]},
    {"slug": "paper-summary", "name": "Paper Summarizer", "cat": "research", "det": "generative",
     "purpose": "Summarize academic papers, extracting key findings, methodology, and limitations",
     "tools": ["arxiv"], "tags": ["papers", "academic", "summary"]},
    {"slug": "tech-comparison", "name": "Technology Comparison", "cat": "research", "det": "generative",
     "purpose": "Compare technologies, frameworks, and tools with objective criteria",
     "tools": ["web-search"], "tags": ["compare", "technology", "evaluation"]},
    {"slug": "market-research", "name": "Market Research", "cat": "research", "det": "generative",
     "purpose": "Research market trends, sizing, and competitive landscape",
     "tools": ["web-search"], "tags": ["market", "trends", "competitive"]},
    {"slug": "literature-review", "name": "Literature Review", "cat": "research", "det": "generative",
     "purpose": "Conduct systematic literature reviews on technical topics",
     "tools": ["web-search", "arxiv"], "tags": ["literature", "review", "academic"]},
    {"slug": "best-practices", "name": "Best Practices Finder", "cat": "research", "det": "generative",
     "purpose": "Research and compile best practices for specific technologies or domains",
     "tools": ["web-search"], "tags": ["best-practices", "standards", "patterns"]},

    # === PRODUCTIVITY (6 skills) ===
    {"slug": "project-planner", "name": "Project Planner", "cat": "productivity", "det": "generative",
     "purpose": "Create project plans with milestones, tasks, dependencies, and timelines",
     "tools": ["notion", "linear", "jira"], "tags": ["planning", "project", "tasks"]},
    {"slug": "standup-summary", "name": "Standup Summary", "cat": "productivity", "det": "generative",
     "purpose": "Generate daily standup summaries from git activity and task updates",
     "tools": ["github", "linear"], "tags": ["standup", "summary", "daily"]},
    {"slug": "decision-matrix", "name": "Decision Matrix", "cat": "productivity", "det": "generative",
     "purpose": "Build weighted decision matrices for comparing options",
     "tools": [], "tags": ["decision", "matrix", "comparison"]},
    {"slug": "retrospective", "name": "Retrospective Facilitator", "cat": "productivity", "det": "generative",
     "purpose": "Facilitate sprint retrospectives with structured formats (Start/Stop/Continue, 4Ls)",
     "tools": ["notion"], "tags": ["retro", "sprint", "team"]},
    {"slug": "time-tracker", "name": "Time Tracker", "cat": "productivity", "det": "deterministic",
     "purpose": "Track time spent on tasks and generate time reports",
     "tools": [], "tags": ["time", "tracking", "report"]},
    {"slug": "priority-sorter", "name": "Priority Sorter", "cat": "productivity", "det": "quasi_deterministic",
     "purpose": "Sort and prioritize tasks using frameworks (Eisenhower, RICE, MoSCoW)",
     "tools": [], "tags": ["priority", "sort", "framework"]},

    # === DESIGN (5 skills) ===
    {"slug": "ui-component", "name": "UI Component Generator", "cat": "design", "det": "generative",
     "purpose": "Generate UI component code from descriptions or design tokens",
     "tools": ["figma"], "tags": ["ui", "component", "frontend"]},
    {"slug": "color-palette", "name": "Color Palette Generator", "cat": "design", "det": "quasi_deterministic",
     "purpose": "Generate accessible, harmonious color palettes from brand colors",
     "tools": [], "tags": ["color", "palette", "design"]},
    {"slug": "icon-finder", "name": "Icon Finder", "cat": "design", "det": "deterministic",
     "purpose": "Find and suggest icons from popular icon libraries for specific use cases",
     "tools": [], "tags": ["icons", "find", "design"]},
    {"slug": "responsive-layout", "name": "Responsive Layout", "cat": "design", "det": "generative",
     "purpose": "Generate responsive CSS layouts using Grid, Flexbox, and modern techniques",
     "tools": [], "tags": ["responsive", "layout", "css"]},
    {"slug": "design-tokens", "name": "Design Tokens", "cat": "design", "det": "deterministic",
     "purpose": "Generate and manage design tokens for consistent theming",
     "tools": ["figma"], "tags": ["tokens", "theme", "variables"]},

    # === COMMUNICATION (4 skills) ===
    {"slug": "presentation-builder", "name": "Presentation Builder", "cat": "communication", "det": "generative",
     "purpose": "Create structured presentation outlines with speaker notes",
     "tools": ["google-slides"], "tags": ["presentation", "slides", "speak"]},
    {"slug": "diagram-generator", "name": "Diagram Generator", "cat": "communication", "det": "quasi_deterministic",
     "purpose": "Generate diagrams (flowcharts, sequence, architecture) in Mermaid or PlantUML",
     "tools": [], "tags": ["diagram", "mermaid", "flowchart"]},
    {"slug": "pr-description", "name": "PR Description Writer", "cat": "communication", "det": "generative",
     "purpose": "Generate detailed pull request descriptions with context and review guidelines",
     "tools": ["github", "gitlab"], "tags": ["pr", "description", "review"]},
    {"slug": "onboarding-guide", "name": "Onboarding Guide", "cat": "communication", "det": "generative",
     "purpose": "Create developer onboarding documentation for projects and teams",
     "tools": ["notion"], "tags": ["onboarding", "guide", "team"]},

    # === EDUCATION (4 skills) ===
    {"slug": "concept-explainer", "name": "Concept Explainer", "cat": "education", "det": "generative",
     "purpose": "Explain technical concepts at adjustable complexity levels",
     "tools": [], "tags": ["explain", "concept", "learn"]},
    {"slug": "quiz-generator", "name": "Quiz Generator", "cat": "education", "det": "generative",
     "purpose": "Generate quizzes and knowledge assessments for technical topics",
     "tools": [], "tags": ["quiz", "assessment", "test"]},
    {"slug": "flashcard-maker", "name": "Flashcard Maker", "cat": "education", "det": "generative",
     "purpose": "Generate spaced-repetition flashcards for learning technical material",
     "tools": [], "tags": ["flashcards", "learn", "memory"]},
    {"slug": "learning-path", "name": "Learning Path Designer", "cat": "education", "det": "generative",
     "purpose": "Design structured learning paths with resources and milestones",
     "tools": [], "tags": ["learning", "path", "curriculum"]},

    # === CREATIVE (4 skills) ===
    {"slug": "name-generator", "name": "Name Generator", "cat": "creative", "det": "generative",
     "purpose": "Generate names for projects, products, domains, and variables",
     "tools": [], "tags": ["names", "branding", "creative"]},
    {"slug": "ascii-art", "name": "ASCII Art Generator", "cat": "creative", "det": "generative",
     "purpose": "Generate ASCII art, banners, and text decorations",
     "tools": [], "tags": ["ascii", "art", "banner"]},
    {"slug": "story-generator", "name": "Story Generator", "cat": "creative", "det": "generative",
     "purpose": "Generate interactive stories, lore, and narrative content for games",
     "tools": [], "tags": ["story", "narrative", "games"]},
    {"slug": "prompt-engineer", "name": "Prompt Engineer", "cat": "creative", "det": "generative",
     "purpose": "Design, test, and optimize prompts for AI models",
     "tools": [], "tags": ["prompt", "engineering", "ai"]},

    # === GAMES (4 skills) ===
    {"slug": "game-dnd", "name": "D&D Game Master", "cat": "games", "det": "generative",
     "purpose": "Run a full D&D campaign as an AI Dungeon Master with rule enforcement",
     "tools": ["notion"], "tags": ["dnd", "rpg", "game"]},
    {"slug": "game-adventure", "name": "Choose Your Adventure", "cat": "games", "det": "generative",
     "purpose": "Run interactive choose-your-own-adventure games with branching narratives",
     "tools": [], "tags": ["adventure", "story", "interactive"]},
    {"slug": "game-zork", "name": "Interactive Fiction", "cat": "games", "det": "quasi_deterministic",
     "purpose": "Run Zork-style text adventure games with parser-based interaction",
     "tools": [], "tags": ["zork", "text-adventure", "parser"]},
    {"slug": "game-trivia", "name": "Trivia Game", "cat": "games", "det": "generative",
     "purpose": "Run interactive trivia games with scoring and leaderboards",
     "tools": [], "tags": ["trivia", "quiz", "game"]},

    # === SYSTEM (6 skills) ===
    {"slug": "health-check", "name": "Health Check", "cat": "system", "det": "deterministic",
     "purpose": "Run health checks across all registered tools and services",
     "tools": [], "tags": ["health", "check", "status"]},
    {"slug": "config-validator", "name": "Config Validator", "cat": "system", "det": "deterministic",
     "purpose": "Validate configuration files against schemas and best practices",
     "tools": [], "tags": ["config", "validate", "schema"]},
    {"slug": "system-status", "name": "System Status", "cat": "system", "det": "deterministic",
     "purpose": "Report Super-MCP system status including all registries, tools, and sessions",
     "tools": [], "tags": ["status", "system", "report"]},
    {"slug": "skill-composer", "name": "Skill Composer", "cat": "system", "det": "generative",
     "purpose": "Compose multiple skills into a single workflow execution",
     "tools": [], "tags": ["compose", "workflow", "chain"]},
    {"slug": "event-replay", "name": "Event Replay", "cat": "system", "det": "deterministic",
     "purpose": "Replay events from checkpoints for debugging and audit",
     "tools": [], "tags": ["replay", "events", "debug"]},
    {"slug": "artifact-export", "name": "Artifact Export", "cat": "system", "det": "deterministic",
     "purpose": "Export artifacts in various formats (Markdown, JSON, PDF, HTML)",
     "tools": [], "tags": ["export", "artifact", "format"]},
]


def generate_skill_md(skill: dict) -> str:
    """Generate a complete Skill.md from a definition dict."""
    tools_list = "\n".join(f"  - {t}" for t in skill.get("tools", [])) or "  (none)"
    tags_list = ", ".join(f'"{t}"' for t in skill.get("tags", []))
    composable = ", ".join(f'"{s["slug"]}"' for s in SKILL_DEFINITIONS[:3] if s["slug"] != skill["slug"])

    return f"""---
name: {skill['name']}
slug: {skill['slug']}
version: 1.0.0
category: {skill['cat']}
determinism: {skill['det']}
tool_dependencies:
{tools_list}
composable_with: [{composable}]
tags: [{tags_list}]
---

# {skill['name']}

## Purpose

{skill['purpose']}.

## Description

{skill['name']} is a canonical Super-MCP skill that provides structured, repeatable capability for {skill['purpose'].lower()}. It integrates with the kernel's safety layer, event bus, and checkpoint system to ensure all operations are auditable and replayable.

## Inputs

- `request` (string) [required]: The primary input describing what needs to be done
- `context` (object): Additional context such as file paths, configurations, or constraints
- `options` (object): Skill-specific options to control behavior

## Outputs

- `result` (string): The primary output of the skill execution
- `artifacts` (array): Any generated artifacts (files, documents, configs)
- `metadata` (object): Execution metadata including timing, token usage, and decisions made

## Constraints

- Must pass safety layer evaluation before execution
- All outputs are logged to the event bus
- Determinism level: {skill['det']}
- Must not exceed configured timeout (default: 300s)
- Must not produce outputs exceeding configured size limits

## Failure Modes

- Invalid input format \u2192 Return validation error with schema hints (recoverable)
- Tool dependency unavailable \u2192 Degrade gracefully or report missing tools (recoverable)
- Safety rule violation \u2192 Block execution and report violated rules (unrecoverable)
- Timeout exceeded \u2192 Return partial results with timeout indicator (recoverable)

## Examples

### Basic Usage

```
invoke {skill['slug']} --request "Describe what you need"
```

### With Context

```
invoke {skill['slug']} --request "Specific task" --context '{{"path": "/src", "lang": "python"}}'
```
"""


def generate_catalog(output_dir: Path) -> int:
    """Generate all Skill.md files to the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for skill in SKILL_DEFINITIONS:
        content = generate_skill_md(skill)
        filepath = output_dir / f"{skill['slug']}.md"
        filepath.write_text(content, encoding="utf-8")
        count += 1

    return count


if __name__ == "__main__":
    import sys
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("skills")
    n = generate_catalog(output)
    print(f"Generated {n} skill files in {output}")
