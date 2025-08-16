"""
Chat API endpoints for natural language queries
"""

import logging
import hashlib
import os
import json
from typing import List, Dict
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from openai import OpenAI

from database.models import get_session, Repository, QueryCache

logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat', __name__)

# Initialize OpenAI client
def get_openai_client():
    """Get OpenAI client instance."""
    logger.debug("Initializing OpenAI client")
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.error("OpenAI API key not found in environment variables")
        return None
    
    logger.debug("OpenAI client initialized successfully")
    return OpenAI(api_key=api_key)

def _classify_query_with_openai(query_text: str, repo_data: dict) -> dict:
    """
    Use OpenAI to classify the query and determine the best approach.
    
    Returns:
    {
        'approach': 'structured_data' | 'rag_codebase',
        'query_type': str,
        'confidence': float,
        'reasoning': str
    }
    """
    logger.info(f"Starting OpenAI query classification for: '{query_text[:100]}...'")
    logger.debug(f"Repository data: {repo_data}")
    
    try:
        client = get_openai_client()
        if not client:
            logger.warning("OpenAI client not available, falling back to structured data approach")
            return {
                'approach': 'structured_data',
                'query_type': 'fallback',
                'confidence': 0.5,
                'reasoning': 'OpenAI client not available, falling back to structured data'
            }
        
        # Define the available structured query types
        structured_types = [
            "contributor_analysis",
            "timeline_history",
            "code_ownership",
            "development_patterns",
            "file_changes",
            "feature_introduction",
            "feature_evolution",
            "repository_summary"
        ]
        
        system_prompt = f"""You are a query classifier for a code repository analysis system.

Repository Info:
- Name: {repo_data.get('name', 'Unknown')}
- Language: {repo_data.get('language', 'Unknown')}
- Total Commits: {repo_data.get('total_commits', 0)}
- Total Files: {repo_data.get('total_files', 0)}

Available structured data query types:
{json.dumps(structured_types, indent=2)}

Your task is to classify the user query and determine the best approach:

1. "structured_data" - Use this when the query can be answered using repository metadata, commit history, contributor statistics, or ownership data. These queries typically ask about:
   - Who contributed to the project
   - Commit timelines and patterns
   - Code ownership and responsibility
   - Development activity and trends
   - When features were introduced or implemented
   - How features evolved over time or why they were added
   - Repository statistics and summaries

2. "rag_codebase" - Use this when the query requires examining actual source code content, specific implementations, or detailed code analysis. These queries typically ask about:
   - How specific features are implemented
   - Code structure and architecture details
   - Specific functions, classes, or modules
   - Code quality or technical debt
   - Specific algorithms or logic

Respond with a JSON object containing:
- approach: "structured_data" or "rag_codebase"
- query_type: one of the structured types if approach is "structured_data", or "code_analysis" if "rag_codebase"
- confidence: float between 0.0 and 1.0
- reasoning: brief explanation of your decision"""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Classify this query: {query_text}"}
            ],
            temperature=0.1,
            max_tokens=300
        )
        
        result_text = response.choices[0].message.content.strip()
        logger.debug(f"OpenAI raw response: {result_text}")
        
        # Parse JSON response
        try:
            result = json.loads(result_text)
            logger.debug(f"Parsed OpenAI response: {result}")
            
            # Validate the response structure
            if not all(key in result for key in ['approach', 'query_type', 'confidence', 'reasoning']):
                raise ValueError("Missing required keys in OpenAI response")
            
            # Ensure confidence is between 0 and 1
            result['confidence'] = max(0.0, min(1.0, float(result['confidence'])))
            
            logger.info(f"Query classified successfully: {result['approach']} - {result['query_type']} (confidence: {result['confidence']:.2f})")
            return result
            
        except (json.JSONDecodeError, ValueError) as parse_error:
            logger.warning(f"Failed to parse OpenAI response: {parse_error}. Raw response: {result_text}")
            logger.info("Falling back to keyword-based classification")
            # Fallback to simple keyword matching
            return _fallback_query_classification(query_text)
            
    except Exception as e:
        logger.error(f"Error in OpenAI query classification: {e}", exc_info=True)
        logger.info("Falling back to keyword-based classification due to error")
        return _fallback_query_classification(query_text)

