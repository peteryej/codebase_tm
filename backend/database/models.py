"""
Database models for the Codebase Time Machine
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Text, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import os

Base = declarative_base()

class Repository(Base):
    """Repository model for storing analyzed repositories."""
    __tablename__ = 'repositories'
    
    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    owner = Column(String, nullable=False)
    description = Column(Text)
    language = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_analyzed = Column(DateTime)
    total_commits = Column(Integer, default=0)
    total_files = Column(Integer, default=0)
    total_lines = Column(Integer, default=0)
    status = Column(String, default='pending')  # pending, analyzing, completed, error
    error_message = Column(Text)
    
    # Relationships
    commits = relationship("Commit", back_populates="repository", cascade="all, delete-orphan")
    files = relationship("File", back_populates="repository", cascade="all, delete-orphan")
    patterns = relationship("Pattern", back_populates="repository", cascade="all, delete-orphan")

class Commit(Base):
    """Commit model for storing git commit information."""
    __tablename__ = 'commits'
    
    id = Column(String, primary_key=True)  # Git commit hash
    repo_id = Column(Integer, ForeignKey('repositories.id'), nullable=False)
    author_name = Column(String, nullable=False)
    author_email = Column(String, nullable=False)
    committer_name = Column(String)
    committer_email = Column(String)
    timestamp = Column(DateTime, nullable=False)
    message = Column(Text, nullable=False)
    files_changed = Column(Integer, default=0)
    insertions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)
    is_merge = Column(Boolean, default=False)
    branch = Column(String)
    
    # Relationships
    repository = relationship("Repository", back_populates="commits")
    file_changes = relationship("FileChange", back_populates="commit", cascade="all, delete-orphan")

class File(Base):
    """File model for storing file information and metrics."""
    __tablename__ = 'files'
    
    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey('repositories.id'), nullable=False)
    path = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    extension = Column(String)
    current_lines = Column(Integer, default=0)
    current_complexity = Column(Float, default=0.0)
    total_commits = Column(Integer, default=0)
    created_at = Column(DateTime)
    last_modified = Column(DateTime)
    is_deleted = Column(Boolean, default=False)
    
    # Relationships
    repository = relationship("Repository", back_populates="files")
    ownership = relationship("Ownership", back_populates="file", cascade="all, delete-orphan")
    file_changes = relationship("FileChange", back_populates="file", cascade="all, delete-orphan")
    complexity_history = relationship("ComplexityHistory", back_populates="file", cascade="all, delete-orphan")

class FileChange(Base):
    """File change model for tracking changes in commits."""
    __tablename__ = 'file_changes'
    
    id = Column(Integer, primary_key=True)
    commit_id = Column(String, ForeignKey('commits.id'), nullable=False)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    change_type = Column(String, nullable=False)  # added, modified, deleted, renamed
    insertions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)
    old_path = Column(String)  # For renamed files
    
    # Relationships
    commit = relationship("Commit", back_populates="file_changes")
    file = relationship("File", back_populates="file_changes")

class Ownership(Base):
    """Code ownership model for tracking who owns what code."""
    __tablename__ = 'ownership'
    
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    author_name = Column(String, nullable=False)
    author_email = Column(String, nullable=False)
    lines_contributed = Column(Integer, default=0)
    commits_count = Column(Integer, default=0)
    percentage = Column(Float, default=0.0)
    first_contribution = Column(DateTime)
    last_contribution = Column(DateTime)
    
    # Relationships
    file = relationship("File", back_populates="ownership")

class Pattern(Base):
    """Pattern model for storing detected code patterns."""
    __tablename__ = 'patterns'
    
    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey('repositories.id'), nullable=False)
    pattern_type = Column(String, nullable=False)  # architectural, design, anti-pattern
    pattern_name = Column(String, nullable=False)
    description = Column(Text)
    first_seen_commit = Column(String)
    last_seen_commit = Column(String)
    confidence_score = Column(Float, default=0.0)
    files_affected = Column(Text)  # JSON list of file paths
    
    # Relationships
    repository = relationship("Repository", back_populates="patterns")

class ComplexityHistory(Base):
    """Complexity history model for tracking complexity over time."""
    __tablename__ = 'complexity_history'
    
    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    commit_id = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    cyclomatic_complexity = Column(Float, default=0.0)
    lines_of_code = Column(Integer, default=0)
    maintainability_index = Column(Float, default=0.0)
    halstead_difficulty = Column(Float, default=0.0)
    
    # Relationships
    file = relationship("File", back_populates="complexity_history")

class QueryCache(Base):
    """Query cache model for caching LLM responses."""
    __tablename__ = 'query_cache'
    
    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey('repositories.id'))
    query_hash = Column(String, unique=True, nullable=False)
    query_text = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    hit_count = Column(Integer, default=1)

# Database engine and session setup
def get_database_url():
    """Get database URL from environment or use default."""
    db_path = os.getenv('DATABASE_PATH', './data/cache/cache.db')
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return f'sqlite:///{db_path}'

def create_engine_and_session():
    """Create database engine and session factory."""
    engine = create_engine(get_database_url(), echo=False)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal

def init_database():
    """Initialize the database by creating all tables."""
    engine, _ = create_engine_and_session()
    Base.metadata.create_all(engine)
    print("Database initialized successfully!")

def get_session():
    """Get a database session."""
    _, SessionLocal = create_engine_and_session()
    return SessionLocal()

if __name__ == '__main__':
    init_database()