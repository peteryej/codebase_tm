"""
Visualization API endpoints
"""

import logging
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta

from analyzers.commit_analyzer import CommitAnalyzer
from analyzers.ownership_analyzer import OwnershipAnalyzer
from database.models import get_session, Repository

logger = logging.getLogger(__name__)

visualization_bp = Blueprint('visualization', __name__)

@visualization_bp.route('/<int:repo_id>/timeline', methods=['GET'])
def get_timeline_data(repo_id):
    """
    Get timeline visualization data.
    
    Query parameters:
    - days: Number of days to include (default: 365)
    - granularity: 'daily', 'weekly', 'monthly' (default: 'daily')
    """
    try:
        days = request.args.get('days', 365, type=int)
        granularity = request.args.get('granularity', 'daily')
        
        # Validate repository
        session = get_session()
        try:
            repo = session.query(Repository).filter_by(id=repo_id).first()
            if not repo:
                return jsonify({'error': 'Repository not found'}), 404
        finally:
            session.close()
        
        analyzer = CommitAnalyzer()
        timeline_data = analyzer.get_commit_timeline(repo_id, days)
        
        # Process data based on granularity
        if granularity == 'weekly':
            timeline_data = _aggregate_timeline_weekly(timeline_data)
        elif granularity == 'monthly':
            timeline_data = _aggregate_timeline_monthly(timeline_data)
        
        return jsonify({
            'repository_id': repo_id,
            'timeline': timeline_data,
            'granularity': granularity,
            'days': days,
            'total_commits': sum(point['commits'] for point in timeline_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting timeline data: {e}")
        return jsonify({'error': 'Failed to get timeline data', 'details': str(e)}), 500

@visualization_bp.route('/<int:repo_id>/heatmap', methods=['GET'])
def get_heatmap_data(repo_id):
    """
    Get ownership heatmap visualization data.
    
    Query parameters:
    - min_percentage: Minimum ownership percentage to include (default: 5)
    - max_files: Maximum number of files to include (default: 100)
    """
    try:
        min_percentage = request.args.get('min_percentage', 5, type=float)
        max_files = request.args.get('max_files', 100, type=int)
        
        # Validate repository
        session = get_session()
        try:
            repo = session.query(Repository).filter_by(id=repo_id).first()
            if not repo:
                return jsonify({'error': 'Repository not found'}), 404
        finally:
            session.close()
        
        analyzer = OwnershipAnalyzer()
        heatmap_data = analyzer.get_ownership_heatmap_data(repo_id)
        
        if 'error' in heatmap_data:
            return jsonify({'error': heatmap_data['error']}), 500
        
        # Filter and limit data
        filtered_data = [
            item for item in heatmap_data['heatmap_data']
            if item['percentage'] >= min_percentage
        ][:max_files]
        
        # Organize data for visualization
        visualization_data = _organize_heatmap_data(filtered_data)
        
        return jsonify({
            'repository_id': repo_id,
            'heatmap': visualization_data,
            'total_files': len(filtered_data),
            'filters': {
                'min_percentage': min_percentage,
                'max_files': max_files
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting heatmap data: {e}")
        return jsonify({'error': 'Failed to get heatmap data', 'details': str(e)}), 500

@visualization_bp.route('/<int:repo_id>/contributors', methods=['GET'])
def get_contributors_chart_data(repo_id):
    """
    Get contributors chart visualization data.
    
    Query parameters:
    - top_n: Number of top contributors to include (default: 10)
    - metric: 'commits', 'lines', 'files' (default: 'commits')
    """
    try:
        top_n = request.args.get('top_n', 10, type=int)
        metric = request.args.get('metric', 'commits')
        
        if metric not in ['commits', 'lines', 'files']:
            return jsonify({'error': 'Invalid metric. Use: commits, lines, or files'}), 400
        
        # Validate repository
        session = get_session()
        try:
            repo = session.query(Repository).filter_by(id=repo_id).first()
            if not repo:
                return jsonify({'error': 'Repository not found'}), 404
        finally:
            session.close()
        
        analyzer = CommitAnalyzer()
        authors = analyzer.get_author_statistics(repo_id)
        
        # Sort by requested metric
        if metric == 'commits':
            authors.sort(key=lambda x: x['commits'], reverse=True)
        elif metric == 'lines':
            authors.sort(key=lambda x: x['insertions'] + x['deletions'], reverse=True)
        elif metric == 'files':
            # For files, we'd need additional data - using commits as fallback
            authors.sort(key=lambda x: x['commits'], reverse=True)
        
        # Prepare chart data
        chart_data = {
            'labels': [author['name'] for author in authors[:top_n]],
            'datasets': []
        }
        
        if metric == 'commits':
            chart_data['datasets'].append({
                'label': 'Commits',
                'data': [author['commits'] for author in authors[:top_n]],
                'backgroundColor': _generate_colors(top_n)
            })
        elif metric == 'lines':
            chart_data['datasets'].extend([
                {
                    'label': 'Lines Added',
                    'data': [author['insertions'] for author in authors[:top_n]],
                    'backgroundColor': _generate_colors(top_n, 'green')
                },
                {
                    'label': 'Lines Removed',
                    'data': [author['deletions'] for author in authors[:top_n]],
                    'backgroundColor': _generate_colors(top_n, 'red')
                }
            ])
        
        return jsonify({
            'repository_id': repo_id,
            'chart_data': chart_data,
            'metric': metric,
            'total_contributors': len(authors)
        })
        
    except Exception as e:
        logger.error(f"Error getting contributors chart data: {e}")
        return jsonify({'error': 'Failed to get contributors data', 'details': str(e)}), 500

@visualization_bp.route('/<int:repo_id>/activity', methods=['GET'])
def get_activity_data(repo_id):
    """
    Get activity pattern visualization data.
    
    Query parameters:
    - type: 'hourly', 'daily', 'monthly' (default: 'daily')
    """
    try:
        activity_type = request.args.get('type', 'daily')
        
        if activity_type not in ['hourly', 'daily', 'monthly']:
            return jsonify({'error': 'Invalid type. Use: hourly, daily, or monthly'}), 400
        
        # Validate repository
        session = get_session()
        try:
            repo = session.query(Repository).filter_by(id=repo_id).first()
            if not repo:
                return jsonify({'error': 'Repository not found'}), 404
        finally:
            session.close()
        
        analyzer = CommitAnalyzer()
        patterns = analyzer.get_commit_patterns(repo_id)
        
        if 'error' in patterns:
            return jsonify({'error': patterns['error']}), 500
        
        # Prepare activity data based on type
        if activity_type == 'hourly':
            activity_data = _prepare_hourly_activity(patterns.get('hourly_distribution', {}))
        elif activity_type == 'daily':
            activity_data = _prepare_daily_activity(patterns.get('daily_distribution', {}))
        elif activity_type == 'monthly':
            # For monthly, we'd need timeline data
            timeline = analyzer.get_commit_timeline(repo_id, 365)
            activity_data = _prepare_monthly_activity(timeline)
        
        return jsonify({
            'repository_id': repo_id,
            'activity_data': activity_data,
            'type': activity_type,
            'total_commits': patterns.get('total_commits', 0)
        })
        
    except Exception as e:
        logger.error(f"Error getting activity data: {e}")
        return jsonify({'error': 'Failed to get activity data', 'details': str(e)}), 500

@visualization_bp.route('/<int:repo_id>/languages', methods=['GET'])
def get_language_distribution(repo_id):
    """Get programming language distribution data."""
    try:
        # Validate repository
        session = get_session()
        try:
            repo = session.query(Repository).filter_by(id=repo_id).first()
            if not repo:
                return jsonify({'error': 'Repository not found'}), 404
        finally:
            session.close()
        
        # Get file extension statistics from ownership data
        analyzer = OwnershipAnalyzer()
        ownership_overview = analyzer.get_repository_ownership_overview(repo_id)
        
        if 'error' in ownership_overview:
            return jsonify({'error': ownership_overview['error']}), 500
        
        # Process extension data
        extensions = ownership_overview.get('extension_breakdown', [])
        
        # Map extensions to languages
        language_map = {
            'py': 'Python',
            'js': 'JavaScript',
            'ts': 'TypeScript',
            'java': 'Java',
            'cpp': 'C++',
            'c': 'C',
            'cs': 'C#',
            'php': 'PHP',
            'rb': 'Ruby',
            'go': 'Go',
            'rs': 'Rust',
            'swift': 'Swift',
            'kt': 'Kotlin',
            'scala': 'Scala',
            'html': 'HTML',
            'css': 'CSS',
            'scss': 'SCSS',
            'less': 'LESS',
            'json': 'JSON',
            'xml': 'XML',
            'yaml': 'YAML',
            'yml': 'YAML',
            'md': 'Markdown',
            'txt': 'Text',
            'sh': 'Shell',
            'sql': 'SQL'
        }
        
        # Prepare chart data
        language_data = []
        for ext_data in extensions:
            ext = ext_data['extension']
            language = language_map.get(ext, ext.upper() if ext != 'no_extension' else 'Other')
            
            language_data.append({
                'language': language,
                'files': ext_data['files'],
                'lines': ext_data['total_lines'],
                'contributors': ext_data['unique_authors']
            })
        
        # Sort by lines of code
        language_data.sort(key=lambda x: x['lines'], reverse=True)
        
        return jsonify({
            'repository_id': repo_id,
            'languages': language_data,
            'total_languages': len(language_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting language distribution: {e}")
        return jsonify({'error': 'Failed to get language data', 'details': str(e)}), 500

@visualization_bp.route('/<int:repo_id>/collaboration', methods=['GET'])
def get_collaboration_data(repo_id):
    """Get collaboration network visualization data."""
    try:
        # Validate repository
        session = get_session()
        try:
            repo = session.query(Repository).filter_by(id=repo_id).first()
            if not repo:
                return jsonify({'error': 'Repository not found'}), 404
        finally:
            session.close()
        
        analyzer = OwnershipAnalyzer()
        ownership_overview = analyzer.get_repository_ownership_overview(repo_id)
        
        if 'error' in ownership_overview:
            return jsonify({'error': ownership_overview['error']}), 500
        
        # Prepare collaboration network data
        contributors = ownership_overview.get('top_contributors', [])
        
        # Create nodes (contributors)
        nodes = []
        for i, contributor in enumerate(contributors[:15]):  # Limit to top 15
            nodes.append({
                'id': contributor['name'],
                'label': contributor['name'],
                'size': min(contributor['lines_contributed'] / 1000, 50),  # Scale node size
                'files': contributor['files_contributed'],
                'lines': contributor['lines_contributed'],
                'percentage': contributor['percentage_of_codebase']
            })
        
        # Create edges (collaboration - simplified)
        # In a full implementation, this would analyze actual file co-authorship
        edges = []
        
        # For now, create connections based on shared file types
        # This is a simplified approach
        for i, contrib1 in enumerate(contributors[:10]):
            for j, contrib2 in enumerate(contributors[i+1:11], i+1):
                # Create edge if both have significant contributions
                if (contrib1['percentage_of_codebase'] > 5 and 
                    contrib2['percentage_of_codebase'] > 5):
                    edges.append({
                        'from': contrib1['name'],
                        'to': contrib2['name'],
                        'weight': min(contrib1['percentage_of_codebase'] + contrib2['percentage_of_codebase'], 100)
                    })
        
        return jsonify({
            'repository_id': repo_id,
            'network': {
                'nodes': nodes,
                'edges': edges
            },
            'collaboration_score': ownership_overview.get('collaboration_score', 0)
        })
        
    except Exception as e:
        logger.error(f"Error getting collaboration data: {e}")
        return jsonify({'error': 'Failed to get collaboration data', 'details': str(e)}), 500

# Helper functions

def _aggregate_timeline_weekly(daily_data):
    """Aggregate daily timeline data into weekly buckets."""
    from collections import defaultdict
    from datetime import datetime, timedelta
    
    weekly_data = defaultdict(int)
    
    for point in daily_data:
        date = datetime.fromisoformat(point['date'])
        # Get Monday of the week
        monday = date - timedelta(days=date.weekday())
        week_key = monday.strftime('%Y-%m-%d')
        weekly_data[week_key] += point['commits']
    
    return [{'date': date, 'commits': commits} for date, commits in sorted(weekly_data.items())]

def _aggregate_timeline_monthly(daily_data):
    """Aggregate daily timeline data into monthly buckets."""
    from collections import defaultdict
    from datetime import datetime
    
    monthly_data = defaultdict(int)
    
    for point in daily_data:
        date = datetime.fromisoformat(point['date'])
        month_key = date.strftime('%Y-%m')
        monthly_data[month_key] += point['commits']
    
    return [{'date': f"{date}-01", 'commits': commits} for date, commits in sorted(monthly_data.items())]

def _organize_heatmap_data(heatmap_data):
    """Organize heatmap data for visualization."""
    # Group by directory
    directories = {}
    
    for item in heatmap_data:
        directory = item['directory'] or 'root'
        if directory not in directories:
            directories[directory] = []
        directories[directory].append(item)
    
    # Prepare visualization structure
    visualization_data = []
    
    for directory, files in directories.items():
        dir_data = {
            'directory': directory,
            'files': files,
            'total_files': len(files),
            'contributors': list(set(f['author'] for f in files))
        }
        visualization_data.append(dir_data)
    
    return visualization_data

def _generate_colors(count, color_scheme='default'):
    """Generate colors for charts."""
    if color_scheme == 'green':
        base_colors = ['#2E7D32', '#388E3C', '#43A047', '#4CAF50', '#66BB6A']
    elif color_scheme == 'red':
        base_colors = ['#C62828', '#D32F2F', '#E53935', '#F44336', '#EF5350']
    else:
        base_colors = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
        ]
    
    colors = []
    for i in range(count):
        colors.append(base_colors[i % len(base_colors)])
    
    return colors

def _prepare_hourly_activity(hourly_distribution):
    """Prepare hourly activity data for visualization."""
    hours = list(range(24))
    data = []
    
    for hour in hours:
        commits = hourly_distribution.get(hour, 0)
        data.append({
            'hour': f"{hour:02d}:00",
            'commits': commits
        })
    
    return data

def _prepare_daily_activity(daily_distribution):
    """Prepare daily activity data for visualization."""
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    data = []
    
    for day in days:
        commits = daily_distribution.get(day, 0)
        data.append({
            'day': day,
            'commits': commits
        })
    
    return data

def _prepare_monthly_activity(timeline_data):
    """Prepare monthly activity data from timeline."""
    from collections import defaultdict
    from datetime import datetime
    
    monthly_data = defaultdict(int)
    
    for point in timeline_data:
        date = datetime.fromisoformat(point['date'])
        month_key = date.strftime('%Y-%m')
        monthly_data[month_key] += point['commits']
    
    data = []
    for month, commits in sorted(monthly_data.items()):
        data.append({
            'month': month,
            'commits': commits
        })
    
    return data