def _fallback_query_classification(query_text: str) -> dict:
    """Fallback classification using simple keyword matching."""
    logger.info(f"Using fallback keyword classification for: '{query_text[:100]}...'")
    query_lower = query_text.lower().strip()
    
    if any(word in query_lower for word in ['contributor', 'author', 'who wrote', 'main developer']):
        logger.debug("Fallback: Detected contributor-related keywords")
        return {
            'approach': 'structured_data',
            'query_type': 'contributor_analysis',
            'confidence': 0.7,
            'reasoning': 'Fallback: Detected contributor-related keywords'
        }
    elif any(word in query_lower for word in ['when', 'introduced', 'added', 'implemented', 'feature']):
        logger.debug("Fallback: Detected feature introduction keywords")
        return {
            'approach': 'structured_data',
            'query_type': 'feature_introduction',
            'confidence': 0.8,
            'reasoning': 'Fallback: Detected feature introduction keywords'
        }
    elif any(word in query_lower for word in ['why', 'evolved', 'evolution', 'changed', 'developed', 'how', 'motivation', 'reason']):
        logger.debug("Fallback: Detected feature evolution keywords")
        return {
            'approach': 'structured_data',
            'query_type': 'feature_evolution',
            'confidence': 0.8,
            'reasoning': 'Fallback: Detected feature evolution keywords'
        }
    elif any(word in query_lower for word in ['timeline', 'history', 'commit']):
        logger.debug("Fallback: Detected timeline-related keywords")
        return {
            'approach': 'structured_data',
            'query_type': 'timeline_history',
            'confidence': 0.7,
            'reasoning': 'Fallback: Detected timeline-related keywords'
        }
    elif any(word in query_lower for word in ['ownership', 'owns', 'responsible for']):
        logger.debug("Fallback: Detected ownership-related keywords")
        return {
            'approach': 'structured_data',
            'query_type': 'code_ownership',
            'confidence': 0.7,
            'reasoning': 'Fallback: Detected ownership-related keywords'
        }
    elif any(word in query_lower for word in ['implement', 'function', 'class', 'code', 'algorithm']):
        logger.debug("Fallback: Detected code implementation keywords")
        return {
            'approach': 'structured_data',
            'query_type': 'code_analysis',
            'confidence': 0.6,
            'reasoning': 'Fallback: Detected code implementation keywords'
        }
    else:
        logger.debug("Fallback: Default to repository summary")
        return {
            'approach': 'structured_data',
            'query_type': 'repository_summary',
            'confidence': 0.5,
            'reasoning': 'Fallback: Default to repository summary'
        }

def _handle_rag_codebase_query(repository_id: int, query_text: str, repo_data: dict) -> dict:
    """
    Handle queries that require RAG on codebase files using OpenAI.
    """
    logger.info(f"Starting RAG codebase query for repository {repository_id}: '{query_text[:100]}...'")
    logger.debug(f"Repository data: {repo_data}")
    
    try:
        client = get_openai_client()
        if not client:
            logger.error("OpenAI client not available for RAG codebase analysis")
            return {
                'success': False,
                'error': 'OpenAI client not available for codebase analysis',
                'details': 'Please check OpenAI API configuration'
            }
        
        # Get repository path
        repos_path = os.getenv('REPOS_PATH', '../data/repos')
        repo_name = f"{repo_data['owner']}_{repo_data['name']}"
        repo_path = os.path.join(repos_path, repo_name)
        logger.debug(f"Repository path: {repo_path}")
        
        if not os.path.exists(repo_path):
            logger.warning(f"Repository path does not exist: {repo_path}")
            return {
                'success': False,
                'error': 'Repository files not found',
                'details': f'Repository path {repo_path} does not exist'
            }
        
        # Get relevant files based on query
        logger.info("Finding relevant files for RAG analysis")
        relevant_files = _find_relevant_files(repo_path, query_text)
        logger.debug(f"Found {len(relevant_files) if relevant_files else 0} relevant files")
        
        if not relevant_files:
            logger.info("No relevant files found for RAG analysis")
            return {
                'success': True,
                'response': f"I couldn't find specific files related to your query: '{query_text}'. "
                          f"The repository contains {repo_data.get('total_files', 0)} files. "
                          f"Try asking about specific file types, functions, or components."
            }
        
        # Read file contents (limit to prevent token overflow)
        file_contents = []
        total_chars = 0
        max_chars = 8000  # Limit to prevent token overflow
        
        for file_path in relevant_files[:5]:  # Limit to 5 files
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if total_chars + len(content) > max_chars:
                        content = content[:max_chars - total_chars]
                    
                    relative_path = os.path.relpath(file_path, repo_path)
                    file_contents.append({
                        'path': relative_path,
                        'content': content
                    })
                    total_chars += len(content)
                    
                    if total_chars >= max_chars:
                        break
                        
            except Exception as file_error:
                logger.warning(f"Could not read file {file_path}: {file_error}")
                continue
        
        if not file_contents:
            return {
                'success': True,
                'response': f"I found relevant files but couldn't read their contents. "
                          f"This might be due to binary files or encoding issues."
            }
        
        # Create context for OpenAI
        context = f"Repository: {repo_data['name']} by {repo_data['owner']}\n"
        context += f"Language: {repo_data.get('language', 'Unknown')}\n"
        context += f"Total Files: {repo_data.get('total_files', 0)}\n\n"
        
        context += "Relevant Files:\n"
        for file_info in file_contents:
            context += f"\n--- {file_info['path']} ---\n"
            context += file_info['content']
            context += "\n"
        
        # Query OpenAI with the context
        system_prompt = """You are a code analysis assistant. You have access to source code files from a repository.
        Analyze the provided code and answer the user's question accurately and helpfully.
        
        Guidelines:
        - Focus on the specific question asked
        - Provide code examples when relevant
        - Explain complex concepts clearly
        - If you can't find the answer in the provided files, say so
        - Be concise but thorough"""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query_text}"}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Add metadata about files analyzed
        files_analyzed = [f['path'] for f in file_contents]
        final_response = ai_response + f"\n\n*Analysis based on {len(files_analyzed)} files: {', '.join(files_analyzed)}*"
        
        return {
            'success': True,
            'response': final_response
        }
        
    except Exception as e:
        logger.error(f"Error in RAG codebase query: {e}")
        return {
            'success': False,
            'error': 'Failed to analyze codebase',
            'details': str(e)
        }

