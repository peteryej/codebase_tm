"""
Code ownership analysis module
"""

import logging
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from sqlalchemy import func

from database.models import get_session, Repository, Commit, File, FileChange, Ownership

logger = logging.getLogger(__name__)

class OwnershipAnalyzer:
    """Analyzes code ownership patterns and contributor statistics."""
    
    def __init__(self):
        """Initialize ownership analyzer."""
        pass
    
    def analyze_code_ownership(self, repo_id: int) -> Dict:
        """
        Analyze code ownership for all files in a repository.
        
        Args:
            repo_id: Database repository ID
            
        Returns:
            Dictionary with ownership analysis results
        """
        session = get_session()
        try:
            logger.info(f"Starting code ownership analysis for repository {repo_id}")
            
            # Clear existing ownership data
            # First get the ownership IDs to delete
            ownership_ids = session.query(Ownership.id).join(File).filter(File.repo_id == repo_id).all()
            if ownership_ids:
                ownership_ids = [oid[0] for oid in ownership_ids]
                session.query(Ownership).filter(Ownership.id.in_(ownership_ids)).delete(synchronize_session=False)
            
            # Get all files in the repository
            files = session.query(File).filter_by(repo_id=repo_id).all()
            
            ownership_records = 0
            files_analyzed = 0
            
            for file_record in files:
                try:
                    ownership_data = self._analyze_file_ownership(file_record, session)
                    if ownership_data:
                        for author_data in ownership_data:
                            ownership_record = Ownership(
                                file_id=file_record.id,
                                author_name=author_data['author_name'],
                                author_email=author_data['author_email'],
                                lines_contributed=author_data['lines_contributed'],
                                commits_count=author_data['commits_count'],
                                percentage=author_data['percentage'],
                                first_contribution=author_data['first_contribution'],
                                last_contribution=author_data['last_contribution']
                            )
                            session.add(ownership_record)
                            ownership_records += 1
                        
                        files_analyzed += 1
                        
                        # Log progress every 100 files
                        if files_analyzed % 100 == 0:
                            logger.info(f"Analyzed ownership for {files_analyzed} files")
                            
                except Exception as e:
                    logger.warning(f"Error analyzing ownership for file {file_record.path}: {e}")
                    continue
            
            # Commit all ownership records
            session.commit()
            
            logger.info(f"Completed ownership analysis: {files_analyzed} files, {ownership_records} ownership records")
            
            return {
                'success': True,
                'files_analyzed': files_analyzed,
                'ownership_records': ownership_records,
                'message': f'Successfully analyzed ownership for {files_analyzed} files'
            }
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error analyzing code ownership: {e}")
            return {
                'success': False,
                'error': 'Ownership analysis failed',
                'details': str(e)
            }
        finally:
            session.close()
    
    def _analyze_file_ownership(self, file_record: File, session) -> List[Dict]:
        """
        Analyze ownership for a single file.
        
        Args:
            file_record: File database record
            
        Returns:
            List of ownership data for each contributor
        """
        try:
            # Get all changes for this file
            changes = session.query(FileChange, Commit).join(
                Commit, FileChange.commit_id == Commit.id
            ).filter(
                FileChange.file_id == file_record.id
            ).all()
            
            if not changes:
                return []
            
            # Track contributions by author
            author_contributions = defaultdict(lambda: {
                'lines_added': 0,
                'lines_removed': 0,
                'commits': 0,
                'first_contribution': None,
                'last_contribution': None,
                'email': None
            })
            
            for change, commit in changes:
                author = commit.author_name
                author_contributions[author]['lines_added'] += change.insertions or 0
                author_contributions[author]['lines_removed'] += change.deletions or 0
                author_contributions[author]['commits'] += 1
                author_contributions[author]['email'] = commit.author_email
                
                # Track contribution dates
                if (author_contributions[author]['first_contribution'] is None or 
                    commit.timestamp < author_contributions[author]['first_contribution']):
                    author_contributions[author]['first_contribution'] = commit.timestamp
                
                if (author_contributions[author]['last_contribution'] is None or 
                    commit.timestamp > author_contributions[author]['last_contribution']):
                    author_contributions[author]['last_contribution'] = commit.timestamp
            
            # Calculate ownership percentages
            total_lines_added = sum(data['lines_added'] for data in author_contributions.values())
            
            ownership_data = []
            for author, data in author_contributions.items():
                # Calculate net contribution (lines added - lines removed by this author)
                net_contribution = max(0, data['lines_added'] - data['lines_removed'])
                
                # Calculate percentage based on lines added (not net)
                percentage = (data['lines_added'] / total_lines_added * 100) if total_lines_added > 0 else 0
                
                ownership_data.append({
                    'author_name': author,
                    'author_email': data['email'],
                    'lines_contributed': net_contribution,
                    'commits_count': data['commits'],
                    'percentage': round(percentage, 2),
                    'first_contribution': data['first_contribution'],
                    'last_contribution': data['last_contribution']
                })
            
            # Sort by percentage (highest first)
            ownership_data.sort(key=lambda x: x['percentage'], reverse=True)
            
            return ownership_data
            
        except Exception as e:
            logger.error(f"Error analyzing file ownership for {file_record.path}: {e}")
            return []
    
    def get_file_ownership(self, repo_id: int, file_path: str) -> Dict:
        """
        Get ownership information for a specific file.
        
        Args:
            repo_id: Database repository ID
            file_path: Path to the file
            
        Returns:
            Dictionary with file ownership data
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
            
            # Get ownership records
            ownership_records = session.query(Ownership).filter_by(
                file_id=file_record.id
            ).order_by(Ownership.percentage.desc()).all()
            
            owners = []
            for record in ownership_records:
                owners.append({
                    'author_name': record.author_name,
                    'author_email': record.author_email,
                    'lines_contributed': record.lines_contributed,
                    'commits_count': record.commits_count,
                    'percentage': record.percentage,
                    'first_contribution': record.first_contribution.isoformat() if record.first_contribution else None,
                    'last_contribution': record.last_contribution.isoformat() if record.last_contribution else None
                })
            
            return {
                'file_path': file_path,
                'total_owners': len(owners),
                'primary_owner': owners[0] if owners else None,
                'owners': owners
            }
            
        except Exception as e:
            logger.error(f"Error getting file ownership: {e}")
            return {'error': str(e)}
        finally:
            session.close()
    
    def get_author_ownership_summary(self, repo_id: int, author_name: str) -> Dict:
        """
        Get ownership summary for a specific author.
        
        Args:
            repo_id: Database repository ID
            author_name: Name of the author
            
        Returns:
            Dictionary with author ownership summary
        """
        session = get_session()
        try:
            # Get all ownership records for this author
            ownership_records = session.query(Ownership, File).join(
                File, Ownership.file_id == File.id
            ).filter(
                File.repo_id == repo_id,
                Ownership.author_name == author_name
            ).all()
            
            if not ownership_records:
                return {'error': 'Author not found or has no contributions'}
            
            # Calculate summary statistics
            total_files = len(ownership_records)
            total_lines = sum(record.Ownership.lines_contributed for record in ownership_records)
            total_commits = sum(record.Ownership.commits_count for record in ownership_records)
            
            # Files where this author is the primary owner (>50% ownership)
            primary_files = [
                record for record in ownership_records 
                if record.Ownership.percentage > 50
            ]
            
            # Group by file extension
            extension_stats = defaultdict(lambda: {'files': 0, 'lines': 0, 'commits': 0})
            for record in ownership_records:
                ext = record.File.extension or 'no_extension'
                extension_stats[ext]['files'] += 1
                extension_stats[ext]['lines'] += record.Ownership.lines_contributed
                extension_stats[ext]['commits'] += record.Ownership.commits_count
            
            # Get contribution timeline
            first_contribution = min(
                record.Ownership.first_contribution for record in ownership_records
                if record.Ownership.first_contribution
            )
            last_contribution = max(
                record.Ownership.last_contribution for record in ownership_records
                if record.Ownership.last_contribution
            )
            
            return {
                'author_name': author_name,
                'total_files_contributed': total_files,
                'total_lines_contributed': total_lines,
                'total_commits': total_commits,
                'primary_owner_files': len(primary_files),
                'first_contribution': first_contribution.isoformat() if first_contribution else None,
                'last_contribution': last_contribution.isoformat() if last_contribution else None,
                'active_days': (last_contribution - first_contribution).days if first_contribution and last_contribution else 0,
                'extension_breakdown': dict(extension_stats),
                'top_files': [
                    {
                        'path': record.File.path,
                        'percentage': record.Ownership.percentage,
                        'lines': record.Ownership.lines_contributed,
                        'commits': record.Ownership.commits_count
                    }
                    for record in sorted(ownership_records, key=lambda x: x.Ownership.percentage, reverse=True)[:10]
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting author ownership summary: {e}")
            return {'error': str(e)}
        finally:
            session.close()
    
    def get_repository_ownership_overview(self, repo_id: int) -> Dict:
        """
        Get overall ownership overview for a repository.
        
        Args:
            repo_id: Database repository ID
            
        Returns:
            Dictionary with repository ownership overview
        """
        session = get_session()
        try:
            # Get all ownership records
            ownership_records = session.query(Ownership, File).join(
                File, Ownership.file_id == File.id
            ).filter(File.repo_id == repo_id).all()
            
            if not ownership_records:
                return {'error': 'No ownership data found'}
            
            # Calculate author statistics
            author_stats = defaultdict(lambda: {
                'files': 0,
                'lines': 0,
                'commits': 0,
                'primary_files': 0,
                'extensions': set()
            })
            
            for record in ownership_records:
                author = record.Ownership.author_name
                author_stats[author]['files'] += 1
                author_stats[author]['lines'] += record.Ownership.lines_contributed
                author_stats[author]['commits'] += record.Ownership.commits_count
                
                if record.Ownership.percentage > 50:
                    author_stats[author]['primary_files'] += 1
                
                if record.File.extension:
                    author_stats[author]['extensions'].add(record.File.extension)
            
            # Convert to list and sort by lines contributed
            authors = []
            total_lines = sum(stats['lines'] for stats in author_stats.values())
            
            for author, stats in author_stats.items():
                authors.append({
                    'name': author,
                    'files_contributed': stats['files'],
                    'lines_contributed': stats['lines'],
                    'commits': stats['commits'],
                    'primary_owner_files': stats['primary_files'],
                    'extensions_worked_on': len(stats['extensions']),
                    'percentage_of_codebase': round((stats['lines'] / total_lines * 100), 2) if total_lines > 0 else 0
                })
            
            authors.sort(key=lambda x: x['lines_contributed'], reverse=True)
            
            # File extension statistics
            extension_stats = defaultdict(lambda: {
                'files': 0,
                'total_lines': 0,
                'unique_authors': set()
            })
            
            for record in ownership_records:
                ext = record.File.extension or 'no_extension'
                extension_stats[ext]['files'] += 1
                extension_stats[ext]['total_lines'] += record.Ownership.lines_contributed
                extension_stats[ext]['unique_authors'].add(record.Ownership.author_name)
            
            # Convert extension stats
            extensions = []
            for ext, stats in extension_stats.items():
                extensions.append({
                    'extension': ext,
                    'files': stats['files'],
                    'total_lines': stats['total_lines'],
                    'unique_authors': len(stats['unique_authors'])
                })
            
            extensions.sort(key=lambda x: x['total_lines'], reverse=True)
            
            # Ownership concentration analysis
            total_files = len(set(record.File.id for record in ownership_records))
            files_with_single_owner = len([
                file_id for file_id in set(record.File.id for record in ownership_records)
                if len([r for r in ownership_records if r.File.id == file_id]) == 1
            ])
            
            return {
                'total_authors': len(authors),
                'total_files': total_files,
                'total_lines_tracked': total_lines,
                'files_with_single_owner': files_with_single_owner,
                'ownership_concentration': round((files_with_single_owner / total_files * 100), 2) if total_files > 0 else 0,
                'top_contributors': authors[:10],
                'extension_breakdown': extensions[:10],
                'collaboration_score': round((1 - files_with_single_owner / total_files) * 100, 2) if total_files > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting repository ownership overview: {e}")
            return {'error': str(e)}
        finally:
            session.close()
    
    def get_ownership_heatmap_data(self, repo_id: int) -> Dict:
        """
        Get data for ownership heatmap visualization.
        
        Args:
            repo_id: Database repository ID
            
        Returns:
            Dictionary with heatmap data
        """
        session = get_session()
        try:
            # Get ownership data with file paths
            ownership_data = session.query(Ownership, File).join(
                File, Ownership.file_id == File.id
            ).filter(
                File.repo_id == repo_id,
                Ownership.percentage > 10  # Only include significant ownership
            ).order_by(Ownership.percentage.desc()).all()
            
            # Organize data by directory structure
            heatmap_data = []
            
            for record in ownership_data:
                file_path = record.File.path
                path_parts = file_path.split('/')
                
                heatmap_data.append({
                    'file_path': file_path,
                    'directory': '/'.join(path_parts[:-1]) if len(path_parts) > 1 else '',
                    'filename': path_parts[-1],
                    'author': record.Ownership.author_name,
                    'percentage': record.Ownership.percentage,
                    'lines': record.Ownership.lines_contributed,
                    'commits': record.Ownership.commits_count,
                    'extension': record.File.extension
                })
            
            return {
                'heatmap_data': heatmap_data,
                'total_files': len(heatmap_data)
            }
            
        except Exception as e:
            logger.error(f"Error getting ownership heatmap data: {e}")
            return {'error': str(e)}
        finally:
            session.close()
    
    def find_code_experts(self, repo_id: int, file_extension: str = None) -> List[Dict]:
        """
        Find code experts for specific file types or overall.
        
        Args:
            repo_id: Database repository ID
            file_extension: Optional file extension to filter by
            
        Returns:
            List of expert information
        """
        session = get_session()
        try:
            query = session.query(Ownership, File).join(
                File, Ownership.file_id == File.id
            ).filter(File.repo_id == repo_id)
            
            if file_extension:
                query = query.filter(File.extension == file_extension)
            
            ownership_records = query.all()
            
            # Calculate expertise scores
            expert_scores = defaultdict(lambda: {
                'files': 0,
                'total_percentage': 0,
                'lines': 0,
                'commits': 0,
                'primary_files': 0
            })
            
            for record in ownership_records:
                author = record.Ownership.author_name
                expert_scores[author]['files'] += 1
                expert_scores[author]['total_percentage'] += record.Ownership.percentage
                expert_scores[author]['lines'] += record.Ownership.lines_contributed
                expert_scores[author]['commits'] += record.Ownership.commits_count
                
                if record.Ownership.percentage > 50:
                    expert_scores[author]['primary_files'] += 1
            
            # Calculate final expertise scores and convert to list
            experts = []
            for author, scores in expert_scores.items():
                avg_ownership = scores['total_percentage'] / scores['files'] if scores['files'] > 0 else 0
                expertise_score = (
                    avg_ownership * 0.4 +  # Average ownership percentage
                    (scores['primary_files'] / scores['files'] * 100) * 0.3 +  # Primary ownership ratio
                    min(scores['files'] / 10 * 100, 100) * 0.3  # File coverage (capped at 100%)
                )
                
                experts.append({
                    'author': author,
                    'expertise_score': round(expertise_score, 2),
                    'files_contributed': scores['files'],
                    'average_ownership': round(avg_ownership, 2),
                    'primary_owner_files': scores['primary_files'],
                    'total_lines': scores['lines'],
                    'total_commits': scores['commits']
                })
            
            # Sort by expertise score
            experts.sort(key=lambda x: x['expertise_score'], reverse=True)
            
            return experts[:10]  # Return top 10 experts
            
        except Exception as e:
            logger.error(f"Error finding code experts: {e}")
            return []
        finally:
            session.close()