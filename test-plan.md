# Codebase Time Machine - Test Plan

## Test Repository
**Target Repository**: https://github.com/peteryej/personal_assistant

This repository will serve as our primary test case for validating the Codebase Time Machine functionality.

## Test Categories

### 1. Repository Analysis Tests

#### 1.1 Basic Repository Information
- **Test**: Validate repository URL parsing and metadata extraction
- **Expected Results**:
  - Repository name: "personal_assistant"
  - Owner: "peteryej"
  - Valid GitHub URL format
  - Repository accessibility (public)

#### 1.2 Git History Analysis
- **Test**: Clone and analyze commit history
- **Expected Results**:
  - Extract all commits with timestamps
  - Identify unique authors and contributors
  - Calculate total commits, insertions, deletions
  - Track branch information

#### 1.3 File Structure Analysis
- **Test**: Analyze repository file structure and evolution
- **Expected Results**:
  - Map current file structure
  - Track file creation/deletion over time
  - Identify file types and extensions
  - Calculate file sizes and complexity

### 2. Code Ownership Analysis Tests

#### 2.1 Author Contribution Analysis
- **Test**: Calculate code ownership by author
- **Expected Results**:
  - Percentage of code owned by each contributor
  - Lines contributed per author
  - Commit frequency per author
  - Time-based contribution patterns

#### 2.2 File-Level Ownership
- **Test**: Determine primary maintainers for each file
- **Expected Results**:
  - Primary author for each file
  - Secondary contributors
  - Ownership percentage breakdown
  - Last modification details

### 3. Pattern Detection Tests

#### 3.1 Architectural Pattern Recognition
- **Test**: Identify common code patterns and structures
- **Expected Results for personal_assistant repo**:
  - Python project structure patterns
  - Configuration file patterns
  - Documentation patterns (README, requirements.txt)
  - Testing patterns (if present)

#### 3.2 Evolution Pattern Analysis
- **Test**: Track how patterns evolved over time
- **Expected Results**:
  - When certain patterns were introduced
  - Pattern modification timeline
  - Refactoring events detection
  - Dependency changes over time

### 4. Complexity Metrics Tests

#### 4.1 Code Complexity Analysis
- **Test**: Calculate complexity metrics for Python files
- **Expected Results**:
  - Cyclomatic complexity per function/method
  - Lines of code trends over time
  - Function/class count evolution
  - Complexity hotspots identification

#### 4.2 Dependency Analysis
- **Test**: Analyze project dependencies
- **Expected Results**:
  - External dependencies (requirements.txt)
  - Internal module dependencies
  - Dependency evolution over time
  - Unused dependency detection

### 5. Natural Language Query Tests

#### 5.1 Basic Query Processing
Test queries specific to the personal_assistant repository:

**Query 1**: "What is this repository about?"
- **Expected**: Description of personal assistant functionality
- **Validation**: Should identify main purpose from README/code

**Query 2**: "Who are the main contributors?"
- **Expected**: List of authors with contribution percentages
- **Validation**: Match with git log analysis

**Query 3**: "Show me the commit timeline"
- **Expected**: Chronological list of commits with dates
- **Validation**: Match with git history

**Query 4**: "What files have changed the most?"
- **Expected**: Files with highest modification frequency
- **Validation**: Cross-reference with git diff analysis

#### 5.2 Advanced Query Processing
**Query 5**: "How has the project structure evolved?"
- **Expected**: Timeline of major structural changes
- **Validation**: Track directory/file additions/removals

**Query 6**: "What are the most complex parts of the code?"
- **Expected**: Files/functions with highest complexity scores
- **Validation**: Match with complexity analysis results

**Query 7**: "When were dependencies last updated?"
- **Expected**: Timeline of dependency changes
- **Validation**: Track requirements.txt modifications

### 6. Visualization Tests

#### 6.1 Timeline Visualization
- **Test**: Generate commit timeline chart
- **Expected Results**:
  - X-axis: Time (dates)
  - Y-axis: Commit frequency
  - Interactive zoom and filter capabilities
  - Hover details for individual commits

#### 6.2 Ownership Heatmap
- **Test**: Create code ownership visualization
- **Expected Results**:
  - File/directory structure as heatmap
  - Color intensity based on ownership percentage
  - Interactive drill-down capabilities
  - Author legend and filtering

#### 6.3 Complexity Trends
- **Test**: Display complexity evolution over time
- **Expected Results**:
  - Line chart showing complexity trends
  - Multiple metrics on same chart
  - Ability to filter by file/module
  - Highlight complexity spikes

### 7. Performance Tests

#### 7.1 Analysis Speed
- **Test**: Measure analysis time for personal_assistant repo
- **Target**: Complete analysis in < 2 minutes
- **Metrics**:
  - Clone time
  - Commit analysis time
  - Pattern detection time
  - Database insertion time

#### 7.2 Query Response Time
- **Test**: Measure query processing speed
- **Target**: < 2 seconds for cached queries, < 10 seconds for new queries
- **Metrics**:
  - Database query time
  - LLM processing time
  - Response formatting time