def _find_relevant_files(repo_path: str, query_text: str) -> list:
    """
    Find files relevant to the query using simple heuristics.
    In a production system, this could use more sophisticated methods like embeddings.
    """
    relevant_files = []
    query_lower = query_text.lower()
    
    # Common source code extensions
    source_extensions = {'.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.cs', '.rb', '.go', '.rs', '.php'}
    
    try:
        for root, dirs, files in os.walk(repo_path):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'build', 'dist'}]
            
            for file in files:
                file_path = os.path.join(root, file)
                file_lower = file.lower()
                
                # Check if file extension is relevant
                _, ext = os.path.splitext(file)
                if ext.lower() not in source_extensions:
                    continue
                
                # Simple relevance scoring
                relevance_score = 0
                
                # Check filename relevance
                for word in query_lower.split():
                    if len(word) > 2 and word in file_lower:
                        relevance_score += 2
                
                # Check for common patterns
                if any(pattern in query_lower for pattern in ['function', 'class', 'method']):
                    if ext.lower() in {'.py', '.js', '.ts', '.java', '.cpp', '.c'}:
                        relevance_score += 1
                
                # Add files with some relevance
                if relevance_score > 0 or len(relevant_files) < 3:  # Always include at least a few files
                    relevant_files.append((file_path, relevance_score))
        
        # Sort by relevance score and return paths
        relevant_files.sort(key=lambda x: x[1], reverse=True)
        return [path for path, score in relevant_files[:10]]  # Return top 10 relevant files
        
    except Exception as e:
        logger.error(f"Error finding relevant files: {e}")
        return []

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
    logger.info(f"Received chat query request: repository_id={request.json.get('repository_id') if request.json else 'None'}")
    
    try:
        data = request.get_json()
        if not data:
            logger.warning("Request body is missing or empty")
            return jsonify({'error': 'Request body is required'}), 400
        
        repository_id = data.get('repository_id')
        query_text = data.get('query', '').strip()
        use_cache = data.get('use_cache', True)
        
        logger.info(f"Processing query: repository_id={repository_id}, query='{query_text[:100]}...', use_cache={use_cache}")
        
        if not repository_id:
            logger.warning("Repository ID is missing from request")
            return jsonify({'error': 'Repository ID is required'}), 400
        
        if not query_text:
            logger.warning("Query text is missing or empty")
            return jsonify({'error': 'Query text is required'}), 400
        
        # Validate repository exists
        logger.info(f"Validating repository {repository_id}")
        session = get_session()
        repo = None
        try:
            repo = session.query(Repository).filter_by(id=repository_id).first()
            if not repo:
                logger.warning(f"Repository {repository_id} not found in database")
                return jsonify({'error': 'Repository not found'}), 404
            
            if repo.status != 'completed':
                logger.warning(f"Repository {repository_id} analysis not completed, status: {repo.status}")
                return jsonify({
                    'error': 'Repository analysis not completed',
                    'status': repo.status
                }), 400
            
            logger.info(f"Repository {repository_id} validated successfully: {repo.name}/{repo.owner}")
            
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
            logger.debug(f"Repository data prepared: {repo_data}")
        finally:
            session.close()
        
        # Check cache first if enabled
        if use_cache:
            logger.info("Checking cache for existing response")
            cached_response = _get_cached_response(repository_id, query_text)
            if cached_response:
                logger.info(f"Cache hit for query: {query_text[:50]}...")
                return jsonify({
                    'repository_id': repository_id,
                    'query': query_text,
                    'response': cached_response['response'],
                    'cached': True,
                    'timestamp': cached_response['created_at']
                })
            else:
                logger.info("Cache miss, processing query")
        else:
            logger.info("Cache disabled, processing query directly")
        
        # Process the query
        logger.info("Starting natural language query processing")
        response = _process_natural_language_query(repository_id, query_text, repo_data)
        logger.debug(f"Query processing result: success={response.get('success')}, error={response.get('error', 'None')}")
        
        # Cache the response
        if use_cache and response.get('success'):
            logger.info("Caching successful response")
            _cache_response(repository_id, query_text, response['response'])
        
        if response.get('success'):
            logger.info("Query processed successfully")
            return jsonify({
                'repository_id': repository_id,
                'query': query_text,
                'response': response['response'],
                'cached': False,
                'timestamp': datetime.now().isoformat()
            })
        else:
            logger.error(f"Query processing failed: {response.get('error', 'Unknown error')}")
            return jsonify({
                'error': response.get('error', 'Query processing failed'),
                'details': response.get('details', '')
            }), 500
            
    except Exception as e:
        logger.error(f"Unexpected error processing chat query: {e}", exc_info=True)
        return jsonify({'error': 'Query processing failed', 'details': str(e)}), 500

