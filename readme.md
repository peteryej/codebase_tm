Project: Codebase Time Machine

  Description: Navigate any codebase through time, understanding evolution of features and architectural decisions.

  Requirements:
  • Clone repo and analyze full git history
  • Build semantic understanding of code changes over time
  • Answer questions like "Why was this pattern introduced?" or "Show me how auth evolved"
  • Visualize code ownership and complexity trends
  • Link commits to business features/decisions

  - Choose simple solutions that can be run from a single machine
  - frontend should accept a github public repo link and provide a chat interface. 
  - Keep frontend UI simple and implement with static pages.

## Backend API Functions

### Repository Analysis
- **POST /api/repository/validate** - Validates GitHub repository URL
- **POST /api/repository/analyze** - Clones and analyzes repository (commits, files, contributors)
- **GET /api/repository/{id}/status** - Gets analysis status and basic repository info
- **GET /api/repository/{id}/authors** - Returns contributor statistics and commit data
- **GET /api/repository/{id}/ownership** - Provides code ownership analysis
- **GET /api/repository/{id}/timeline** - Gets recent commit timeline data

### Intelligent Chat System
- **POST /api/chat/query** - Processes natural language queries using OpenAI classification
  - **Structured Data Queries**: Uses repository analytics for questions about contributors, timelines, ownership, patterns
  - **RAG Codebase Queries**: Analyzes actual source code files for implementation details using OpenAI
- **GET /api/chat/suggestions** - Generates contextual query suggestions based on repository
- **GET /api/chat/history** - Returns recent chat query history with caching

### Visualization Data
- **GET /api/visualization/{id}/timeline** - Commit timeline data for charts (configurable days/granularity)
- **GET /api/visualization/{id}/contributors** - Top contributors data for visualizations
- **GET /api/visualization/{id}/heatmap** - File change heatmap data
- **GET /api/visualization/{id}/activity** - Development activity patterns
- **GET /api/visualization/{id}/languages** - Programming language distribution

### Core Analysis Modules
- **CommitAnalyzer**: Processes git history, extracts patterns, calculates statistics
- **OwnershipAnalyzer**: Determines code ownership, collaboration metrics, file expertise
- **Query Classification**: OpenAI-powered system that routes queries to appropriate handlers
- **RAG System**: Retrieval-Augmented Generation for code implementation questions

### Key Features
- **OpenAI Integration**: GPT-3.5-turbo for intelligent query classification and code analysis
- **Dual Query Approach**:
  - Repository metadata analysis for statistical queries
  - Source code RAG analysis for implementation details
- **Caching System**: Query response caching with configurable expiration
- **File Discovery**: Smart file relevance scoring for RAG queries
- **Fallback System**: Keyword-based classification when OpenAI is unavailable