#### 7.3 Memory Usage
- **Test**: Monitor memory consumption during analysis
- **Target**: < 1GB RAM usage for personal_assistant repo
- **Metrics**:
  - Peak memory usage
  - Memory cleanup after analysis
  - Concurrent analysis impact

### 8. Error Handling Tests

#### 8.1 Invalid Repository URLs
- **Test Cases**:
  - Non-existent repository
  - Private repository (should fail gracefully)
  - Malformed URLs
  - Non-GitHub URLs

#### 8.2 Network Issues
- **Test Cases**:
  - GitHub API rate limiting
  - Network connectivity issues
  - Partial clone failures
  - API authentication failures

#### 8.3 Large Repository Handling
- **Test**: Simulate analysis of repositories approaching limits
- **Expected**: Graceful degradation or progressive loading

### 9. Integration Tests

#### 9.1 End-to-End Workflow
1. **Input**: Repository URL (personal_assistant)
2. **Process**: Complete analysis pipeline
3. **Output**: Functional web interface with all features
4. **Validation**: All components working together

#### 9.2 API Integration
- **Test**: All REST endpoints with personal_assistant data
- **Endpoints to test**:
  - `POST /api/repository/analyze`
  - `GET /api/repository/{id}/status`
  - `POST /api/chat/query`
  - `GET /api/commits/timeline`
  - `GET /api/ownership/{file}`
  - `GET /api/complexity/trends`

### 10. User Experience Tests

#### 10.1 Frontend Functionality
- **Test**: Complete user workflow
- **Steps**:
  1. Enter repository URL
  2. Wait for analysis completion
  3. Ask natural language questions
  4. Interact with visualizations
  5. Navigate between different views

#### 10.2 Chat Interface
- **Test**: Chat functionality with personal_assistant context
- **Validation**:
  - Query input and submission
  - Response formatting and display
  - Query history maintenance
  - Error message handling

## Test Data Expectations for personal_assistant Repository

Based on the repository structure, we expect to find:

### Repository Characteristics
- **Language**: Primarily Python
- **Structure**: Typical Python project with modules
- **Dependencies**: Python packages (requirements.txt)
- **Documentation**: README files
- **Configuration**: Setup/config files

### Analysis Expectations
- **Commit History**: Multiple commits showing development progression
- **File Types**: `.py`, `.txt`, `.md`, `.json`, etc.
- **Complexity**: Moderate complexity typical of personal projects
- **Patterns**: Python project patterns, module organization

### Query Test Results
- **"What does this code do?"**: Should identify personal assistant functionality
- **"Show me the main modules"**: Should list primary Python files
- **"Who wrote most of the code?"**: Should identify peteryej as primary author
- **"When was this project most active?"**: Should show development timeline

## Test Environment Setup

### Prerequisites
```bash
# Test environment requirements
python -m pytest --version  # Ensure pytest is available
git --version               # Ensure git is available
curl --version             # For API testing
```

### Test Data Preparation
```bash
# Create test data directory
mkdir -p tests/data/personal_assistant

# Set up test configuration
export TEST_REPO_URL="https://github.com/peteryej/personal_assistant"
export TEST_CACHE_DB="tests/data/test_cache.db"
export TEST_REPOS_PATH="tests/data/repos"
```

### Automated Test Execution
```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/test_repository_analysis.py -v
pytest tests/test_nlp_queries.py -v
pytest tests/test_visualizations.py -v

# Run performance tests
pytest tests/test_performance.py -v --benchmark-only
```

## Success Criteria

### Minimum Viable Product (MVP)
- ✅ Successfully clone and analyze personal_assistant repository
- ✅ Extract basic commit history and file information
- ✅ Answer at least 5 basic natural language queries
- ✅ Display timeline visualization
- ✅ Complete analysis in under 5 minutes

### Full Feature Set
- ✅ All visualization components working
- ✅ Advanced pattern detection
- ✅ Complex natural language query processing
- ✅ Real-time chat interface
- ✅ Performance targets met
- ✅ Error handling robust

## Test Schedule

### Phase 1: Core Functionality (Week 1)
- Repository cloning and basic analysis
- Database operations
- Simple queries

### Phase 2: Advanced Features (Week 2)
- Pattern detection
- Complex queries
- LLM integration

### Phase 3: User Interface (Week 3)
- Frontend components
- Visualizations
- Chat interface

### Phase 4: Integration & Performance (Week 4)
- End-to-end testing
- Performance optimization
- Error handling refinement

## Continuous Testing Strategy

### Automated Testing
- Unit tests run on every code change
- Integration tests run daily
- Performance benchmarks run weekly

### Manual Testing
- User experience testing with personal_assistant repo
- Edge case validation
- Cross-browser compatibility (for frontend)

### Regression Testing
- Test suite run before each release
- Validate against multiple repository types
- Ensure backward compatibility

This comprehensive test plan ensures that the Codebase Time Machine will work reliably with real repositories like personal_assistant, providing users with accurate insights and a smooth experience.