@chat_bp.route('/suggestions', methods=['GET'])
def get_query_suggestions():
    """Get suggested queries for a repository."""
    logger.info(f"Received suggestions request for repository_id={request.args.get('repository_id')}")
    
    try:
        repository_id = request.args.get('repository_id', type=int)
        
        if not repository_id:
            logger.warning("Repository ID is missing from suggestions request")
            return jsonify({'error': 'Repository ID is required'}), 400
        
        logger.info(f"Generating suggestions for repository {repository_id}")
        
        # Validate repository exists
        session = get_session()
        repo_data = None
        try:
            repo = session.query(Repository).filter_by(id=repository_id).first()
            if not repo:
                logger.warning(f"Repository {repository_id} not found for suggestions")
                return jsonify({'error': 'Repository not found'}), 404
            
            logger.info(f"Repository {repository_id} found: {repo.name}/{repo.owner}")
            
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
        logger.info("Generating contextual query suggestions")
        suggestions = _generate_query_suggestions(repository_id, repo_data)
        logger.debug(f"Generated {len(suggestions)} suggestions")
        
        return jsonify({
            'repository_id': repository_id,
            'suggestions': suggestions
        })
        
    except Exception as e:
        logger.error(f"Error getting query suggestions: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get suggestions', 'details': str(e)}), 500

@chat_bp.route('/history', methods=['GET'])
def get_query_history():
    """Get query history for a repository."""
    logger.info(f"Received history request for repository_id={request.args.get('repository_id')}, limit={request.args.get('limit', 10)}")
    
    try:
        repository_id = request.args.get('repository_id', type=int)
        limit = request.args.get('limit', 10, type=int)
        
        if not repository_id:
            logger.warning("Repository ID is missing from history request")
            return jsonify({'error': 'Repository ID is required'}), 400
        
        logger.info(f"Retrieving query history for repository {repository_id}, limit: {limit}")
        
        session = get_session()
        try:
            # Get recent queries from cache
            recent_queries = session.query(QueryCache).filter_by(
                repo_id=repository_id
            ).order_by(
                QueryCache.created_at.desc()
            ).limit(limit).all()
            
            logger.debug(f"Found {len(recent_queries)} cached queries for repository {repository_id}")
            
            history = []
            for query in recent_queries:
                history.append({
                    'query': query.query_text,
                    'response': query.response[:200] + '...' if len(query.response) > 200 else query.response,
                    'timestamp': query.created_at.isoformat(),
                    'hit_count': query.hit_count
                })
            
            logger.info(f"Returning {len(history)} history items for repository {repository_id}")
            return jsonify({
                'repository_id': repository_id,
                'history': history,
                'total': len(history)
            })
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error getting query history: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get history', 'details': str(e)}), 500

def _get_cached_response(repository_id: int, query_text: str) -> dict:
    """Get cached response for a query."""
    logger.debug(f"Checking cache for repository {repository_id}, query: '{query_text[:50]}...'")
    
    try:
        query_hash = _generate_query_hash(repository_id, query_text)
        logger.debug(f"Generated query hash: {query_hash[:8]}...")
        
        session = get_session()
        try:
            cached_query = session.query(QueryCache).filter_by(
                query_hash=query_hash
            ).first()
            
            if cached_query and cached_query.expires_at > datetime.utcnow():
                logger.debug(f"Cache hit found, hit_count: {cached_query.hit_count}")
                # Update hit count
                cached_query.hit_count += 1
                session.commit()
                
                return {
                    'response': cached_query.response,
                    'created_at': cached_query.created_at.isoformat()
                }
            else:
                if cached_query:
                    logger.debug(f"Cache entry expired at {cached_query.expires_at}")
                else:
                    logger.debug("No cache entry found")
            
            return None
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error getting cached response: {e}", exc_info=True)
        return None

def _cache_response(repository_id: int, query_text: str, response: str):
    """Cache a query response."""
    logger.debug(f"Caching response for repository {repository_id}, query: '{query_text[:50]}...'")
    
    try:
        query_hash = _generate_query_hash(repository_id, query_text)
        cache_duration = int(os.getenv('CACHE_DURATION', 3600))  # 1 hour default
        expires_at = datetime.utcnow() + timedelta(seconds=cache_duration)
        
        logger.debug(f"Cache settings: duration={cache_duration}s, expires_at={expires_at}")
        
        session = get_session()
        try:
            # Check if already exists
            existing = session.query(QueryCache).filter_by(query_hash=query_hash).first()
            
            if existing:
                logger.debug("Updating existing cache entry")
                # Update existing
                existing.response = response
                existing.created_at = datetime.utcnow()
                existing.expires_at = expires_at
                existing.hit_count = 1
            else:
                logger.debug("Creating new cache entry")
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
            logger.debug("Response cached successfully")
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error caching response: {e}", exc_info=True)

def _generate_query_hash(repository_id: int, query_text: str) -> str:
    """Generate a hash for query caching."""
    content = f"{repository_id}:{query_text.lower().strip()}"
    query_hash = hashlib.md5(content.encode()).hexdigest()
    logger.debug(f"Generated query hash: {query_hash[:8]}... for content: {content[:50]}...")
    return query_hash

def _process_natural_language_query(repository_id: int, query_text: str, repo_data: dict) -> dict:
    """
    Process a natural language query using OpenAI to determine the best approach.
    Routes to either structured data analysis or RAG-based codebase analysis.
    """
    logger.info(f"Processing natural language query: repository_id={repository_id}, query='{query_text[:100]}...'")
    
    try:
        # Use OpenAI to classify the query
        logger.info("Classifying query using OpenAI")
        classification = _classify_query_with_openai(query_text, repo_data)
        
        logger.info(f"Query classification result: {classification}")
        
        # Route based on classification
        if classification['approach'] == 'rag_codebase':
            logger.info("Routing to RAG codebase analysis")
            return _handle_rag_codebase_query(repository_id, query_text, repo_data)
        
        elif classification['approach'] == 'structured_data':
            logger.info("Routing to structured data analysis")
            # Import analyzers with error handling
            try:
                from analyzers.commit_analyzer import CommitAnalyzer
                from analyzers.ownership_analyzer import OwnershipAnalyzer
                logger.debug("Analyzers imported successfully")
            except ImportError as import_error:
                logger.error(f"Failed to import analyzers: {import_error}", exc_info=True)
                return {
                    'success': False,
                    'error': 'Analysis modules not available',
                    'details': str(import_error)
                }
            
            # Route to appropriate structured data handler
            query_type = classification.get('query_type', 'repository_summary')
            
            if query_type == 'contributor_analysis':
                return _handle_contributor_query(repository_id, query_text)
            
            elif query_type == 'timeline_history':
                return _handle_timeline_query(repository_id, query_text)
            
            elif query_type == 'feature_introduction':
                return _handle_feature_introduction_query(repository_id, query_text)
            
            elif query_type == 'feature_evolution':
                return _handle_feature_evolution_query(repository_id, query_text)
            
            elif query_type == 'code_ownership':
                return _handle_ownership_query(repository_id, query_text)
            
            elif query_type == 'development_patterns':
                return _handle_pattern_query(repository_id, query_text)
            
            elif query_type == 'file_changes':
                return _handle_file_query(repository_id, query_text)
            
            elif query_type == 'repository_summary':
                return _handle_summary_query(repository_id, query_text, repo_data)
            
            else:
                # Fallback for unknown structured query types
                return _handle_summary_query(repository_id, query_text, repo_data)
        
        else:
            # Fallback if classification fails
            logger.warning(f"Unknown approach in classification: {classification}")
            return {
                'success': True,
                'response': f"I understand you're asking about: '{query_text}'. "
                          f"I can help you with information about contributors, commit timeline, "
                          f"code ownership, file changes, project summaries, and code implementation details. "
                          f"Try asking something like 'Who are the main contributors?' or "
                          f"'How is the authentication implemented?'"
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

def _handle_feature_introduction_query(repository_id: int, query_text: str) -> dict:
    """Handle queries about when features were introduced."""
    try:
        from analyzers.commit_analyzer import CommitAnalyzer
        analyzer = CommitAnalyzer()
        
        # Extract potential feature keywords from the query
        feature_keywords = _extract_feature_keywords(query_text)
        
        if not feature_keywords:
            return {
                'success': True,
                'response': "I'd be happy to help you find when a feature was introduced! "
                          "Please specify the feature name or functionality you're asking about. "
                          "For example: 'When was authentication added?' or 'When was the login feature implemented?'"
            }
        
        # Search for commits related to the feature
        feature_commits = analyzer.find_feature_introduction_commits(repository_id, feature_keywords)
        
        if not feature_commits:
            return {
                'success': True,
                'response': f"I couldn't find specific commits related to '{' '.join(feature_keywords)}'. "
                          f"This could mean the feature was implemented before the repository was analyzed, "
                          f"or it might be referenced by different terms in commit messages. "
                          f"Try asking about related terms or check the commit history manually."
            }
        
        # Generate commit summary using OpenAI if available
        commit_summary = _generate_commit_summary(feature_commits, f"introduction of {' '.join(feature_keywords)}")
        
        # Format the response
        response = f"**Feature Introduction Analysis for '{' '.join(feature_keywords)}':**\n\n"
        
        if commit_summary:
            response += f"**Summary of Changes:**\n{commit_summary}\n\n"
        
        if len(feature_commits) == 1:
            commit = feature_commits[0]
            response += f"**Initial Introduction:**\n"
            response += f"- **Date:** {commit['timestamp'][:10]}\n"
            response += f"- **Author:** {commit['author']}\n"
            response += f"- **Commit:** {commit['hash'][:8]}\n"
            response += f"- **Message:** {commit['message']}\n"
            response += f"- **Files Changed:** {commit['files_changed']}\n"
            if commit.get('insertions'):
                response += f"- **Lines Added:** {commit['insertions']}\n"
        else:
            # Multiple commits found - show evolution
            response += f"**Found {len(feature_commits)} related commits:**\n\n"
            
            # Show the earliest (likely introduction)
            earliest = min(feature_commits, key=lambda x: x['timestamp'])
            response += f"**Initial Introduction ({earliest['timestamp'][:10]}):**\n"
            response += f"- **Author:** {earliest['author']}\n"
            response += f"- **Commit:** {earliest['hash'][:8]}\n"
            response += f"- **Message:** {earliest['message']}\n\n"
            
            # Show recent developments
            if len(feature_commits) > 1:
                recent = max(feature_commits, key=lambda x: x['timestamp'])
                if recent['hash'] != earliest['hash']:
                    response += f"**Most Recent Update ({recent['timestamp'][:10]}):**\n"
                    response += f"- **Author:** {recent['author']}\n"
                    response += f"- **Commit:** {recent['hash'][:8]}\n"
                    response += f"- **Message:** {recent['message']}\n\n"
            
            # Summary
            authors = set(commit['author'] for commit in feature_commits)
            total_changes = sum(commit.get('files_changed', 0) for commit in feature_commits)
            response += f"**Summary:**\n"
            response += f"- **Total related commits:** {len(feature_commits)}\n"
            response += f"- **Contributors:** {', '.join(authors)}\n"
            response += f"- **Total files affected:** {total_changes}\n"
            
            date_range = f"{earliest['timestamp'][:10]} to {recent['timestamp'][:10]}"
            response += f"- **Development period:** {date_range}\n"
        
        return {
            'success': True,
            'response': response
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': 'Failed to analyze feature introduction',
            'details': str(e)
        }

def _handle_feature_evolution_query(repository_id: int, query_text: str) -> dict:
    """Handle queries about how features evolved or why they were introduced."""
    try:
        from analyzers.commit_analyzer import CommitAnalyzer
        analyzer = CommitAnalyzer()
        
        # Extract potential feature keywords from the query
        feature_keywords = _extract_feature_keywords(query_text)
        
        if not feature_keywords:
            return {
                'success': True,
                'response': "I'd be happy to help you understand how a feature evolved! "
                          "Please specify the feature name or functionality you're asking about. "
                          "For example: 'How did the authentication system evolve?' or 'Why was the login feature changed?'"
            }
        
        # Search for commits related to the feature
        feature_commits = analyzer.find_feature_introduction_commits(repository_id, feature_keywords)
        
        if not feature_commits:
            return {
                'success': True,
                'response': f"I couldn't find specific commits related to '{' '.join(feature_keywords)}'. "
                          f"This could mean the feature was implemented before the repository was analyzed, "
                          f"or it might be referenced by different terms in commit messages. "
                          f"Try asking about related terms or check the commit history manually."
            }
        
        # Sort commits chronologically to show evolution
        feature_commits.sort(key=lambda x: x['timestamp'])
        
        # Generate evolution summary using OpenAI if available
        evolution_summary = _generate_evolution_summary(feature_commits, f"evolution of {' '.join(feature_keywords)}")
        
        # Format the response
        response = f"**Feature Evolution Analysis for '{' '.join(feature_keywords)}':**\n\n"
        
        if evolution_summary:
            response += f"**Evolution Summary:**\n{evolution_summary}\n\n"
        
        # Show chronological development
        response += f"**Chronological Development ({len(feature_commits)} commits):**\n\n"
        
        # Group commits by time periods for better readability
        if len(feature_commits) <= 5:
            # Show all commits if there are few
            for i, commit in enumerate(feature_commits, 1):
                response += f"**{i}. {commit['timestamp'][:10]} - {commit['author']}**\n"
                response += f"   - Commit: {commit['hash'][:8]}\n"
                response += f"   - Changes: {commit['files_changed']} files"
                if commit.get('insertions') or commit.get('deletions'):
                    response += f" (+{commit.get('insertions', 0)}/-{commit.get('deletions', 0)} lines)"
                response += f"\n   - Message: {commit['message'][:100]}{'...' if len(commit['message']) > 100 else ''}\n\n"
        else:
            # Show key milestones for many commits
            earliest = feature_commits[0]
            latest = feature_commits[-1]
            middle_idx = len(feature_commits) // 2
            middle = feature_commits[middle_idx]
            
            response += f"**Initial Implementation ({earliest['timestamp'][:10]}):**\n"
            response += f"- Author: {earliest['author']}\n"
            response += f"- Commit: {earliest['hash'][:8]}\n"
            response += f"- Message: {earliest['message']}\n\n"
            
            if len(feature_commits) > 2:
                response += f"**Mid-Development ({middle['timestamp'][:10]}):**\n"
                response += f"- Author: {middle['author']}\n"
                response += f"- Commit: {middle['hash'][:8]}\n"
                response += f"- Message: {middle['message']}\n\n"
            
            response += f"**Latest Changes ({latest['timestamp'][:10]}):**\n"
            response += f"- Author: {latest['author']}\n"
            response += f"- Commit: {latest['hash'][:8]}\n"
            response += f"- Message: {latest['message']}\n\n"
        
        # Analysis summary
        authors = set(commit['author'] for commit in feature_commits)
        total_insertions = sum(commit.get('insertions', 0) for commit in feature_commits)
        total_deletions = sum(commit.get('deletions', 0) for commit in feature_commits)
        total_files = sum(commit.get('files_changed', 0) for commit in feature_commits)
        
        time_span = (
            datetime.fromisoformat(feature_commits[-1]['timestamp'].replace('Z', '+00:00')) -
            datetime.fromisoformat(feature_commits[0]['timestamp'].replace('Z', '+00:00'))
        ).days
        
        response += f"**Evolution Statistics:**\n"
        response += f"- **Development span:** {time_span} days\n"
        response += f"- **Total commits:** {len(feature_commits)}\n"
        response += f"- **Contributors:** {len(authors)} ({', '.join(sorted(authors))})\n"
        response += f"- **Code changes:** +{total_insertions}/-{total_deletions} lines across {total_files} file changes\n"
        response += f"- **Average commits per contributor:** {len(feature_commits) / len(authors):.1f}\n"
        
        return {
            'success': True,
            'response': response
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': 'Failed to analyze feature evolution',
            'details': str(e)
        }

def _extract_feature_keywords(query_text: str) -> list:
    """Extract potential feature keywords from the query."""
    import re
    
    # Convert to lowercase for analysis
    query_lower = query_text.lower()
    
    # Remove common question words and focus on the feature terms
    stop_words = {'when', 'was', 'is', 'the', 'a', 'an', 'introduced', 'added', 'implemented',
                  'feature', 'functionality', 'how', 'what', 'where', 'why', 'did', 'does'}
    
    # Extract words that might be feature names
    words = re.findall(r'\b\w+\b', query_lower)
    keywords = [word for word in words if word not in stop_words and len(word) > 2]
    
    # Look for quoted terms (explicit feature names)
    quoted_terms = re.findall(r'"([^"]+)"', query_text)
    quoted_terms.extend(re.findall(r"'([^']+)'", query_text))
    
    # Combine keywords and quoted terms
    all_keywords = keywords + [term.lower() for term in quoted_terms]
    
    # Remove duplicates while preserving order
    seen = set()
    unique_keywords = []
    for keyword in all_keywords:
        if keyword not in seen:
            seen.add(keyword)
            unique_keywords.append(keyword)
    
    return unique_keywords[:5]  # Limit to 5 most relevant keywords

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
        
        # Add main functions/features from README analysis
        readme_features = _extract_readme_features(repository_id, repo_data)
        if readme_features:
            response += f"**Main Functions & Features:**\n{readme_features}\n\n"
        
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
        response += f"code ownership, feature introduction history, and development patterns. Just ask!"
        
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

def _extract_readme_features(repository_id: int, repo_data: dict) -> str:
    """Extract main features and functions from README file."""
    try:
        # Get repository path
        repos_path = os.getenv('REPOS_PATH', '../data/repos')
        repo_name = f"{repo_data['owner']}_{repo_data['name']}"
        repo_path = os.path.join(repos_path, repo_name)
        
        # Look for README files
        readme_files = ['README.md', 'readme.md', 'README.txt', 'readme.txt', 'README.rst', 'readme.rst']
        readme_content = None
        
        for readme_file in readme_files:
            readme_path = os.path.join(repo_path, readme_file)
            if os.path.exists(readme_path):
                try:
                    with open(readme_path, 'r', encoding='utf-8', errors='ignore') as f:
                        readme_content = f.read()
                        break
                except Exception as e:
                    logger.warning(f"Could not read {readme_file}: {e}")
                    continue
        
        if not readme_content:
            return None
        
        # Use OpenAI to extract key features if available
        client = get_openai_client()
        if client and readme_content:
            try:
                # Limit README content to prevent token overflow
                if len(readme_content) > 4000:
                    readme_content = readme_content[:4000] + "..."
                
                system_prompt = """You are a technical documentation analyzer. Extract the main functions, features, and capabilities from this README file.

Focus on:
- Core functionality and features
- Key capabilities and use cases
- Main components or modules
- Primary purpose of the project

Format your response as a concise bulleted list (3-6 key points maximum). Be specific and technical but concise."""

                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Extract main features from this README:\n\n{readme_content}"}
                    ],
                    temperature=0.1,
                    max_tokens=300
                )
                
                features_text = response.choices[0].message.content.strip()
                return features_text
                
            except Exception as e:
                logger.warning(f"OpenAI feature extraction failed: {e}")
                # Fallback to simple keyword extraction
                return _extract_features_fallback(readme_content)
        else:
            # Fallback to simple keyword extraction
            return _extract_features_fallback(readme_content)
            
    except Exception as e:
        logger.warning(f"Error extracting README features: {e}")
        return None

