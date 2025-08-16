"""
Repository cloning and management system
"""

import os
import shutil
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import git
from git import Repo, InvalidGitRepositoryError
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

class RepositoryManager:
    """Manages local repository cloning and operations."""
    
    def __init__(self):
        """Initialize repository manager."""
        self.repos_path = Path(os.getenv('REPOS_PATH', './data/repos'))
        self.repos_path.mkdir(parents=True, exist_ok=True)
        self.max_repo_size = int(os.getenv('MAX_REPO_SIZE', 10000))
    
    def _get_repo_local_path(self, owner: str, repo_name: str) -> Path:
        """
        Get local path for a repository.
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            
        Returns:
            Path object for local repository
        """
        # Create a safe directory name
        safe_name = f"{owner}_{repo_name}".replace('/', '_').replace('\\', '_')
        return self.repos_path / safe_name
    
    def _get_repo_url(self, owner: str, repo_name: str) -> str:
        """
        Get clone URL for a repository.
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            
        Returns:
            HTTPS clone URL
        """
        return f"https://github.com/{owner}/{repo_name}.git"
    
    def clone_repository(self, owner: str, repo_name: str, force_refresh: bool = False) -> Dict:
        """
        Clone a repository locally.
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            force_refresh: Whether to force re-clone if exists
            
        Returns:
            Dictionary with clone results
        """
        local_path = self._get_repo_local_path(owner, repo_name)
        repo_url = self._get_repo_url(owner, repo_name)
        
        try:
            # Check if repository already exists
            if local_path.exists() and not force_refresh:
                try:
                    repo = Repo(local_path)
                    if repo.remotes.origin.url.endswith(f"{owner}/{repo_name}.git"):
                        logger.info(f"Repository {owner}/{repo_name} already exists locally")
                        return {
                            'success': True,
                            'path': str(local_path),
                            'action': 'existing',
                            'message': 'Repository already exists locally'
                        }
                except InvalidGitRepositoryError:
                    # Directory exists but is not a valid git repo, remove it
                    shutil.rmtree(local_path)
            
            # Remove existing directory if force refresh
            if force_refresh and local_path.exists():
                shutil.rmtree(local_path)
            
            logger.info(f"Cloning repository {owner}/{repo_name} to {local_path}")
            
            # Clone with shallow clone first to check size
            repo = Repo.clone_from(
                repo_url,
                local_path,
                depth=1,  # Shallow clone initially
                progress=self._clone_progress_callback
            )
            
            # Check if we need to unshallow based on commit count estimation
            try:
                # Get approximate commit count from first commit
                commits = list(repo.iter_commits(max_count=1))
                if commits:
                    # Unshallow the repository for full analysis
                    repo.git.fetch('--unshallow')
                    logger.info(f"Unshallowed repository {owner}/{repo_name}")
            except Exception as e:
                logger.warning(f"Could not unshallow repository: {e}")
            
            # Verify the clone was successful
            if not repo.heads:
                raise Exception("No branches found in cloned repository")
            
            return {
                'success': True,
                'path': str(local_path),
                'action': 'cloned',
                'message': f'Successfully cloned {owner}/{repo_name}',
                'default_branch': repo.active_branch.name if repo.active_branch else 'main'
            }
            
        except git.exc.GitCommandError as e:
            error_msg = f"Git command failed: {e}"
            logger.error(error_msg)
            
            # Clean up failed clone
            if local_path.exists():
                shutil.rmtree(local_path)
            
            return {
                'success': False,
                'error': 'Clone failed',
                'details': error_msg
            }
        except Exception as e:
            error_msg = f"Failed to clone repository: {e}"
            logger.error(error_msg)
            
            # Clean up failed clone
            if local_path.exists():
                shutil.rmtree(local_path)
            
            return {
                'success': False,
                'error': 'Clone failed',
                'details': error_msg
            }
    
    def _clone_progress_callback(self, op_code, cur_count, max_count=None, message=''):
        """Callback for clone progress."""
        if max_count:
            percentage = (cur_count / max_count) * 100
            logger.info(f"Clone progress: {percentage:.1f}% - {message}")
    
    def get_repository(self, owner: str, repo_name: str) -> Optional[Repo]:
        """
        Get a local repository object.
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            
        Returns:
            GitPython Repo object or None if not found
        """
        local_path = self._get_repo_local_path(owner, repo_name)
        
        try:
            if local_path.exists():
                return Repo(local_path)
        except InvalidGitRepositoryError:
            logger.error(f"Invalid git repository at {local_path}")
        
        return None
    
    def update_repository(self, owner: str, repo_name: str) -> Dict:
        """
        Update a local repository by pulling latest changes.
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            
        Returns:
            Dictionary with update results
        """
        try:
            repo = self.get_repository(owner, repo_name)
            if not repo:
                return {
                    'success': False,
                    'error': 'Repository not found locally',
                    'details': 'Repository must be cloned first'
                }
            
            # Fetch latest changes
            origin = repo.remotes.origin
            origin.fetch()
            
            # Get current branch
            current_branch = repo.active_branch
            
            # Pull changes
            origin.pull(current_branch.name)
            
            return {
                'success': True,
                'message': f'Successfully updated {owner}/{repo_name}',
                'branch': current_branch.name
            }
            
        except Exception as e:
            error_msg = f"Failed to update repository: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': 'Update failed',
                'details': error_msg
            }
    
    def get_repository_info(self, owner: str, repo_name: str) -> Dict:
        """
        Get information about a local repository.
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            
        Returns:
            Dictionary with repository information
        """
        try:
            repo = self.get_repository(owner, repo_name)
            if not repo:
                return {
                    'exists': False,
                    'error': 'Repository not found locally'
                }
            
            # Get basic info
            info = {
                'exists': True,
                'path': str(repo.working_dir),
                'bare': repo.bare,
                'active_branch': repo.active_branch.name if repo.active_branch else None,
                'branches': [branch.name for branch in repo.branches],
                'remotes': [remote.name for remote in repo.remotes],
                'tags': [tag.name for tag in repo.tags],
                'is_dirty': repo.is_dirty(),
                'untracked_files': repo.untracked_files
            }
            
            # Get commit count (approximate)
            try:
                commit_count = sum(1 for _ in repo.iter_commits())
                info['total_commits'] = commit_count
            except Exception as e:
                logger.warning(f"Could not count commits: {e}")
                info['total_commits'] = 0
            
            # Get latest commit info
            try:
                latest_commit = repo.head.commit
                info['latest_commit'] = {
                    'hash': latest_commit.hexsha,
                    'author': latest_commit.author.name,
                    'date': latest_commit.committed_datetime,
                    'message': latest_commit.message.strip()
                }
            except Exception as e:
                logger.warning(f"Could not get latest commit: {e}")
                info['latest_commit'] = None
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting repository info: {e}")
            return {
                'exists': False,
                'error': str(e)
            }
    
    def delete_repository(self, owner: str, repo_name: str) -> Dict:
        """
        Delete a local repository.
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            
        Returns:
            Dictionary with deletion results
        """
        local_path = self._get_repo_local_path(owner, repo_name)
        
        try:
            if local_path.exists():
                shutil.rmtree(local_path)
                logger.info(f"Deleted local repository {owner}/{repo_name}")
                return {
                    'success': True,
                    'message': f'Successfully deleted {owner}/{repo_name}'
                }
            else:
                return {
                    'success': True,
                    'message': f'Repository {owner}/{repo_name} was not found locally'
                }
                
        except Exception as e:
            error_msg = f"Failed to delete repository: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': 'Deletion failed',
                'details': error_msg
            }
    
    def list_local_repositories(self) -> List[Dict]:
        """
        List all locally cloned repositories.
        
        Returns:
            List of repository information dictionaries
        """
        repositories = []
        
        try:
            for repo_dir in self.repos_path.iterdir():
                if repo_dir.is_dir():
                    try:
                        repo = Repo(repo_dir)
                        
                        # Extract owner and name from directory name
                        dir_name = repo_dir.name
                        if '_' in dir_name:
                            owner, repo_name = dir_name.split('_', 1)
                        else:
                            owner, repo_name = 'unknown', dir_name
                        
                        # Get basic info
                        repo_info = {
                            'owner': owner,
                            'name': repo_name,
                            'path': str(repo_dir),
                            'active_branch': repo.active_branch.name if repo.active_branch else None,
                            'is_dirty': repo.is_dirty()
                        }
                        
                        # Get latest commit
                        try:
                            latest_commit = repo.head.commit
                            repo_info['latest_commit_date'] = latest_commit.committed_datetime
                            repo_info['latest_commit_author'] = latest_commit.author.name
                        except:
                            repo_info['latest_commit_date'] = None
                            repo_info['latest_commit_author'] = None
                        
                        repositories.append(repo_info)
                        
                    except InvalidGitRepositoryError:
                        logger.warning(f"Invalid git repository found: {repo_dir}")
                        continue
                    except Exception as e:
                        logger.warning(f"Error reading repository {repo_dir}: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error listing repositories: {e}")
        
        return repositories
    
    def cleanup_old_repositories(self, days_old: int = 30) -> Dict:
        """
        Clean up repositories older than specified days.
        
        Args:
            days_old: Number of days after which to consider repo old
            
        Returns:
            Dictionary with cleanup results
        """
        try:
            repositories = self.list_local_repositories()
            cleaned_count = 0
            errors = []
            
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            for repo_info in repositories:
                if repo_info.get('latest_commit_date'):
                    # Convert to datetime if it's not already
                    commit_date = repo_info['latest_commit_date']
                    if hasattr(commit_date, 'replace'):  # It's a datetime
                        commit_date = commit_date.replace(tzinfo=None)
                    
                    if commit_date < cutoff_date:
                        result = self.delete_repository(repo_info['owner'], repo_info['name'])
                        if result['success']:
                            cleaned_count += 1
                        else:
                            errors.append(f"{repo_info['owner']}/{repo_info['name']}: {result.get('error', 'Unknown error')}")
            
            return {
                'success': True,
                'cleaned_count': cleaned_count,
                'errors': errors,
                'message': f'Cleaned up {cleaned_count} old repositories'
            }
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {
                'success': False,
                'error': 'Cleanup failed',
                'details': str(e)
            }
    
    def get_disk_usage(self) -> Dict:
        """
        Get disk usage information for the repositories directory.
        
        Returns:
            Dictionary with disk usage information
        """
        try:
            total_size = 0
            repo_count = 0
            
            for repo_dir in self.repos_path.iterdir():
                if repo_dir.is_dir():
                    repo_count += 1
                    for file_path in repo_dir.rglob('*'):
                        if file_path.is_file():
                            total_size += file_path.stat().st_size
            
            return {
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'total_size_gb': round(total_size / (1024 * 1024 * 1024), 2),
                'repository_count': repo_count,
                'repos_path': str(self.repos_path)
            }
            
        except Exception as e:
            logger.error(f"Error calculating disk usage: {e}")
            return {
                'error': str(e)
            }