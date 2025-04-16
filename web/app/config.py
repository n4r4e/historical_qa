from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Settings(BaseSettings):
    """Application settings"""
    # Neo4j settings
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    
    # OpenAI settings
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"  # Default value
    
    # App settings
    app_name: str = "Knowledge Graph QA System"
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"