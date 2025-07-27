#!/bin/bash
# One-click setup script for Dialtone development

set -e  # Exit on error

echo "🎵 Setting up Dialtone development environment..."

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    echo "Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11+."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python $PYTHON_VERSION is installed, but $REQUIRED_VERSION+ is required."
    exit 1
fi

echo "✅ Prerequisites check passed!"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file to set your Obsidian vault path!"
fi

# Create virtual environment for local development
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install development dependencies
echo "Installing development dependencies..."
pip install --upgrade pip
pip install -r requirements-dev.txt

# Create necessary directories
echo "Creating project directories..."
mkdir -p logs
mkdir -p obsidian-vault  # Default vault location

# Run code quality checks
echo "Running code quality checks..."
black --check app tests || true
mypy app || true

# Build Docker image
echo "Building Docker image..."
docker-compose build

# Run tests
echo "Running tests..."
pytest tests/ -v --cov=app --cov-report=term-missing || true

# Start services
echo "Starting services..."
docker-compose up -d

# Wait for health check
echo "Waiting for API to be healthy..."
for i in {1..30}; do
    if curl -f http://localhost:8000/health &> /dev/null; then
        echo "✅ API is healthy!"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 1
done

# Display status
echo ""
echo "🎉 Dialtone setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Edit .env file to set your Obsidian vault path"
echo "2. View API docs: http://localhost:8000/docs"
echo "3. Check health: http://localhost:8000/health"
echo "4. View logs: docker-compose logs -f"
echo ""
echo "🛠️  Development commands:"
echo "- Run tests: pytest"
echo "- Format code: black app tests"
echo "- Type check: mypy app"
echo "- Restart services: docker-compose restart"
echo "- Stop services: docker-compose down"
echo ""

# Check if API is actually responding
if curl -f http://localhost:8000/health &> /dev/null; then
    echo "✅ API is running at http://localhost:8000"
    curl -s http://localhost:8000/health | python3 -m json.tool
else
    echo "⚠️  API is not responding. Check logs with: docker-compose logs"
fi