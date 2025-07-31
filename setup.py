#!/usr/bin/env python3
"""
Setup script for AI Restaurant Agent Backend
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(command, description):
    """Run a command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False


def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True


def install_dependencies():
    """Install Python dependencies"""
    return run_command("pip install -r requirements.txt", "Installing Python dependencies")


def setup_database():
    """Initialize database with Alembic"""
    # Create initial migration
    if not run_command("alembic revision --autogenerate -m 'Initial migration'", "Creating initial database migration"):
        return False
    
    # Apply migration
    if not run_command("alembic upgrade head", "Applying database migration"):
        return False
    
    return True


def create_env_file():
    """Create .env file from template"""
    env_file = Path(".env")
    env_example = Path("env.example")
    
    if env_file.exists():
        print("⚠️  .env file already exists, skipping creation")
        return True
    
    if not env_example.exists():
        print("❌ env.example file not found")
        return False
    
    # Copy env.example to .env
    try:
        with open(env_example, 'r') as src:
            content = src.read()
        
        with open(env_file, 'w') as dst:
            dst.write(content)
        
        print("✅ Created .env file from template")
        print("⚠️  Please update .env file with your actual API keys and configuration")
        return True
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return False


def main():
    """Main setup function"""
    print("🚀 Setting up AI Restaurant Agent Backend")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("❌ Failed to install dependencies")
        sys.exit(1)
    
    # Create .env file
    if not create_env_file():
        print("❌ Failed to create .env file")
        sys.exit(1)
    
    # Setup database
    if not setup_database():
        print("❌ Failed to setup database")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("✅ Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Update .env file with your API keys:")
    print("   - TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN")
    print("   - OPENAI_API_KEY")
    print("   - ELEVENLABS_API_KEY")
    print("   - DATABASE_URL")
    print("2. Run the application: uvicorn app.main:app --reload")
    print("3. Test the API: http://localhost:8000/docs")
    print("\n📚 For more information, see README.md")


if __name__ == "__main__":
    main() 