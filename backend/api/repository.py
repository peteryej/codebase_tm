"""
Repository API endpoints
"""

import logging
import threading
from flask import Blueprint, request, jsonify
from datetime import datetime

from git_ops.github_client import GitHubClient
from git_ops.repo_manager import RepositoryManager
from analyzers.commit_analyzer import CommitAnalyzer
from analyzers.ownership_analyzer import OwnershipAnalyzer
from database.models import get_session, Repository

logger = logging.getLogger(__name__)

repository_bp = Blueprint('repository', __name__)

# Global analysis status tracking
analysis_status = {}
analysis_lock = threading.Lock()

@repository_bp.route('/validate', methods=['POST'])
def validate_repository():
    """
    Validate a GitHub repository URL.
    
    Expected JSON:
    {
        "url": "https://github.com/owner/repo"
    }
    """
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'Repository URL is required'}), 400
        
        url = data['url'].strip()
        if not url:
            return jsonify({'error': 'Repository URL cannot be empty'}), 400
        
        # Validate with GitHub client
        github_client = GitHubClient()
        validation_result = github_client.validate_repository(url)
        
        if validation_result['valid']:
            return jsonify({
                'valid': True,
                'repository': {
                    'owner': validation_result['owner'],
                    'name': validation_result['name'],
                    'full_name': validation_result['full_name'],
                    'description': validation_result.get('description'),
                    'language': validation_result.get('language'),
                    'stars': validation_result.get('stars', 0),
                    'forks': validation_result.get('forks', 0),
                    'size': validation_result.get('size', 0),
                    'created_at': validation_result.get('created_at').isoformat() if validation_result.get('created_at') else None,
                    'updated_at': validation_result.get('updated_at').isoformat() if validation_result.get('updated_at') else None
                }
            })
        else:
            return jsonify({
                'valid': False,
                'error': validation_result['error'],
                'details': validation_result.get('details', '')
            }), 400
            
    except Exception as e:
        logger.error(f"Error validating repository: {e}")
        return jsonify({'error': 'Validation failed', 'details': str(e)}), 500

@repository_bp.route('/analyze', methods=['POST'])
def analyze_repository():
    """
    Start analysis of a GitHub repository.
    
    Expected JSON:
    {
        "url": "https://github.com/owner/repo",
        "force_refresh": false
    }
    """
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'Repository URL is required'}), 400
        
        url = data['url'].strip()
        force_refresh = data.get('force_refresh', False)
        
        # Validate repository first
        github_client = GitHubClient()
        validation_result = github_client.validate_repository(url)
        
        if not validation_result['valid']:
            return jsonify({
                'error': validation_result['error'],
                'details': validation_result.get('details', '')
            }), 400
        
        owner = validation_result['owner']
        repo_name = validation_result['name']
        repo_key = f"{owner}/{repo_name}"
        
        # Check if analysis is already in progress
        with analysis_lock:
            if repo_key in analysis_status and analysis_status[repo_key]['status'] == 'analyzing':
                return jsonify({
                    'message': 'Analysis already in progress',
                    'analysis_id': analysis_status[repo_key]['analysis_id'],
                    'status': 'analyzing'
                })
        
        # Check if repository already exists in database
        session = get_session()
        try:
            existing_repo = session.query(Repository).filter_by(url=url).first()
            
            if existing_repo and not force_refresh:
                if existing_repo.status == 'completed':
                    return jsonify({
                        'message': 'Repository already analyzed',
                        'repository_id': existing_repo.id,
                        'status': 'completed',
                        'last_analyzed': existing_repo.last_analyzed.isoformat() if existing_repo.last_analyzed else None
                    })
                elif existing_repo.status == 'analyzing':
                    return jsonify({
                        'message': 'Analysis in progress',
                        'repository_id': existing_repo.id,
                        'status': 'analyzing'
                    })
            
            # Create or update repository record
            if existing_repo:
                repo_record = existing_repo
                repo_record.status = 'analyzing'
                repo_record.error_message = None
            else:
                repo_record = Repository(
                    url=url,
                    name=repo_name,
                    owner=owner,
                    description=validation_result.get('description'),
                    language=validation_result.get('language'),
                    status='analyzing'
                )
                session.add(repo_record)
            
            session.commit()
            repo_id = repo_record.id
            
        finally:
            session.close()
        
        # Start analysis in background thread
        analysis_id = f"{repo_key}_{int(datetime.now().timestamp())}"
        
        with analysis_lock:
            analysis_status[repo_key] = {
                'analysis_id': analysis_id,
                'status': 'analyzing',
                'progress': 0,
                'current_step': 'Starting analysis',
                'started_at': datetime.now().isoformat()
            }
        
        # Start background analysis
        analysis_thread = threading.Thread(
            target=_analyze_repository_background,
            args=(repo_id, owner, repo_name, repo_key, force_refresh)
        )
        analysis_thread.daemon = True
        analysis_thread.start()
        
        return jsonify({
            'message': 'Analysis started',
            'analysis_id': analysis_id,
            'repository_id': repo_id,
            'status': 'analyzing'
        })
        
    except Exception as e:
        logger.error(f"Error starting repository analysis: {e}")
        return jsonify({'error': 'Failed to start analysis', 'details': str(e)}), 500

