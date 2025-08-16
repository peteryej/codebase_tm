"""
Chat API endpoints for natural language queries
"""

import logging
import hashlib
import os
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta

from database.models import get_session, Repository, QueryCache

logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/query', methods=['POST'])
def process_query():
    """
    Process a natural language query about a repository.
    
    Expected JSON:
    {
        "repository_id": 1,
        "query": "Who are the main contributors to this project?",
        "use_cache": true
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        repository_id = data.get('repository_id')
        query_text = data.get('query', '').strip()
        use_cache = data.get('use_cache', True)
        
        if not repository_id:
            return jsonify({'error': 'Repository ID is required'}), 400
        
        if not query_text:
            return jsonify({'error': 'Query text is required'}), 400
        
        # Validate repository exists
        session = get_session()
        repo = None
        try:
            repo = session.query(Repository).filter_by(id=repository_id).first()
            if not repo:
                return jsonify({'error': 'Repository not found'}), 404
            
            if repo.status != 'completed':
                return jsonify({
                    'error': 'Repository analysis not completed',
                    'status': repo.status
                }), 400
            
            # Create a detached copy of repo data for use after session closes
            repo_data = {
                'id': repo.id,
                'name': repo.name,
                'owner': repo.owner,
                'language': repo.language,
                'description': repo.description,
                'total_commits': repo.total_commits,
                'total_files': repo.total_files,
                'last_analyzed': repo.last_analyzed
            }
        finally:
            session.close()
        
        # Check cache first if enabled
        if use_cache:
            cached_response = _get_cached_response(repository_id, query_text)
            if cached_response:
                return jsonify({
                    'repository_id': repository_id,
                    'query': query_text,
                    'response': cached_response['response'],
                    'cached': True,
                    'timestamp': cached_response['created_at']
                })
        
        # Process the query
        response = _process_natural_language_query(repository_id, query_text, repo_data)
        
        # Cache the response
        if use_cache and response.get('success'):
            _cache_response(repository_id, query_text, response['response'])
        
        if response.get('success'):
            return jsonify({
                'repository_id': repository_id,
                'query': query_text,
                'response': response['response'],
                'cached': False,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'error': response.get('error', 'Query processing failed'),
                'details': response.get('details', '')
            }), 500
            
    except Exception as e:
        logger.error(f"Error processing chat query: {e}")
        return jsonify({'error': 'Query processing failed', 'details': str(e)}), 500

@chat_bp.route('/suggestions', methods=['GET'])
def get_query_suggestions():
    """Get suggested queries for a repository."""
    try:
        repository_id = request.args.get('repository_id', type=int)
        
        if not repository_id:
            return jsonify({'error': 'Repository ID is required'}), 400
        
        # Validate repository exists
        session = get_session()
        repo_data = None
        try:
            repo = session.query(Repository).filter_by(id=repository_id).first()
            if not repo:
                return jsonify({'error': 'Repository not found'}), 404
            
            # Create a detached copy of repo data
            repo_data = {
                'id': repo.id,
                'name': repo.name,
                'owner': repo.owner,
                'language': repo.language,
                'description': repo.description,
                'total_commits': repo.total_commits,
                'total_files': repo.total_files,
                'last_analyzed': repo.last_analyzed
            }
        finally:
            session.close()
        
        # Generate contextual suggestions based on repository
        suggestions = _generate_query_suggestions(repository_id, repo_data)
        
        return jsonify({
            'repository_id': repository_id,
            'suggestions': suggestions
        })
        
    except Exception as e:
        logger.error(f"Error getting query suggestions: {e}")
        return jsonify({'error': 'Failed to get suggestions', 'details': str(e)}), 500

@chat_bp.route('/history', methods=['GET'])
def get_query_history():
    """Get query history for a repository."""
    try:
        repository_id = request.args.get('repository_id', type=int)
        limit = request.args.get('limit', 10, type=int)
        
        if not repository_id:
            return jsonify({'error': 'Repository ID is required'}), 400
        
        session = get_session()
        try:
            # Get recent queries from cache
            recent_queries = session.query(QueryCache).filter_by(
                repo_id=repository_id
            ).order_by(
                QueryCache.created_at.desc()
            ).limit(limit).all()
            
            history = []
            for query in recent_queries:
                history.append({
                    'query': query.query_text,
                    'response': query.response[:200] + '...' if len(query.response) > 200 else query.response,
                    'timestamp': query.created_at.isoformat(),
                    'hit_count': query.hit_count
                })
            
            return jsonify({
                'repository_id': repository_id,
                'history': history,
                'total': len(history)
            })
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error getting query history: {e}")
        return jsonify({'error': 'Failed to get history', 'details': str(e)}), 500

def _get_cached_response(repository_id: int, query_text: str) -> dict:
    """Get cached response for a query."""
    try:
        query_hash = _generate_query_hash(repository_id, query_text)
        
        session = get_session()
        try:
            cached_query = session.query(QueryCache).filter_by(
                query_hash=query_hash
            ).first()
            
            if cached_query and cached_query.expires_at > datetime.utcnow():
                # Update hit count
                cached_query.hit_count += 1
                session.commit()
                
                return {
                    'response': cached_query.response,
                    'created_at': cached_query.created_at.isoformat()
                }
            
            return None
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error getting cached response: {e}")
        return None

def _cache_response(repository_id: int, query_text: str, response: str):
    """Cache a query response."""
    try:
        query_hash = _generate_query_hash(repository_id, query_text)
        cache_duration = int(os.getenv('CACHE_DURATION', 3600))  # 1 hour default
        expires_at = datetime.utcnow() + timedelta(seconds=cache_duration)
        
        session = get_session()
        try:
            # Check if already exists
            existing = session.query(QueryCache).filter_by(query_hash=query_hash).first()
            
            if existing:
                # Update existing
                existing.response = response
                existing.created_at = datetime.utcnow()
                existing.expires_at = expires_at
                existing.hit_count = 1
            else:
                # Create new
                cache_entry = QueryCache(
                    repo_id=repository_id,
                    query_hash=query_hash,
                    query_text=query_text,
                    response=response,
                    expires_at=expires_at
                )
                session.add(cache_entry)
            
            session.commit()
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error caching response: {e}")

def _generate_query_hash(repository_id: int, query_text: str) -> str:
    """Generate a hash for query caching."""
    content = f"{repository_id}:{query_text.lower().strip()}"
    return hashlib.md5(content.encode()).hexdigest()

def _process_natural_language_query(repository_id: int, query_text: str, repo_data: dict) -> dict:
    """
    Process a natural language query and generate response.
    
    This is a simplified implementation that maps common queries to data.
    In a full implementation, this would use LLM integration.
    """
    try:
        query_lower = query_text.lower().strip()
        
        # Import analyzers with error handling
        try:
            from analyzers.commit_analyzer import CommitAnalyzer
            from analyzers.ownership_analyzer import OwnershipAnalyzer
        except ImportError as import_error:
            logger.error(f"Failed to import analyzers: {import_error}")
            return {
                'success': False,
                'error': 'Analysis modules not available',
                'details': str(import_error)
            }
        
        # Pattern matching for common queries
        if any(word in query_lower for word in ['contributor', 'author', 'who wrote', 'main developer']):
            return _handle_contributor_query(repository_id, query_text)
        
        elif any(word in query_lower for word in ['timeline', 'history', 'when', 'commit']):
            return _handle_timeline_query(repository_id, query_text)
        
        elif any(word in query_lower for word in ['ownership', 'owns', 'responsible for']):
            return _handle_ownership_query(repository_id, query_text)
        
        elif any(word in query_lower for word in ['pattern', 'trend', 'activity']):
            return _handle_pattern_query(repository_id, query_text)
        
        elif any(word in query_lower for word in ['file', 'changed', 'modified']):
            return _handle_file_query(repository_id, query_text)
        
        elif any(word in query_lower for word in ['summary', 'overview', 'about']):
            return _handle_summary_query(repository_id, query_text, repo_data)
        
        else:
            # Generic response for unrecognized queries
            return {
                'success': True,
                'response': f"I understand you're asking about: '{query_text}'. "
                          f"I can help you with information about contributors, commit timeline, "
                          f"code ownership, file changes, and project summaries. "
                          f"Try asking something like 'Who are the main contributors?' or "
                          f"'Show me the commit timeline'."
            }
            
    except Exception as e:
        logger.error(f"Error processing natural language query: {e}")
        return {
            'success': False,
            'error': 'Query processing failed',
            'details': str(e)
        }

def _handle_contributor_query(repository_id: int, query_text: str) -> dict:
    """Handle queries about contributors."""
    try:
        from analyzers.commit_analyzer import CommitAnalyzer
        analyzer = CommitAnalyzer()
        authors = analyzer.get_author_statistics(repository_id)
        
        if not authors:
            return {
                'success': True,
                'response': "No contributor data found for this repository."
            }
        
        # Format response
        response = f"**Main Contributors to this repository:**\n\n"
        
        for i, author in enumerate(authors[:5], 1):
            response += f"{i}. **{author['name']}**\n"
            response += f"   - {author['commits']} commits ({author['percentage']}%)\n"
            response += f"   - {author['insertions']} lines added, {author['deletions']} lines removed\n"
            if author['first_commit']:
                response += f"   - Active from {author['first_commit'][:10]} to {author['last_commit'][:10]}\n"
            response += "\n"
        
        if len(authors) > 5:
            response += f"...and {len(authors) - 5} more contributors.\n\n"
        
        response += f"Total contributors: {len(authors)}"
        
        return {
            'success': True,
            'response': response
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': 'Failed to get contributor information',
            'details': str(e)
        }

def _handle_timeline_query(repository_id: int, query_text: str) -> dict:
    """Handle queries about timeline and commit history."""
    try:
        from analyzers.commit_analyzer import CommitAnalyzer
        analyzer = CommitAnalyzer()
        timeline = analyzer.get_commit_timeline(repository_id, 90)  # Last 90 days
        patterns = analyzer.get_commit_patterns(repository_id)
        
        if not timeline:
            return {
                'success': True,
                'response': "No recent commit activity found for this repository."
            }
        
        # Calculate statistics
        total_commits = sum(day['commits'] for day in timeline)
        active_days = len([day for day in timeline if day['commits'] > 0])
        avg_commits_per_active_day = total_commits / active_days if active_days > 0 else 0
        
        # Find most active day
        most_active_day = max(timeline, key=lambda x: x['commits']) if timeline else None
        
        response = f"**Commit Timeline (Last 90 days):**\n\n"
        response += f"- Total commits: {total_commits}\n"
        response += f"- Active days: {active_days}\n"
        response += f"- Average commits per active day: {avg_commits_per_active_day:.1f}\n"
        
        if most_active_day:
            response += f"- Most active day: {most_active_day['date']} ({most_active_day['commits']} commits)\n"
        
        if patterns:
            response += f"\n**Commit Patterns:**\n"
            if patterns.get('most_active_hour') is not None:
                response += f"- Most active hour: {patterns['most_active_hour']}:00\n"
            if patterns.get('most_active_day'):
                response += f"- Most active day of week: {patterns['most_active_day']}\n"
            if patterns.get('message_types'):
                top_type = max(patterns['message_types'].items(), key=lambda x: x[1])
                response += f"- Most common commit type: {top_type[0]} ({top_type[1]} commits)\n"
        
        return {
            'success': True,
            'response': response
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': 'Failed to get timeline information',
            'details': str(e)
        }

def _handle_ownership_query(repository_id: int, query_text: str) -> dict:
    """Handle queries about code ownership."""
    try:
        from analyzers.ownership_analyzer import OwnershipAnalyzer
        analyzer = OwnershipAnalyzer()
        ownership = analyzer.get_repository_ownership_overview(repository_id)
        
        if 'error' in ownership:
            return {
                'success': True,
                'response': "No ownership data found for this repository."
            }
        
        response = f"**Code Ownership Overview:**\n\n"
        response += f"- Total contributors: {ownership['total_authors']}\n"
        response += f"- Total files tracked: {ownership['total_files']}\n"
        response += f"- Files with single owner: {ownership['files_with_single_owner']} ({ownership['ownership_concentration']}%)\n"
        response += f"- Collaboration score: {ownership['collaboration_score']}%\n\n"
        
        response += f"**Top Contributors by Code Ownership:**\n"
        for i, contributor in enumerate(ownership['top_contributors'][:5], 1):
            response += f"{i}. **{contributor['name']}**\n"
            response += f"   - {contributor['files_contributed']} files contributed to\n"
            response += f"   - {contributor['lines_contributed']} lines of code\n"
            response += f"   - {contributor['percentage_of_codebase']}% of codebase\n"
            response += f"   - Primary owner of {contributor['primary_owner_files']} files\n\n"
        
        if ownership.get('extension_breakdown'):
            response += f"**Most Active File Types:**\n"
            for ext in ownership['extension_breakdown'][:3]:
                response += f"- .{ext['extension']}: {ext['files']} files, {ext['unique_authors']} contributors\n"
        
        return {
            'success': True,
            'response': response
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': 'Failed to get ownership information',
            'details': str(e)
        }

def _handle_pattern_query(repository_id: int, query_text: str) -> dict:
    """Handle queries about patterns and trends."""
    try:
        from analyzers.commit_analyzer import CommitAnalyzer
        analyzer = CommitAnalyzer()
        patterns = analyzer.get_commit_patterns(repository_id)
        
        if not patterns or 'error' in patterns:
            return {
                'success': True,
                'response': "No pattern data found for this repository."
            }
        
        response = f"**Development Patterns & Trends:**\n\n"
        response += f"- Total commits analyzed: {patterns['total_commits']}\n"
        response += f"- Average commit message length: {patterns['average_message_length']:.1f} characters\n\n"
        
        if patterns.get('message_types'):
            response += f"**Commit Types:**\n"
            for commit_type, count in list(patterns['message_types'].items())[:5]:
                percentage = (count / patterns['total_commits']) * 100
                response += f"- {commit_type}: {count} commits ({percentage:.1f}%)\n"
            response += "\n"
        
        if patterns.get('hourly_distribution'):
            # Find peak hours
            hourly = patterns['hourly_distribution']
            peak_hour = max(hourly.items(), key=lambda x: x[1])
            response += f"**Activity Patterns:**\n"
            response += f"- Peak activity hour: {peak_hour[0]}:00 ({peak_hour[1]} commits)\n"
            
            if patterns.get('most_active_day'):
                response += f"- Most active day: {patterns['most_active_day']}\n"
        
        return {
            'success': True,
            'response': response
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': 'Failed to get pattern information',
            'details': str(e)
        }

def _handle_file_query(repository_id: int, query_text: str) -> dict:
    """Handle queries about files and changes."""
    try:
        # This would need more sophisticated file analysis
        # For now, provide a basic response
        response = f"**File Analysis:**\n\n"
        response += f"I can provide information about file changes and evolution. "
        response += f"Try asking about specific files like 'Show me the history of README.md' "
        response += f"or 'Which files change the most?'"
        
        return {
            'success': True,
            'response': response
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': 'Failed to get file information',
            'details': str(e)
        }

def _handle_summary_query(repository_id: int, query_text: str, repo_data: dict) -> dict:
    """Handle queries asking for repository summary."""
    try:
        # Get basic repository info
        response = f"**Repository Summary: {repo_data['name']}**\n\n"
        response += f"- **Owner:** {repo_data['owner']}\n"
        response += f"- **Primary Language:** {repo_data['language'] or 'Not specified'}\n"
        if repo_data['description']:
            response += f"- **Description:** {repo_data['description']}\n"
        response += f"- **Total Commits:** {repo_data['total_commits'] or 0}\n"
        response += f"- **Total Files:** {repo_data['total_files'] or 0}\n"
        response += f"- **Last Analyzed:** {repo_data['last_analyzed'].strftime('%Y-%m-%d %H:%M') if repo_data['last_analyzed'] else 'Unknown'}\n\n"
        
        # Get contributor summary with error handling
        try:
            from analyzers.commit_analyzer import CommitAnalyzer
            analyzer = CommitAnalyzer()
            authors = analyzer.get_author_statistics(repository_id)
            
            if authors:
                response += f"**Contributors:** {len(authors)} total\n"
                if len(authors) > 0:
                    top_contributor = authors[0]
                    response += f"- Top contributor: {top_contributor['name']} ({top_contributor['percentage']}% of commits)\n"
        except Exception as author_error:
            logger.warning(f"Could not get author statistics: {author_error}")
            response += f"**Contributors:** Information not available\n"
        
        response += f"\nI can provide more detailed information about contributors, commit timeline, "
        response += f"code ownership, and development patterns. Just ask!"
        
        return {
            'success': True,
            'response': response
        }
        
    except Exception as e:
        logger.error(f"Error in _handle_summary_query: {e}")
        return {
            'success': False,
            'error': 'Failed to get repository summary',
            'details': str(e)
        }

def _generate_query_suggestions(repository_id: int, repo_data: dict) -> list:
    """Generate contextual query suggestions."""
    suggestions = [
        "Who are the main contributors to this project?",
        "Show me the commit timeline for the last 3 months",
        "What are the development patterns in this repository?",
        "Which files have changed the most?",
        "Give me an overview of code ownership",
        "What programming languages are used in this project?",
        "When was this project most active?",
        "Who are the experts for different file types?",
        "Show me collaboration patterns between developers",
        "What are the most common types of commits?"
    ]
    
    # Add repository-specific suggestions based on language
    if repo_data['language']:
        suggestions.append(f"Show me {repo_data['language']} experts in this project")
        suggestions.append(f"How has the {repo_data['language']} code evolved over time?")
    
    return suggestions