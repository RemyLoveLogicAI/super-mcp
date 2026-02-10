"""Tool catalog — 50+ AI/developer tool definitions with OAuth configs.

Each tool is a verified integration with health checks, auth handling,
and rate limiting. Tools are registered with the kernel at boot.
"""

from __future__ import annotations

from src.kernel.types import (
    Capability,
    OAuthConfig,
    ToolAuthType,
    ToolDefinition,
    ToolEndpoint,
)


def _tool(
    slug: str,
    name: str,
    desc: str,
    auth: ToolAuthType = ToolAuthType.NONE,
    oauth: OAuthConfig | None = None,
    endpoints: list[ToolEndpoint] | None = None,
    rate_limit: int | None = None,
    tags: list[str] | None = None,
    verified: bool = True,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        slug=slug,
        description=desc,
        auth_type=auth,
        oauth_config=oauth,
        endpoints=endpoints or [],
        rate_limit_rpm=rate_limit,
        tags=tags or [],
        verified=verified,
    )


TOOL_CATALOG: list[ToolDefinition] = [
    # === AI / LLM Providers ===
    _tool("openai", "OpenAI", "GPT-4, DALL-E, Whisper, Embeddings APIs",
          auth=ToolAuthType.BEARER, rate_limit=60,
          endpoints=[ToolEndpoint(url="https://api.openai.com/v1/chat/completions")],
          tags=["ai", "llm", "embeddings", "vision"]),
    _tool("anthropic", "Anthropic", "Claude API for advanced reasoning and coding",
          auth=ToolAuthType.API_KEY, rate_limit=60,
          endpoints=[ToolEndpoint(url="https://api.anthropic.com/v1/messages")],
          tags=["ai", "llm", "reasoning"]),
    _tool("google-ai", "Google AI", "Gemini models for multimodal AI tasks",
          auth=ToolAuthType.API_KEY, rate_limit=60,
          endpoints=[ToolEndpoint(url="https://generativelanguage.googleapis.com/v1/models")],
          tags=["ai", "llm", "multimodal"]),
    _tool("cohere", "Cohere", "Rerank, Embed, and Generate APIs",
          auth=ToolAuthType.BEARER, rate_limit=100,
          tags=["ai", "embeddings", "rerank"]),
    _tool("replicate", "Replicate", "Run open-source ML models in the cloud",
          auth=ToolAuthType.BEARER, rate_limit=60,
          tags=["ai", "ml", "inference"]),
    _tool("huggingface", "Hugging Face", "Inference API for thousands of open-source models",
          auth=ToolAuthType.BEARER, rate_limit=30,
          tags=["ai", "ml", "open-source"]),
    _tool("stability-ai", "Stability AI", "Stable Diffusion and image generation APIs",
          auth=ToolAuthType.API_KEY, rate_limit=30,
          tags=["ai", "image-generation"]),
    _tool("eleven-labs", "ElevenLabs", "AI voice synthesis and text-to-speech",
          auth=ToolAuthType.API_KEY, rate_limit=20,
          tags=["ai", "voice", "tts"]),
    _tool("deepgram", "Deepgram", "Speech-to-text and audio intelligence",
          auth=ToolAuthType.API_KEY, rate_limit=30,
          tags=["ai", "stt", "audio"]),
    _tool("pinecone", "Pinecone", "Vector database for semantic search and RAG",
          auth=ToolAuthType.API_KEY, rate_limit=100,
          tags=["ai", "vector-db", "rag"]),

    # === Code & Version Control ===
    _tool("github", "GitHub", "Repos, issues, PRs, Actions, and code search",
          auth=ToolAuthType.OAUTH2,
          oauth=OAuthConfig(
              authorization_url="https://github.com/login/oauth/authorize",
              token_url="https://github.com/login/oauth/access_token",
              scopes=["repo", "read:user", "read:org"],
              client_id_env="GITHUB_CLIENT_ID",
              client_secret_env="GITHUB_CLIENT_SECRET",
          ),
          rate_limit=5000,
          tags=["code", "git", "ci-cd"]),
    _tool("gitlab", "GitLab", "GitLab API for repos, pipelines, and merge requests",
          auth=ToolAuthType.OAUTH2,
          oauth=OAuthConfig(
              authorization_url="https://gitlab.com/oauth/authorize",
              token_url="https://gitlab.com/oauth/token",
              scopes=["api", "read_user"],
              client_id_env="GITLAB_CLIENT_ID",
              client_secret_env="GITLAB_CLIENT_SECRET",
          ),
          rate_limit=2000,
          tags=["code", "git", "ci-cd"]),
    _tool("bitbucket", "Bitbucket", "Bitbucket API for repos and pipelines",
          auth=ToolAuthType.OAUTH2,
          oauth=OAuthConfig(
              authorization_url="https://bitbucket.org/site/oauth2/authorize",
              token_url="https://bitbucket.org/site/oauth2/access_token",
              scopes=["repository", "pullrequest"],
              client_id_env="BITBUCKET_CLIENT_ID",
              client_secret_env="BITBUCKET_CLIENT_SECRET",
          ),
          tags=["code", "git"]),
    _tool("sourcegraph", "Sourcegraph", "Universal code search across repositories",
          auth=ToolAuthType.BEARER,
          tags=["code", "search"]),

    # === Project Management ===
    _tool("linear", "Linear", "Issue tracking and project management",
          auth=ToolAuthType.OAUTH2,
          oauth=OAuthConfig(
              authorization_url="https://linear.app/oauth/authorize",
              token_url="https://api.linear.app/oauth/token",
              scopes=["read", "write"],
              client_id_env="LINEAR_CLIENT_ID",
              client_secret_env="LINEAR_CLIENT_SECRET",
          ),
          tags=["project", "issues", "tracking"]),
    _tool("jira", "Jira", "Atlassian Jira issue tracking and agile boards",
          auth=ToolAuthType.OAUTH2,
          oauth=OAuthConfig(
              authorization_url="https://auth.atlassian.com/authorize",
              token_url="https://auth.atlassian.com/oauth/token",
              scopes=["read:jira-work", "write:jira-work"],
              client_id_env="JIRA_CLIENT_ID",
              client_secret_env="JIRA_CLIENT_SECRET",
          ),
          tags=["project", "issues", "agile"]),
    _tool("asana", "Asana", "Work management and team collaboration",
          auth=ToolAuthType.OAUTH2,
          oauth=OAuthConfig(
              authorization_url="https://app.asana.com/-/oauth_authorize",
              token_url="https://app.asana.com/-/oauth_token",
              scopes=[],
              client_id_env="ASANA_CLIENT_ID",
              client_secret_env="ASANA_CLIENT_SECRET",
          ),
          tags=["project", "tasks", "team"]),
    _tool("trello", "Trello", "Kanban boards and task management",
          auth=ToolAuthType.API_KEY,
          tags=["project", "kanban", "tasks"]),

    # === Documentation & Knowledge ===
    _tool("notion", "Notion", "Docs, databases, wikis, and project management",
          auth=ToolAuthType.OAUTH2,
          oauth=OAuthConfig(
              authorization_url="https://api.notion.com/v1/oauth/authorize",
              token_url="https://api.notion.com/v1/oauth/token",
              scopes=[],
              client_id_env="NOTION_CLIENT_ID",
              client_secret_env="NOTION_CLIENT_SECRET",
          ),
          tags=["docs", "wiki", "database"]),
    _tool("confluence", "Confluence", "Team documentation and knowledge base",
          auth=ToolAuthType.OAUTH2,
          oauth=OAuthConfig(
              authorization_url="https://auth.atlassian.com/authorize",
              token_url="https://auth.atlassian.com/oauth/token",
              scopes=["read:confluence-content.all", "write:confluence-content"],
              client_id_env="CONFLUENCE_CLIENT_ID",
              client_secret_env="CONFLUENCE_CLIENT_SECRET",
          ),
          tags=["docs", "wiki", "knowledge"]),
    _tool("google-docs", "Google Docs", "Document creation and collaboration",
          auth=ToolAuthType.OAUTH2,
          oauth=OAuthConfig(
              authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
              token_url="https://oauth2.googleapis.com/token",
              scopes=["https://www.googleapis.com/auth/documents"],
              client_id_env="GOOGLE_CLIENT_ID",
              client_secret_env="GOOGLE_CLIENT_SECRET",
          ),
          tags=["docs", "google", "collaboration"]),

    # === Communication ===
    _tool("slack", "Slack", "Messaging, channels, and workflow automation",
          auth=ToolAuthType.OAUTH2,
          oauth=OAuthConfig(
              authorization_url="https://slack.com/oauth/v2/authorize",
              token_url="https://slack.com/api/oauth.v2.access",
              scopes=["chat:write", "channels:read"],
              client_id_env="SLACK_CLIENT_ID",
              client_secret_env="SLACK_CLIENT_SECRET",
          ),
          tags=["communication", "messaging", "team"]),
    _tool("discord", "Discord", "Community messaging and bot integration",
          auth=ToolAuthType.OAUTH2,
          oauth=OAuthConfig(
              authorization_url="https://discord.com/api/oauth2/authorize",
              token_url="https://discord.com/api/oauth2/token",
              scopes=["bot", "messages.read"],
              client_id_env="DISCORD_CLIENT_ID",
              client_secret_env="DISCORD_CLIENT_SECRET",
          ),
          tags=["communication", "community"]),
    _tool("gmail", "Gmail", "Email sending and management",
          auth=ToolAuthType.OAUTH2,
          oauth=OAuthConfig(
              authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
              token_url="https://oauth2.googleapis.com/token",
              scopes=["https://www.googleapis.com/auth/gmail.send"],
              client_id_env="GOOGLE_CLIENT_ID",
              client_secret_env="GOOGLE_CLIENT_SECRET",
          ),
          tags=["email", "communication"]),
    _tool("sendgrid", "SendGrid", "Transactional and marketing email API",
          auth=ToolAuthType.API_KEY,
          tags=["email", "transactional"]),
    _tool("twilio", "Twilio", "SMS, voice, and communication APIs",
          auth=ToolAuthType.BASIC,
          tags=["sms", "voice", "communication"]),

    # === Cloud & Infrastructure ===
    _tool("aws", "AWS", "Amazon Web Services SDK for cloud infrastructure",
          auth=ToolAuthType.API_KEY,
          tags=["cloud", "infrastructure", "aws"]),
    _tool("gcp", "Google Cloud", "Google Cloud Platform APIs",
          auth=ToolAuthType.OAUTH2,
          oauth=OAuthConfig(
              authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
              token_url="https://oauth2.googleapis.com/token",
              scopes=["https://www.googleapis.com/auth/cloud-platform"],
              client_id_env="GCP_CLIENT_ID",
              client_secret_env="GCP_CLIENT_SECRET",
          ),
          tags=["cloud", "infrastructure", "gcp"]),
    _tool("azure", "Azure", "Microsoft Azure cloud services",
          auth=ToolAuthType.OAUTH2,
          oauth=OAuthConfig(
              authorization_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
              token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
              scopes=["https://management.azure.com/.default"],
              client_id_env="AZURE_CLIENT_ID",
              client_secret_env="AZURE_CLIENT_SECRET",
          ),
          tags=["cloud", "infrastructure", "azure"]),
    _tool("vercel", "Vercel", "Deployment and hosting platform",
          auth=ToolAuthType.BEARER,
          tags=["deploy", "hosting", "frontend"]),
    _tool("netlify", "Netlify", "Web deployment and serverless functions",
          auth=ToolAuthType.BEARER,
          tags=["deploy", "hosting", "jamstack"]),
    _tool("docker-hub", "Docker Hub", "Container image registry",
          auth=ToolAuthType.BEARER,
          tags=["containers", "docker", "registry"]),
    _tool("terraform-registry", "Terraform Registry", "Infrastructure as Code module registry",
          auth=ToolAuthType.API_KEY,
          tags=["iac", "terraform", "infrastructure"]),

    # === Database & Storage ===
    _tool("supabase", "Supabase", "Postgres database, auth, storage, and realtime",
          auth=ToolAuthType.API_KEY,
          tags=["database", "postgres", "baas"]),
    _tool("firebase", "Firebase", "Google's app platform with Firestore and Auth",
          auth=ToolAuthType.API_KEY,
          tags=["database", "auth", "baas"]),
    _tool("planetscale", "PlanetScale", "Serverless MySQL-compatible database",
          auth=ToolAuthType.API_KEY,
          tags=["database", "mysql", "serverless"]),
    _tool("redis-cloud", "Redis Cloud", "In-memory database and caching",
          auth=ToolAuthType.API_KEY,
          tags=["cache", "database", "redis"]),
    _tool("s3", "AWS S3", "Object storage service",
          auth=ToolAuthType.API_KEY,
          tags=["storage", "files", "aws"]),

    # === Monitoring & Observability ===
    _tool("datadog", "Datadog", "Infrastructure monitoring and APM",
          auth=ToolAuthType.API_KEY,
          tags=["monitoring", "apm", "observability"]),
    _tool("sentry", "Sentry", "Error tracking and performance monitoring",
          auth=ToolAuthType.BEARER,
          tags=["errors", "monitoring", "debugging"]),
    _tool("pagerduty", "PagerDuty", "Incident management and alerting",
          auth=ToolAuthType.API_KEY,
          tags=["alerting", "incidents", "oncall"]),
    _tool("grafana", "Grafana", "Dashboards and observability platform",
          auth=ToolAuthType.API_KEY,
          tags=["dashboards", "visualization", "monitoring"]),

    # === Search & Web ===
    _tool("web-search", "Web Search", "General web search via SerpAPI or similar",
          auth=ToolAuthType.API_KEY,
          tags=["search", "web"]),
    _tool("web-fetch", "Web Fetch", "Fetch and parse web pages",
          auth=ToolAuthType.NONE,
          tags=["web", "fetch", "scrape"]),
    _tool("algolia", "Algolia", "Search-as-a-service API",
          auth=ToolAuthType.API_KEY,
          tags=["search", "indexing"]),

    # === Design ===
    _tool("figma", "Figma", "Design file inspection and asset export",
          auth=ToolAuthType.OAUTH2,
          oauth=OAuthConfig(
              authorization_url="https://www.figma.com/oauth",
              token_url="https://www.figma.com/api/oauth/token",
              scopes=["file_read"],
              client_id_env="FIGMA_CLIENT_ID",
              client_secret_env="FIGMA_CLIENT_SECRET",
          ),
          tags=["design", "ui", "assets"]),
    _tool("google-slides", "Google Slides", "Presentation creation and editing",
          auth=ToolAuthType.OAUTH2,
          oauth=OAuthConfig(
              authorization_url="https://accounts.google.com/o/oauth2/v2/auth",
              token_url="https://oauth2.googleapis.com/token",
              scopes=["https://www.googleapis.com/auth/presentations"],
              client_id_env="GOOGLE_CLIENT_ID",
              client_secret_env="GOOGLE_CLIENT_SECRET",
          ),
          tags=["presentation", "design"]),

    # === Automation ===
    _tool("zapier", "Zapier", "Workflow automation connecting 5000+ apps",
          auth=ToolAuthType.API_KEY,
          tags=["automation", "workflow", "integration"]),
    _tool("n8n", "n8n", "Open-source workflow automation",
          auth=ToolAuthType.API_KEY,
          tags=["automation", "workflow", "open-source"]),
    _tool("github-actions", "GitHub Actions", "CI/CD workflow automation",
          auth=ToolAuthType.BEARER,
          tags=["ci-cd", "automation", "github"]),
    _tool("gitlab-ci", "GitLab CI", "GitLab continuous integration",
          auth=ToolAuthType.BEARER,
          tags=["ci-cd", "automation", "gitlab"]),

    # === Package Registries ===
    _tool("npm-registry", "npm Registry", "Node.js package registry",
          auth=ToolAuthType.BEARER,
          tags=["packages", "npm", "node"]),
    _tool("pypi", "PyPI", "Python package index",
          auth=ToolAuthType.API_KEY,
          tags=["packages", "python"]),
    _tool("crates-io", "Crates.io", "Rust package registry",
          auth=ToolAuthType.API_KEY,
          tags=["packages", "rust"]),

    # === Research & Data ===
    _tool("arxiv", "arXiv", "Academic paper search and retrieval",
          auth=ToolAuthType.NONE,
          tags=["research", "papers", "academic"]),
    _tool("wolfram-alpha", "Wolfram Alpha", "Computational knowledge engine",
          auth=ToolAuthType.API_KEY,
          tags=["math", "computation", "knowledge"]),
    _tool("nvd-api", "NVD", "National Vulnerability Database API",
          auth=ToolAuthType.API_KEY,
          tags=["security", "cve", "vulnerabilities"]),
    _tool("wordpress", "WordPress", "Blog and CMS API",
          auth=ToolAuthType.OAUTH2,
          oauth=OAuthConfig(
              authorization_url="https://public-api.wordpress.com/oauth2/authorize",
              token_url="https://public-api.wordpress.com/oauth2/token",
              scopes=["global"],
              client_id_env="WORDPRESS_CLIENT_ID",
              client_secret_env="WORDPRESS_CLIENT_SECRET",
          ),
          tags=["cms", "blog", "content"]),
]


def get_all_tools() -> list[ToolDefinition]:
    return list(TOOL_CATALOG)


def get_tools_by_tag(tag: str) -> list[ToolDefinition]:
    return [t for t in TOOL_CATALOG if tag in t.tags]


def get_tool_by_slug(slug: str) -> ToolDefinition | None:
    for t in TOOL_CATALOG:
        if t.slug == slug:
            return t
    return None
