# Codebase Time Machine - Implementation Guide

## Project Setup Instructions

### Prerequisites
- Python 3.9 or higher
- Git installed on the system
- Node.js (optional, for advanced visualization libraries)
- 10GB free disk space for repository storage
- 2GB RAM minimum

### Python Dependencies

Create a `requirements.txt` file with the following dependencies:

```txt
# Core Web Framework
Flask==3.0.0
Flask-CORS==4.0.0

# Git Operations
GitPython==3.1.40
pygit2==1.13.3

# GitHub API
PyGithub==2.1.1
requests==2.31.0

# Database
SQLAlchemy==2.0.23

# Code Analysis
radon==6.0.1  # For complexity metrics
lizard==1.17.10  # For cyclomatic complexity
pydriller==2.5  # For mining git repositories

# LLM Integration
openai==1.6.1
anthropic==0.8.1

# Data Processing
pandas==2.1.4
numpy==1.26.2

# Utilities
python-dotenv==1.0.0
click==8.1.7
colorama==0.4.6

# Testing
pytest==7.4.3
pytest-cov==4.1.0
pytest-mock==3.12.0

# Development
black==23.12.1
flake8==6.1.0
mypy==1.7.1
```

### Frontend Dependencies

For the frontend, we'll use CDN links for simplicity, but here are the libraries we'll include:

```html
<!-- In index.html -->
<!-- Chart.js for visualizations -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>

<!-- D3.js for complex visualizations -->
<script src="https://d3js.org/d3.v7.min.js"></script>

<!-- Marked.js for markdown rendering in chat -->
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>

<!-- Prism.js for code syntax highlighting -->
<link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism.min.css" rel="stylesheet" />
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
```

## Directory Structure Setup

```bash
# Create the project structure
mkdir -p codebase_tm/backend/{api,analyzers,git_ops,llm,database}
mkdir -p codebase_tm/frontend/{css,js,visualizations}
mkdir -p codebase_tm/data/{repos,cache}
mkdir -p codebase_tm/tests/{unit,integration}
```

## Environment Configuration

Create a `.env` file in the project root:

```env
# GitHub Configuration
GITHUB_TOKEN=your_github_token_here  # Optional, increases API rate limit

# LLM Configuration
LLM_PROVIDER=openai  # or 'anthropic'
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here

# Database Configuration
DATABASE_PATH=./data/cache/cache.db
REPOS_PATH=./data/repos

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=your-secret-key-here
FLASK_PORT=5000

# Analysis Configuration
MAX_REPO_SIZE=10000  # Maximum commits to analyze
CACHE_DURATION=86400  # Cache duration in seconds (24 hours)
MAX_CONCURRENT_ANALYSES=3
```

## Backend Implementation Steps

### Step 1: Flask Application Setup

Create `backend/app.py`:

```python
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# Import blueprints
from api import repository_bp, chat_bp, visualization_bp

app.register_blueprint(repository_bp, url_prefix='/api/repository')
app.register_blueprint(chat_bp, url_prefix='/api/chat')
app.register_blueprint(visualization_bp, url_prefix='/api/visualization')

if __name__ == '__main__':
    app.run(debug=True, port=int(os.getenv('FLASK_PORT', 5000)))
```

### Step 2: Database Models

Create `backend/database/models.py`:

```python
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import os

Base = declarative_base()
engine = create_engine(f"sqlite:///{os.getenv('DATABASE_PATH')}")
Session = sessionmaker(bind=engine)

class Repository(Base):
    __tablename__ = 'repositories'
    
    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    last_analyzed = Column(DateTime)
    total_commits = Column(Integer)
    status = Column(String)
    
    commits = relationship("Commit", back_populates="repository")
    files = relationship("File", back_populates="repository")

# Additional models...
```

### Step 3: Git Operations Module

Create `backend/git_ops/manager.py`:

```python
import git
from github import Github
import os

class GitManager:
    def __init__(self):
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.repos_path = os.getenv('REPOS_PATH')
        self.github = Github(self.github_token) if self.github_token else Github()
    
    def clone_repository(self, repo_url):
        # Implementation for cloning
        pass
    
    def fetch_metadata(self, repo_url):
        # Implementation for fetching via API
        pass
```

### Step 4: Analysis Engine

Create `backend/analyzers/commit_analyzer.py`:

```python
from pydriller import Repository
import radon.complexity as radon_cc

class CommitAnalyzer:
    def analyze_commits(self, repo_path):
        # Implementation for commit analysis
        pass
    
    def calculate_ownership(self, repo_path):
        # Implementation for ownership calculation
        pass
    
    def detect_patterns(self, repo_path):
        # Implementation for pattern detection
        pass
```

### Step 5: LLM Integration

Create `backend/llm/processor.py`:

```python
import openai
from anthropic import Anthropic
import os

class LLMProcessor:
    def __init__(self):
        self.provider = os.getenv('LLM_PROVIDER', 'openai')
        if self.provider == 'openai':
            openai.api_key = os.getenv('OPENAI_API_KEY')
        else:
            self.client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    
    def process_query(self, query, context):
        # Implementation for natural language processing
        pass
```