def _extract_features_fallback(readme_content: str) -> str:
    """Fallback method to extract features from README using simple text analysis."""
    try:
        lines = readme_content.split('\n')
        features = []
        
        # Look for common feature indicators
        feature_indicators = [
            'features', 'functionality', 'capabilities', 'what it does',
            'key features', 'main features', 'core features'
        ]
        
        # Look for bullet points or numbered lists after feature sections
        in_feature_section = False
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            # Check if we're entering a feature section
            if any(indicator in line_lower for indicator in feature_indicators):
                in_feature_section = True
                continue
            
            # If we're in a feature section, look for bullet points
            if in_feature_section:
                # Stop if we hit another major section
                if line.startswith('#') and not any(indicator in line_lower for indicator in feature_indicators):
                    break
                
                # Extract bullet points or numbered items
                if line.strip().startswith(('- ', '* ', '+ ')) or line.strip().startswith(tuple(f'{i}.' for i in range(1, 10))):
                    feature = line.strip().lstrip('- * + 0123456789.')
                    if len(feature) > 10 and len(feature) < 200:  # Reasonable feature description length
                        features.append(f"- {feature}")
                        if len(features) >= 5:  # Limit to 5 features
                            break
        
        # If no structured features found, look for description patterns
        if not features:
            # Look for project description or purpose
            for line in lines[:20]:  # Check first 20 lines
                if len(line.strip()) > 50 and len(line.strip()) < 300:
                    if any(word in line.lower() for word in ['analyze', 'provide', 'enable', 'allow', 'help', 'tool', 'system']):
                        features.append(f"- {line.strip()}")
                        break
        
        return '\n'.join(features) if features else None
        
    except Exception as e:
        logger.warning(f"Fallback feature extraction failed: {e}")
        return None

