"""
GitHub API client for fetching repository metadata
"""

import os
import re
import logging
from typing import Dict, List, Optional, Tuple
from github import Github, GithubException
from github.Repository import Repository as GithubRepo
import requests

logger = logging.getLogger(__name__)

class GitHubClient:
    """Client for interacting with GitHub API."""
    
    def __init__(self):
        """Initialize GitHub client with optional token."""
        self.token = os.getenv('GITHUB_TOKEN')
        self.github = Github(self.token) if self.token else Github()
        self.session = requests.Session()
        
        # Set up authentication headers if token is available
        if self.token:
            self.session.headers.update({'Authorization': f'token {self.token}'})
    
    def parse_github_url(self, url: str) -> Optional[Tuple[str, str]]:
        """
        Parse GitHub URL to extract owner and repository name.
        
        Args:
            url: GitHub repository URL
            
        Returns:
            Tuple of (owner, repo_name) or None if invalid
        """
        # Support various GitHub URL formats
        patterns = [
            r'https://github\.com/([^/]+)/([^/]+)/?$',
            r'https://github\.com/([^/]+)/([^/]+)\.git$',
            r'git@github\.com:([^/]+)/([^/]+)\.git$',
            r'github\.com/([^/]+)/([^/]+)/?$'
        ]
        
        for pattern in patterns:
            match = re.match(pattern, url.strip())
            if match:
                owner, repo = match.groups()
                # Remove .git suffix if present
                repo = repo.replace('.git', '')
                return owner, repo
        
        logger.error(f"Invalid GitHub URL format: {url}")
        return None
    
    def validate_repository(self, url: str) -> Dict:
        """
        Validate that the repository exists and is accessible.
        
        Args:
            url: GitHub repository URL
            
        Returns:
            Dictionary with validation results
        """
        try:
            parsed = self.parse_github_url(url)
            if not parsed:
                return {
                    'valid': False,
                    'error': 'Invalid GitHub URL format',
                    'details': 'URL must be in format: https://github.com/owner/repo'
                }
            
            owner, repo_name = parsed
            repo = self.github.get_repo(f"{owner}/{repo_name}")
            
            # Check if repository is public
            if repo.private:
                return {
                    'valid': False,
                    'error': 'Repository is private',
                    'details': 'Only public repositories are supported'
                }
            
            # Check repository size (approximate)
            if repo.size > 1000000:  # 1GB in KB
                return {
                    'valid': False,
                    'error': 'Repository too large',
                    'details': f'Repository size ({repo.size} KB) exceeds limit'
                }
            
            return {
                'valid': True,
                'owner': owner,
                'name': repo_name,
                'full_name': repo.full_name,
                'description': repo.description,
                'language': repo.language,
                'stars': repo.stargazers_count,
                'forks': repo.forks_count,
                'size': repo.size,
                'created_at': repo.created_at,
                'updated_at': repo.updated_at,
                'default_branch': repo.default_branch
            }
            
        except GithubException as e:
            if e.status == 404:
                return {
                    'valid': False,
                    'error': 'Repository not found',
                    'details': 'Repository does not exist or is not accessible'
                }
            elif e.status == 403:
                return {
                    'valid': False,
                    'error': 'Access forbidden',
                    'details': 'API rate limit exceeded or insufficient permissions'
                }
            else:
                return {
                    'valid': False,
                    'error': f'GitHub API error: {e.status}',
                    'details': str(e)
                }
        except Exception as e:
            logger.error(f"Error validating repository {url}: {e}")
            return {
                'valid': False,
                'error': 'Validation failed',
                'details': str(e)
            }
    
    def get_repository_metadata(self, owner: str, repo_name: str) -> Dict:
        """
        Get comprehensive repository metadata.
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            
        Returns:
            Dictionary with repository metadata
        """
        try:
            repo = self.github.get_repo(f"{owner}/{repo_name}")
            
            # Get basic repository info
            metadata = {
                'name': repo.name,
                'full_name': repo.full_name,
                'owner': owner,
                'description': repo.description,
                'language': repo.language,
                'size': repo.size,
                'stars': repo.stargazers_count,
                'forks': repo.forks_count,
                'watchers': repo.watchers_count,
                'open_issues': repo.open_issues_count,
                'created_at': repo.created_at,
                'updated_at': repo.updated_at,
                'pushed_at': repo.pushed_at,
                'default_branch': repo.default_branch,
                'topics': repo.get_topics(),
                'license': repo.license.name if repo.license else None,
                'has_wiki': repo.has_wiki,
                'has_pages': repo.has_pages,
                'has_issues': repo.has_issues,
                'archived': repo.archived,
                'disabled': repo.disabled
            }
            
            # Get languages
            try:
                languages = repo.get_languages()
                metadata['languages'] = languages
            except Exception as e:
                logger.warning(f"Could not fetch languages: {e}")
                metadata['languages'] = {}
            
            # Get contributors (limited to avoid rate limiting)
            try:
                contributors = []
                for contributor in repo.get_contributors()[:10]:  # Limit to top 10
                    contributors.append({
                        'login': contributor.login,
                        'contributions': contributor.contributions,
                        'avatar_url': contributor.avatar_url
                    })
                metadata['top_contributors'] = contributors
            except Exception as e:
                logger.warning(f"Could not fetch contributors: {e}")
                metadata['top_contributors'] = []
            
            # Get recent releases
            try:
                releases = []
                for release in repo.get_releases()[:5]:  # Limit to 5 most recent
                    releases.append({
                        'tag_name': release.tag_name,
                        'name': release.title,
                        'published_at': release.published_at,
                        'prerelease': release.prerelease
                    })
                metadata['recent_releases'] = releases
            except Exception as e:
                logger.warning(f"Could not fetch releases: {e}")
                metadata['recent_releases'] = []
            
            return metadata
            
        except Exception as e:
            logger.error(f"Error fetching metadata for {owner}/{repo_name}: {e}")
            raise
    
    def get_commit_stats(self, owner: str, repo_name: str) -> Dict:
        """
        Get commit statistics from GitHub API.
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            
        Returns:
            Dictionary with commit statistics
        """
        try:
            repo = self.github.get_repo(f"{owner}/{repo_name}")
            
            # Get commit activity (weekly stats for the last year)
            try:
                commit_activity = repo.get_stats_commit_activity()
                weekly_commits = []
                if commit_activity:
                    for week in commit_activity:
                        weekly_commits.append({
                            'week': week.week,
                            'total': week.total,
                            'days': week.days
                        })
            except Exception as e:
                logger.warning(f"Could not fetch commit activity: {e}")
                weekly_commits = []
            
            # Get contributor stats
            try:
                contributor_stats = []
                stats = repo.get_stats_contributors()
                if stats:
                    for stat in stats[:10]:  # Limit to top 10
                        contributor_stats.append({
                            'author': stat.author.login,
                            'total_commits': stat.total,
                            'weeks': len(stat.weeks)
                        })
            except Exception as e:
                logger.warning(f"Could not fetch contributor stats: {e}")
                contributor_stats = []
            
            return {
                'weekly_commits': weekly_commits,
                'contributor_stats': contributor_stats
            }
            
        except Exception as e:
            logger.error(f"Error fetching commit stats for {owner}/{repo_name}: {e}")
            return {'weekly_commits': [], 'contributor_stats': []}
    
    def check_rate_limit(self) -> Dict:
        """
        Check current GitHub API rate limit status.
        
        Returns:
            Dictionary with rate limit information
        """
        try:
            rate_limit = self.github.get_rate_limit()
            return {
                'core': {
                    'limit': rate_limit.core.limit,
                    'remaining': rate_limit.core.remaining,
                    'reset': rate_limit.core.reset
                },
                'search': {
                    'limit': rate_limit.search.limit,
                    'remaining': rate_limit.search.remaining,
                    'reset': rate_limit.search.reset
                }
            }
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return {}
    
    def is_rate_limited(self) -> bool:
        """
        Check if we're currently rate limited.
        
        Returns:
            True if rate limited, False otherwise
        """
        try:
            rate_limit = self.check_rate_limit()
            return rate_limit.get('core', {}).get('remaining', 0) < 10
        except:
            return False