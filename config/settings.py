from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
class Settings(BaseSettings):
    #Load the configurations from .env 
    module_config = SettingsConfigDict(env_file='.env',env_file_encodings='utf-8',extra = 'ignore')

    #extra variable to read 
    LLM_PROVIDER: str = Field(default='openai')
    EMBEDDING_PROVIDER: str = Field(default='openai')
    DB_PATH: str = Field(default="./data/database/agrisubsidy.db")
    OPENAI_API_KEY : str | None = Field(default=None)

settings =  Settings()   