def _generate_query_suggestions(repository_id: int, repo_data: dict) -> list:
    """Generate contextual query suggestions."""
    logger.debug(f"Generating suggestions for repository {repository_id}: {repo_data.get('name', 'Unknown')}")
    
    suggestions = [
        "Who are the main contributors to this project?",
        "Show me the commit timeline for the last 3 months",
        "When was the authentication feature introduced?",
        "How did the authentication system evolve over time?",
        "Why was the login feature changed?",
        "What are the development patterns in this repository?",
        "Which files have changed the most?",
        "When was the login functionality added?",
        "Give me an overview of code ownership",
        "What programming languages are used in this project?",
        "When was this project most active?",
        "Who are the experts for different file types?",
        "Show me collaboration patterns between developers",
        "What are the most common types of commits?",
        "How has the codebase evolved over time?",
        "Why were certain features introduced?"
    ]
    
    # Add repository-specific suggestions based on language
    if repo_data['language']:
        logger.debug(f"Adding language-specific suggestions for {repo_data['language']}")
        suggestions.append(f"Show me {repo_data['language']} experts in this project")
        suggestions.append(f"How has the {repo_data['language']} code evolved over time?")
    
    logger.debug(f"Generated {len(suggestions)} suggestions for repository {repository_id}")
    return suggestions

