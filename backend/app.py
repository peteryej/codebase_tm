"""
Codebase Time Machine - Main Flask Application
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__, static_folder='../frontend', static_url_path='')
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Enable CORS for all routes - Environment aware
    if app.config['DEBUG']:
        # Development: Allow localhost origins
        CORS(app, origins=['http://localhost:3000', 'http://127.0.0.1:3000', 'http://localhost:5000', 'http://127.0.0.1:5000'])
    else:
        # Production: Allow all origins (since we're serving frontend from same domain)
        CORS(app, origins="*")
    
    # Import and register blueprints
    from api.repository import repository_bp
    from api.chat import chat_bp
    from api.visualization import visualization_bp
    
    app.register_blueprint(repository_bp, url_prefix='/api/repository')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(visualization_bp, url_prefix='/api/visualization')
    
    # Serve frontend files
    @app.route('/')
    def serve_frontend():
        """Serve the main frontend page."""
        return send_from_directory(app.static_folder, 'index.html')
    
    @app.route('/health')
    def health_check():
        """Health check endpoint."""
        return jsonify({
            'status': 'healthy',
            'service': 'Codebase Time Machine',
            'version': '1.0.0'
        })
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({'error': 'Internal server error'}), 500
    
    return app

# Create app instance for gunicorn
app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5000))
    
    logger.info(f"Starting Codebase Time Machine on port {port}")
    app.run(host='0.0.0.0', port=port, debug=app.config['DEBUG'])