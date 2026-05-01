"""GitHub provider package — token isolation lives in github_client.py only."""

from app.git_provider.github.github_provider import GitHubProvider

__all__ = ["GitHubProvider"]