@repository_bp.route('/<int:repo_id>/status', methods=['GET'])
def get_analysis_status(repo_id):
    """Get the current analysis status for a repository."""
    try:
        session = get_session()
        try:
            repo = session.query(Repository).filter_by(id=repo_id).first()
            if not repo:
                return jsonify({'error': 'Repository not found'}), 404
            
            repo_key = f"{repo.owner}/{repo.name}"
            
            # Check in-memory status first
            with analysis_lock:
                if repo_key in analysis_status:
                    status_info = analysis_status[repo_key].copy()
                    status_info['repository_id'] = repo_id
                    status_info['repository_name'] = repo.name
                    status_info['repository_owner'] = repo.owner
                    return jsonify(status_info)
            
            # Return database status
            return jsonify({
                'repository_id': repo_id,
                'repository_name': repo.name,
                'repository_owner': repo.owner,
                'status': repo.status,
                'last_analyzed': repo.last_analyzed.isoformat() if repo.last_analyzed else None,
                'total_commits': repo.total_commits,
                'total_files': repo.total_files,
                'error_message': repo.error_message
            })
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error getting analysis status: {e}")
        return jsonify({'error': 'Failed to get status', 'details': str(e)}), 500

@repository_bp.route('/<int:repo_id>/timeline', methods=['GET'])
def get_commit_timeline(repo_id):
    """Get commit timeline data for visualization."""
    try:
        days = request.args.get('days', 365, type=int)
        
        analyzer = CommitAnalyzer()
        timeline_data = analyzer.get_commit_timeline(repo_id, days)
        
        return jsonify({
            'repository_id': repo_id,
            'timeline': timeline_data,
            'days': days
        })
        
    except Exception as e:
        logger.error(f"Error getting commit timeline: {e}")
        return jsonify({'error': 'Failed to get timeline', 'details': str(e)}), 500

@repository_bp.route('/<int:repo_id>/authors', methods=['GET'])
def get_author_statistics(repo_id):
    """Get author contribution statistics."""
    try:
        analyzer = CommitAnalyzer()
        author_stats = analyzer.get_author_statistics(repo_id)
        
        return jsonify({
            'repository_id': repo_id,
            'authors': author_stats
        })
        
    except Exception as e:
        logger.error(f"Error getting author statistics: {e}")
        return jsonify({'error': 'Failed to get author statistics', 'details': str(e)}), 500

@repository_bp.route('/<int:repo_id>/ownership', methods=['GET'])
def get_ownership_overview(repo_id):
    """Get code ownership overview."""
    try:
        analyzer = OwnershipAnalyzer()
        ownership_data = analyzer.get_repository_ownership_overview(repo_id)
        
        return jsonify({
            'repository_id': repo_id,
            'ownership': ownership_data
        })
        
    except Exception as e:
        logger.error(f"Error getting ownership overview: {e}")
        return jsonify({'error': 'Failed to get ownership data', 'details': str(e)}), 500

@repository_bp.route('/<int:repo_id>/ownership/file', methods=['GET'])
def get_file_ownership(repo_id):
    """Get ownership data for a specific file."""
    try:
        file_path = request.args.get('path')
        if not file_path:
            return jsonify({'error': 'File path is required'}), 400
        
        analyzer = OwnershipAnalyzer()
        ownership_data = analyzer.get_file_ownership(repo_id, file_path)
        
        return jsonify({
            'repository_id': repo_id,
            'file_ownership': ownership_data
        })
        
    except Exception as e:
        logger.error(f"Error getting file ownership: {e}")
        return jsonify({'error': 'Failed to get file ownership', 'details': str(e)}), 500