def _generate_commit_summary(commits: List[Dict], context: str) -> str:
    """
    Generate a summary of commits using OpenAI.
    
    Args:
        commits: List of commit dictionaries
        context: Context for the summary (e.g., "introduction of authentication")
        
    Returns:
        Summary text or None if OpenAI is not available
    """
    try:
        client = get_openai_client()
        if not client or not commits:
            return None
        
        # Prepare commit messages for analysis
        commit_messages = []
        for commit in commits[:10]:  # Limit to 10 most relevant commits
            commit_info = f"[{commit['timestamp'][:10]}] {commit['author']}: {commit['message']}"
            commit_messages.append(commit_info)
        
        commits_text = "\n".join(commit_messages)
        
        system_prompt = f"""You are a code repository analyst. Analyze the following commit messages related to the {context} and provide a concise summary.

Focus on:
- What was implemented or changed
- The main purpose or motivation behind the changes
- Key technical decisions or approaches
- Any notable patterns or evolution in the implementation

Keep the summary concise (2-4 sentences) and technical but accessible."""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze these commits:\n\n{commits_text}"}
            ],
            temperature=0.1,
            max_tokens=200
        )
        
        summary = response.choices[0].message.content.strip()
        logger.debug(f"Generated commit summary: {summary[:100]}...")
        return summary
        
    except Exception as e:
        logger.warning(f"Failed to generate commit summary: {e}")
        return None

