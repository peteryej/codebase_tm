"""
Commit history analysis engine
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import re
from git import Repo
from pydriller import Repository as PyDrillerRepo
from pydriller.domain.commit import Commit as PyDrillerCommit

from database.models import get_session, Repository, Commit, File, FileChange

logger = logging.getLogger(__name__)

class CommitAnalyzer:
    """Analyzes git commit history and extracts insights."""
    
    def __init__(self):
        """Initialize commit analyzer."""
        pass
    
    def analyze_repository_commits(self, repo_path: str, repo_id: int) -> Dict:
        """
        Analyze all commits in a repository.
        
        Args:
            repo_path: Path to local repository
            repo_id: Database repository ID
            
        Returns:
            Dictionary with analysis results
        """
        session = get_session()
        try:
            logger.info(f"Starting commit analysis for repository at {repo_path}")
            
            # Use PyDriller for detailed commit analysis
            commits_processed = 0
            files_tracked = {}
            authors = set()
            
            # Analyze commits using PyDriller
            for commit in PyDrillerRepo(repo_path).traverse_commits():
                try:
                    # Process commit
                    commit_data = self._process_commit(commit, repo_id, session)
                    if commit_data:
                        commits_processed += 1
                        authors.add(commit.author.name)
                        
                        # Track files
                        for modified_file in commit.modified_files:
                            if modified_file.filename:
                                files_tracked[modified_file.new_path or modified_file.old_path] = True
                    
                    # Log progress every 100 commits
                    if commits_processed % 100 == 0:
                        logger.info(f"Processed {commits_processed} commits")
                        
                except Exception as e:
                    logger.warning(f"Error processing commit {commit.hash}: {e}")
                    continue
            
            # Update repository statistics
            self._update_repository_stats(repo_id, commits_processed, len(files_tracked), len(authors), session)
            
            # Commit all changes
            session.commit()
            
            logger.info(f"Completed commit analysis: {commits_processed} commits, {len(files_tracked)} files, {len(authors)} authors")
            
            return {
                'success': True,
                'commits_processed': commits_processed,
                'files_tracked': len(files_tracked),
                'unique_authors': len(authors),
                'message': f'Successfully analyzed {commits_processed} commits'
            }
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error analyzing repository commits: {e}")
            return {
                'success': False,
                'error': 'Analysis failed',
                'details': str(e)
            }
        finally:
            session.close()
    
    def _process_commit(self, commit: PyDrillerCommit, repo_id: int, session) -> Optional[Dict]:
        """
        Process a single commit and store in database.
        
        Args:
            commit: PyDriller commit object
            repo_id: Database repository ID
            session: Database session
            
        Returns:
            Dictionary with commit data or None if error
        """
        try:
            # Check if commit already exists
            existing_commit = session.query(Commit).filter_by(id=commit.hash).first()
            if existing_commit:
                return None
            
            # Create commit record
            commit_record = Commit(
                id=commit.hash,
                repo_id=repo_id,
                author_name=commit.author.name,
                author_email=commit.author.email,
                committer_name=commit.committer.name if commit.committer else commit.author.name,
                committer_email=commit.committer.email if commit.committer else commit.author.email,
                timestamp=commit.committer_date,
                message=commit.msg,
                files_changed=len(commit.modified_files),
                insertions=commit.insertions,
                deletions=commit.deletions,
                is_merge=commit.merge,
                branch=self._get_commit_branch(commit)
            )
            
            session.add(commit_record)
            
            # Process modified files
            for modified_file in commit.modified_files:
                self._process_file_change(commit, modified_file, repo_id, session)
            
            return {
                'hash': commit.hash,
                'author': commit.author.name,
                'timestamp': commit.committer_date,
                'files_changed': len(commit.modified_files)
            }
            
        except Exception as e:
            logger.error(f"Error processing commit {commit.hash}: {e}")
            return None
    
    def _process_file_change(self, commit: PyDrillerCommit, modified_file, repo_id: int, session):
        """
        Process a file change within a commit.
        
        Args:
            commit: PyDriller commit object
            modified_file: Modified file object
            repo_id: Database repository ID
            session: Database session
        """
        try:
            if not modified_file.filename:
                return
            
            file_path = modified_file.new_path or modified_file.old_path
            if not file_path:
                return
            
            # Get or create file record
            file_record = session.query(File).filter_by(
                repo_id=repo_id,
                path=file_path
            ).first()
            
            if not file_record:
                file_record = File(
                    repo_id=repo_id,
                    path=file_path,
                    filename=modified_file.filename,
                    extension=self._get_file_extension(modified_file.filename),
                    created_at=commit.committer_date,
                    last_modified=commit.committer_date,
                    total_commits=1
                )
                session.add(file_record)
                session.flush()  # Get the ID
            else:
                # Update file record
                file_record.last_modified = commit.committer_date
                file_record.total_commits += 1
                if modified_file.nloc:
                    file_record.current_lines = modified_file.nloc
            
            # Determine change type
            change_type = self._determine_change_type(modified_file)
            
            # Create file change record
            file_change = FileChange(
                commit_id=commit.hash,
                file_id=file_record.id,
                change_type=change_type,
                insertions=modified_file.added_lines,
                deletions=modified_file.deleted_lines,
                old_path=modified_file.old_path if modified_file.old_path != modified_file.new_path else None
            )
            
            session.add(file_change)
            
        except Exception as e:
            logger.warning(f"Error processing file change for {modified_file.filename}: {e}")
    
    def _determine_change_type(self, modified_file) -> str:
        """
        Determine the type of change for a file.
        
        Args:
            modified_file: Modified file object
            
        Returns:
            Change type string
        """
        if modified_file.change_type.name == 'ADD':
            return 'added'
        elif modified_file.change_type.name == 'DELETE':
            return 'deleted'
        elif modified_file.change_type.name == 'RENAME':
            return 'renamed'
        elif modified_file.change_type.name == 'MODIFY':
            return 'modified'
        else:
            return 'unknown'
    
    def _get_file_extension(self, filename: str) -> Optional[str]:
        """
        Get file extension from filename.
        
        Args:
            filename: Name of the file
            
        Returns:
            File extension or None
        """
        if '.' in filename:
            return filename.split('.')[-1].lower()
        return None
    
    def _get_commit_branch(self, commit: PyDrillerCommit) -> Optional[str]:
        """
        Get branch name for a commit (simplified).
        
        Args:
            commit: PyDriller commit object
            
        Returns:
            Branch name or None
        """
        # This is a simplified approach - in practice, determining
        # the exact branch for each commit can be complex
        return 'main'  # Default assumption
    
    def _update_repository_stats(self, repo_id: int, total_commits: int, total_files: int, total_authors: int, session):
        """
        Update repository statistics.
        
        Args:
            repo_id: Database repository ID
            total_commits: Total number of commits
            total_files: Total number of files
            total_authors: Total number of unique authors
            session: Database session
        """
        try:
            repo = session.query(Repository).filter_by(id=repo_id).first()
            if repo:
                repo.total_commits = total_commits
                repo.total_files = total_files
                repo.last_analyzed = datetime.utcnow()
                repo.status = 'completed'
                
        except Exception as e:
            logger.error(f"Error updating repository stats: {e}")
    
    def get_commit_timeline(self, repo_id: int, days: int = 365) -> List[Dict]:
        """
        Get commit timeline for visualization.
        
        Args:
            repo_id: Database repository ID
            days: Number of days to include
            
        Returns:
            List of timeline data points
        """
        session = get_session()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            commits = session.query(Commit).filter(
                Commit.repo_id == repo_id,
                Commit.timestamp >= cutoff_date
            ).order_by(Commit.timestamp).all()
            
            # Group commits by date
            daily_commits = defaultdict(int)
            for commit in commits:
                date_key = commit.timestamp.date().isoformat()
                daily_commits[date_key] += 1
            
            # Convert to timeline format
            timeline = []
            for date_str, count in sorted(daily_commits.items()):
                timeline.append({
                    'date': date_str,
                    'commits': count
                })
            
            return timeline
            
        except Exception as e:
            logger.error(f"Error getting commit timeline: {e}")
            return []
        finally:
            session.close()
    
    def get_author_statistics(self, repo_id: int) -> List[Dict]:
        """
        Get author contribution statistics.
        
        Args:
            repo_id: Database repository ID
            
        Returns:
            List of author statistics
        """
        session = get_session()
        try:
            # Query commits grouped by author
            from sqlalchemy import func
            
            author_stats = session.query(
                Commit.author_name,
                Commit.author_email,
                func.count(Commit.id).label('commit_count'),
                func.sum(Commit.insertions).label('total_insertions'),
                func.sum(Commit.deletions).label('total_deletions'),
                func.min(Commit.timestamp).label('first_commit'),
                func.max(Commit.timestamp).label('last_commit')
            ).filter(
                Commit.repo_id == repo_id
            ).group_by(
                Commit.author_name, Commit.author_email
            ).order_by(
                func.count(Commit.id).desc()
            ).all()
            
            # Convert to list of dictionaries
            authors = []
            total_commits = sum(stat.commit_count for stat in author_stats)
            
            for stat in author_stats:
                authors.append({
                    'name': stat.author_name,
                    'email': stat.author_email,
                    'commits': stat.commit_count,
                    'insertions': stat.total_insertions or 0,
                    'deletions': stat.total_deletions or 0,
                    'percentage': round((stat.commit_count / total_commits) * 100, 2) if total_commits > 0 else 0,
                    'first_commit': stat.first_commit.isoformat() if stat.first_commit else None,
                    'last_commit': stat.last_commit.isoformat() if stat.last_commit else None,
                    'active_days': (stat.last_commit - stat.first_commit).days if stat.first_commit and stat.last_commit else 0
                })
            
            return authors
            
        except Exception as e:
            logger.error(f"Error getting author statistics: {e}")
            return []
        finally:
            session.close()
    
    def get_file_evolution(self, repo_id: int, file_path: str) -> Dict:
        """
        Get evolution history for a specific file.
        
        Args:
            repo_id: Database repository ID
            file_path: Path to the file
            
        Returns:
            Dictionary with file evolution data
        """
        session = get_session()
        try:
            # Get file record
            file_record = session.query(File).filter_by(
                repo_id=repo_id,
                path=file_path
            ).first()
            
            if not file_record:
                return {'error': 'File not found'}
            
            # Get file changes
            changes = session.query(FileChange, Commit).join(
                Commit, FileChange.commit_id == Commit.id
            ).filter(
                FileChange.file_id == file_record.id
            ).order_by(Commit.timestamp).all()
            
            # Build evolution timeline
            evolution = []
            cumulative_lines = 0
            
            for change, commit in changes:
                cumulative_lines += (change.insertions or 0) - (change.deletions or 0)
                
                evolution.append({
                    'commit_hash': commit.id,
                    'timestamp': commit.timestamp.isoformat(),
                    'author': commit.author_name,
                    'change_type': change.change_type,
                    'insertions': change.insertions or 0,
                    'deletions': change.deletions or 0,
                    'cumulative_lines': max(0, cumulative_lines),
                    'message': commit.message[:100] + '...' if len(commit.message) > 100 else commit.message
                })
            
            return {
                'file_path': file_path,
                'total_changes': len(evolution),
                'current_lines': file_record.current_lines,
                'created_at': file_record.created_at.isoformat() if file_record.created_at else None,
                'last_modified': file_record.last_modified.isoformat() if file_record.last_modified else None,
                'evolution': evolution
            }
            
        except Exception as e:
            logger.error(f"Error getting file evolution: {e}")
            return {'error': str(e)}
        finally:
            session.close()
    
    def get_commit_patterns(self, repo_id: int) -> Dict:
        """
        Analyze commit message patterns and trends.
        
        Args:
            repo_id: Database repository ID
            
        Returns:
            Dictionary with pattern analysis
        """
        session = get_session()
        try:
            commits = session.query(Commit).filter_by(repo_id=repo_id).all()
            
            # Analyze commit message patterns
            message_types = Counter()
            message_lengths = []
            hourly_commits = defaultdict(int)
            daily_commits = defaultdict(int)
            
            # Common commit message prefixes
            type_patterns = {
                'feat': r'^(feat|feature)',
                'fix': r'^(fix|bugfix)',
                'docs': r'^(docs|doc)',
                'style': r'^style',
                'refactor': r'^refactor',
                'test': r'^test',
                'chore': r'^chore',
                'merge': r'^(merge|merged)',
                'initial': r'^(initial|init)',
                'update': r'^update',
                'add': r'^(add|added)',
                'remove': r'^(remove|removed|delete)'
            }
            
            for commit in commits:
                message = commit.message.lower().strip()
                message_lengths.append(len(commit.message))
                
                # Categorize commit type
                categorized = False
                for type_name, pattern in type_patterns.items():
                    if re.match(pattern, message):
                        message_types[type_name] += 1
                        categorized = True
                        break
                
                if not categorized:
                    message_types['other'] += 1
                
                # Time-based patterns
                hour = commit.timestamp.hour
                day = commit.timestamp.strftime('%A')
                hourly_commits[hour] += 1
                daily_commits[day] += 1
            
            return {
                'total_commits': len(commits),
                'message_types': dict(message_types.most_common()),
                'average_message_length': sum(message_lengths) / len(message_lengths) if message_lengths else 0,
                'hourly_distribution': dict(hourly_commits),
                'daily_distribution': dict(daily_commits),
                'most_active_hour': max(hourly_commits.items(), key=lambda x: x[1])[0] if hourly_commits else None,
                'most_active_day': max(daily_commits.items(), key=lambda x: x[1])[0] if daily_commits else None
            }
            
        except Exception as e:
            logger.error(f"Error analyzing commit patterns: {e}")
            return {'error': str(e)}
        finally:
            session.close()
    
    def find_feature_introduction_commits(self, repo_id: int, feature_keywords: List[str]) -> List[Dict]:
        """
        Find commits that likely introduced a specific feature.
        
        Args:
            repo_id: Database repository ID
            feature_keywords: List of keywords related to the feature
            
        Returns:
            List of commits that match the feature keywords
        """
        session = get_session()
        try:
            if not feature_keywords:
                return []
            
            # Build search patterns for commit messages
            search_patterns = []
            for keyword in feature_keywords:
                # Create case-insensitive pattern
                search_patterns.append(f"%{keyword.lower()}%")
            
            # Query commits that match any of the keywords
            from sqlalchemy import or_, func
            
            # Create OR conditions for each keyword
            conditions = []
            for pattern in search_patterns:
                conditions.append(func.lower(Commit.message).like(pattern))
            
            matching_commits = session.query(Commit).filter(
                Commit.repo_id == repo_id,
                or_(*conditions)
            ).order_by(Commit.timestamp).all()
            
            # Convert to list of dictionaries with relevance scoring
            commits_with_scores = []
            for commit in matching_commits:
                # Calculate relevance score based on keyword matches
                message_lower = commit.message.lower()
                score = 0
                matched_keywords = []
                
                for keyword in feature_keywords:
                    keyword_lower = keyword.lower()
                    if keyword_lower in message_lower:
                        # Higher score for exact matches
                        score += message_lower.count(keyword_lower) * 2
                        matched_keywords.append(keyword)
                        
                        # Bonus for keywords in commit title (first line)
                        first_line = commit.message.split('\n')[0].lower()
                        if keyword_lower in first_line:
                            score += 3
                
                # Bonus for commits that look like feature additions
                feature_indicators = ['add', 'implement', 'create', 'introduce', 'new', 'feat']
                for indicator in feature_indicators:
                    if indicator in message_lower:
                        score += 1
                
                # Penalty for merge commits (usually not the original implementation)
                if commit.is_merge:
                    score -= 2
                
                commits_with_scores.append({
                    'commit': commit,
                    'score': score,
                    'matched_keywords': matched_keywords
                })
            
            # Sort by relevance score (highest first) and then by date (earliest first for same score)
            commits_with_scores.sort(key=lambda x: (-x['score'], x['commit'].timestamp))
            
            # Convert to the expected format
            result_commits = []
            for item in commits_with_scores[:10]:  # Limit to top 10 most relevant
                commit = item['commit']
                result_commits.append({
                    'hash': commit.id,
                    'author': commit.author_name,
                    'timestamp': commit.timestamp.isoformat(),
                    'message': commit.message.strip(),
                    'files_changed': commit.files_changed,
                    'insertions': commit.insertions,
                    'deletions': commit.deletions,
                    'is_merge': commit.is_merge,
                    'relevance_score': item['score'],
                    'matched_keywords': item['matched_keywords']
                })
            
            logger.info(f"Found {len(result_commits)} commits matching feature keywords: {feature_keywords}")
            return result_commits
            
        except Exception as e:
            logger.error(f"Error finding feature introduction commits: {e}")
            return []
        finally:
            session.close()
    
    def get_commits_by_file_pattern(self, repo_id: int, file_pattern: str) -> List[Dict]:
        """
        Get commits that modified files matching a pattern.
        
        Args:
            repo_id: Database repository ID
            file_pattern: Pattern to match file paths (can include wildcards)
            
        Returns:
            List of commits that modified matching files
        """
        session = get_session()
        try:
            from sqlalchemy import distinct
            
            # Find files matching the pattern
            matching_files = session.query(File).filter(
                File.repo_id == repo_id,
                File.path.like(file_pattern.replace('*', '%'))
            ).all()
            
            if not matching_files:
                return []
            
            file_ids = [f.id for f in matching_files]
            
            # Find commits that modified these files
            commits = session.query(Commit).join(
                FileChange, Commit.id == FileChange.commit_id
            ).filter(
                FileChange.file_id.in_(file_ids)
            ).order_by(Commit.timestamp).distinct().all()
            
            # Convert to list format
            result_commits = []
            for commit in commits:
                result_commits.append({
                    'hash': commit.id,
                    'author': commit.author_name,
                    'timestamp': commit.timestamp.isoformat(),
                    'message': commit.message.strip(),
                    'files_changed': commit.files_changed,
                    'insertions': commit.insertions,
                    'deletions': commit.deletions,
                    'is_merge': commit.is_merge
                })
            
            return result_commits
            
        except Exception as e:
            logger.error(f"Error getting commits by file pattern: {e}")
            return []
        finally:
            session.close()