@repository_bp.route('/<int:repo_id>/ownership/heatmap', methods=['GET'])
def get_ownership_heatmap(repo_id):
    """Get ownership heatmap data."""
    try:
        analyzer = OwnershipAnalyzer()
        heatmap_data = analyzer.get_ownership_heatmap_data(repo_id)
        
        return jsonify({
            'repository_id': repo_id,
            'heatmap': heatmap_data
        })
        
    except Exception as e:
        logger.error(f"Error getting ownership heatmap: {e}")
        return jsonify({'error': 'Failed to get heatmap data', 'details': str(e)}), 500

@repository_bp.route('/<int:repo_id>/experts', methods=['GET'])
def get_code_experts(repo_id):
    """Get code experts for the repository."""
    try:
        file_extension = request.args.get('extension')
        
        analyzer = OwnershipAnalyzer()
        experts = analyzer.find_code_experts(repo_id, file_extension)
        
        return jsonify({
            'repository_id': repo_id,
            'file_extension': file_extension,
            'experts': experts
        })
        
    except Exception as e:
        logger.error(f"Error getting code experts: {e}")
        return jsonify({'error': 'Failed to get experts', 'details': str(e)}), 500

@repository_bp.route('/<int:repo_id>/features', methods=['GET'])
def get_repository_features(repo_id):
    """Get main features and related commits for the repository."""
    try:
        analyzer = CommitAnalyzer()
        
        # Get commit patterns to identify main feature types
        patterns = analyzer.get_commit_patterns(repo_id)
        
        if 'error' in patterns:
            return jsonify({'error': 'Failed to analyze commit patterns', 'details': patterns['error']}), 500
        
        # Extract main feature categories from commit message types
        feature_categories = []
        message_types = patterns.get('message_types', {})
        
        # Define feature mappings based on commit message patterns
        feature_mappings = {
            'feat': {'name': 'New Features', 'keywords': ['feat', 'feature', 'add', 'implement', 'create', 'new']},
            'fix': {'name': 'Bug Fixes', 'keywords': ['fix', 'bugfix', 'bug', 'patch', 'resolve']},
            'refactor': {'name': 'Code Refactoring', 'keywords': ['refactor', 'restructure', 'reorganize', 'cleanup']},
            'docs': {'name': 'Documentation', 'keywords': ['docs', 'doc', 'documentation', 'readme']},
            'test': {'name': 'Testing', 'keywords': ['test', 'testing', 'spec', 'unit test']},
            'update': {'name': 'Updates & Improvements', 'keywords': ['update', 'upgrade', 'improve', 'enhance']},
            'initial': {'name': 'Initial Setup', 'keywords': ['initial', 'init', 'setup', 'bootstrap']}
        }
        
        # Get top feature categories based on commit frequency
        for category, info in feature_mappings.items():
            commit_count = message_types.get(category, 0)
            if commit_count > 0:
                # Get related commits for this feature category
                related_commits = analyzer.find_feature_introduction_commits(repo_id, info['keywords'])
                
                feature_categories.append({
                    'name': info['name'],
                    'category': category,
                    'commit_count': commit_count,
                    'keywords': info['keywords'],
                    'recent_commits': related_commits[:3]  # Top 3 most relevant commits
                })
        
        # Sort by commit count (most active features first)
        feature_categories.sort(key=lambda x: x['commit_count'], reverse=True)
        
        # Limit to top 5 features
        feature_categories = feature_categories[:5]
        
        return jsonify({
            'repository_id': repo_id,
            'features': feature_categories,
            'total_commits': patterns.get('total_commits', 0),
            'analysis_summary': {
                'most_active_feature': feature_categories[0]['name'] if feature_categories else None,
                'feature_diversity': len(feature_categories)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting repository features: {e}")
        return jsonify({'error': 'Failed to get features', 'details': str(e)}), 500

@repository_bp.route('/list', methods=['GET'])
def list_repositories():
    """List all analyzed repositories."""
    try:
        session = get_session()
        try:
            repos = session.query(Repository).order_by(Repository.last_analyzed.desc()).all()
            
            repository_list = []
            for repo in repos:
                repository_list.append({
                    'id': repo.id,
                    'name': repo.name,
                    'owner': repo.owner,
                    'url': repo.url,
                    'description': repo.description,
                    'language': repo.language,
                    'status': repo.status,
                    'total_commits': repo.total_commits,
                    'total_files': repo.total_files,
                    'created_at': repo.created_at.isoformat() if repo.created_at else None,
                    'last_analyzed': repo.last_analyzed.isoformat() if repo.last_analyzed else None
                })
            
            return jsonify({
                'repositories': repository_list,
                'total': len(repository_list)
            })
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error listing repositories: {e}")
        return jsonify({'error': 'Failed to list repositories', 'details': str(e)}), 500

def _analyze_repository_background(repo_id: int, owner: str, repo_name: str, repo_key: str, force_refresh: bool):
    """Background task for repository analysis."""
    try:
        logger.info(f"Starting background analysis for {repo_key}")
        
        # Update status
        with analysis_lock:
            if repo_key in analysis_status:
                analysis_status[repo_key]['current_step'] = 'Cloning repository'
                analysis_status[repo_key]['progress'] = 10
        
        # Clone repository
        repo_manager = RepositoryManager()
        clone_result = repo_manager.clone_repository(owner, repo_name, force_refresh)
        
        if not clone_result['success']:
            _update_analysis_error(repo_id, repo_key, f"Clone failed: {clone_result.get('details', 'Unknown error')}")
            return
        
        repo_path = clone_result['path']
        
        # Update status
        with analysis_lock:
            if repo_key in analysis_status:
                analysis_status[repo_key]['current_step'] = 'Analyzing commits'
                analysis_status[repo_key]['progress'] = 30
        
        # Analyze commits
        commit_analyzer = CommitAnalyzer()
        commit_result = commit_analyzer.analyze_repository_commits(repo_path, repo_id)
        
        if not commit_result['success']:
            _update_analysis_error(repo_id, repo_key, f"Commit analysis failed: {commit_result.get('details', 'Unknown error')}")
            return
        
        # Update status
        with analysis_lock:
            if repo_key in analysis_status:
                analysis_status[repo_key]['current_step'] = 'Analyzing code ownership'
                analysis_status[repo_key]['progress'] = 70
        
        # Analyze ownership
        ownership_analyzer = OwnershipAnalyzer()
        ownership_result = ownership_analyzer.analyze_code_ownership(repo_id)
        
        if not ownership_result['success']:
            _update_analysis_error(repo_id, repo_key, f"Ownership analysis failed: {ownership_result.get('details', 'Unknown error')}")
            return
        
        # Update final status
        with analysis_lock:
            if repo_key in analysis_status:
                analysis_status[repo_key]['current_step'] = 'Analysis completed'
                analysis_status[repo_key]['progress'] = 100
                analysis_status[repo_key]['status'] = 'completed'
                analysis_status[repo_key]['completed_at'] = datetime.now().isoformat()
        
        # Update database
        session = get_session()
        try:
            repo = session.query(Repository).filter_by(id=repo_id).first()
            if repo:
                repo.status = 'completed'
                repo.last_analyzed = datetime.utcnow()
                repo.error_message = None
                session.commit()
        finally:
            session.close()
        
        logger.info(f"Completed background analysis for {repo_key}")
        
        # Clean up status after some time (keep for 1 hour)
        def cleanup_status():
            import time
            time.sleep(3600)  # 1 hour
            with analysis_lock:
                if repo_key in analysis_status:
                    del analysis_status[repo_key]
        
        cleanup_thread = threading.Thread(target=cleanup_status)
        cleanup_thread.daemon = True
        cleanup_thread.start()
        
    except Exception as e:
        logger.error(f"Error in background analysis for {repo_key}: {e}")
        _update_analysis_error(repo_id, repo_key, str(e))

def _update_analysis_error(repo_id: int, repo_key: str, error_message: str):
    """Update analysis status with error."""
    with analysis_lock:
        if repo_key in analysis_status:
            analysis_status[repo_key]['status'] = 'error'
            analysis_status[repo_key]['error'] = error_message
            analysis_status[repo_key]['completed_at'] = datetime.now().isoformat()
    
    # Update database
    session = get_session()
    try:
        repo = session.query(Repository).filter_by(id=repo_id).first()
        if repo:
            repo.status = 'error'
            repo.error_message = error_message
            session.commit()
    except Exception as e:
        logger.error(f"Error updating database with error status: {e}")
    finally:
        session.close()