def _generate_evolution_summary(commits: List[Dict], context: str) -> str:
    """
    Generate an evolution summary of commits using OpenAI.
    
    Args:
        commits: List of commit dictionaries in chronological order
        context: Context for the summary (e.g., "evolution of authentication")
        
    Returns:
        Evolution summary text or None if OpenAI is not available
    """
    try:
        client = get_openai_client()
        if not client or not commits:
            return None
        
        # Prepare chronological commit information
        commit_timeline = []
        for i, commit in enumerate(commits[:15]):  # Limit to 15 commits
            commit_info = f"{i+1}. [{commit['timestamp'][:10]}] {commit['author']}: {commit['message']}"
            if commit.get('files_changed'):
                commit_info += f" ({commit['files_changed']} files)"
            commit_timeline.append(commit_info)
        
        timeline_text = "\n".join(commit_timeline)
        
        system_prompt = f"""You are a software development analyst. Analyze the chronological evolution of commits related to the {context}.

Provide insights on:
- How the feature/component evolved over time
- Key phases or milestones in development
- Reasons for changes (bug fixes, enhancements, refactoring)
- Technical decisions and their motivations
- Overall development patterns and trends

Format as a narrative summary (3-5 sentences) that tells the story of how this feature developed."""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this chronological development:\n\n{timeline_text}"}
            ],
            temperature=0.1,
            max_tokens=300
        )
        
        summary = response.choices[0].message.content.strip()
        logger.debug(f"Generated evolution summary: {summary[:100]}...")
        return summary
        
    except Exception as e:
        logger.warning(f"Failed to generate evolution summary: {e}")
        return None