## Frontend Implementation Steps

### Step 1: Main HTML Structure

Create `frontend/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Codebase Time Machine</title>
    <link rel="stylesheet" href="css/styles.css">
    <!-- CDN links for libraries -->
</head>
<body>
    <div id="app">
        <header>
            <h1>Codebase Time Machine</h1>
            <div id="repo-input">
                <input type="text" id="repo-url" placeholder="Enter GitHub repository URL">
                <button id="analyze-btn">Analyze</button>
            </div>
        </header>
        
        <main>
            <div id="chat-container">
                <!-- Chat interface -->
            </div>
            <div id="visualization-container">
                <!-- Visualizations -->
            </div>
        </main>
    </div>
    
    <script src="js/main.js"></script>
    <script src="js/chat.js"></script>
    <script src="js/visualizations.js"></script>
</body>
</html>
```

### Step 2: JavaScript Modules

Create `frontend/js/main.js`:

```javascript
class CodebaseTimeMachine {
    constructor() {
        this.apiBase = 'http://localhost:5000/api';
        this.currentRepo = null;
        this.init();
    }
    
    init() {
        // Initialize event listeners
        document.getElementById('analyze-btn').addEventListener('click', () => {
            this.analyzeRepository();
        });
    }
    
    async analyzeRepository() {
        const url = document.getElementById('repo-url').value;
        // Implementation for repository analysis
    }
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    new CodebaseTimeMachine();
});
```

## Testing Strategy

### Unit Tests

Create `tests/unit/test_analyzers.py`:

```python
import pytest
from backend.analyzers.commit_analyzer import CommitAnalyzer

def test_commit_analysis():
    analyzer = CommitAnalyzer()
    # Test implementation
    assert True
```

### Integration Tests

Create `tests/integration/test_api.py`:

```python
import pytest
from backend.app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_repository_analysis(client):
    response = client.post('/api/repository/analyze', 
                          json={'url': 'https://github.com/test/repo'})
    assert response.status_code == 200
```

## Deployment Instructions

### Local Development

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd codebase_tm

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# 5. Initialize database
python backend/database/init_db.py

# 6. Run the application
python backend/app.py

# 7. Open browser to http://localhost:5000
```

### Production Deployment

For production deployment on a single machine:

```bash
# 1. Install production server
pip install gunicorn

# 2. Run with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 backend.app:app

# 3. Optional: Use nginx as reverse proxy
# Configure nginx to proxy requests to gunicorn

# 4. Set up systemd service for auto-start
# Create /etc/systemd/system/codebase-tm.service
```

## Performance Optimization Tips

1. **Caching Strategy**
   - Cache repository analysis results for 24 hours
   - Use Redis for session management if scaling
   - Implement query result caching

2. **Database Optimization**
   - Create indexes on frequently queried columns
   - Use connection pooling
   - Implement pagination for large result sets

3. **Git Operations**
   - Use shallow clones for initial analysis
   - Implement incremental updates
   - Parallelize file analysis

4. **Frontend Optimization**
   - Lazy load visualizations
   - Implement virtual scrolling for large datasets
   - Use web workers for heavy computations

## Troubleshooting Guide

### Common Issues

1. **GitHub API Rate Limiting**
   - Solution: Add GitHub token to .env file
   - Implement exponential backoff

2. **Large Repository Analysis Timeout**
   - Solution: Implement progressive loading
   - Use background jobs for analysis

3. **Memory Issues with Large Repos**
   - Solution: Process commits in batches
   - Implement streaming for large files

4. **LLM API Errors**
   - Solution: Implement retry logic
   - Cache successful responses
   - Provide fallback responses

## Security Considerations

1. **Input Validation**
   - Validate GitHub URLs
   - Sanitize user queries
   - Prevent SQL injection

2. **API Security**
   - Implement rate limiting
   - Use API keys for authentication
   - Enable CORS properly

3. **Data Privacy**
   - Only analyze public repositories
   - Don't store sensitive information
   - Implement data retention policies

## Next Development Steps

1. **Week 1**: Set up core infrastructure
2. **Week 2**: Implement basic analysis features
3. **Week 3**: Add LLM integration and chat interface
4. **Week 4**: Build visualizations and polish UI
5. **Week 5**: Testing and optimization
6. **Week 6**: Documentation and deployment

## Resources and References

- [Flask Documentation](https://flask.palletsprojects.com/)
- [GitPython Documentation](https://gitpython.readthedocs.io/)
- [PyDriller Documentation](https://pydriller.readthedocs.io/)
- [Chart.js Documentation](https://www.chartjs.org/docs/)
- [D3.js Documentation](https://d3js.org/)
- [OpenAI API Documentation](https://platform.openai.com/docs/)
- [Anthropic API Documentation](https://docs.anthropic.com/)