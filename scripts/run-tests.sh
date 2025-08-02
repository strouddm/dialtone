#!/bin/bash
# Test execution script for local development

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_TYPE="all"
COVERAGE=false
VERBOSE=false
PARALLEL=false
BENCHMARK=false

# Help function
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Test execution script for Dialtone voice processing system.

OPTIONS:
    -t, --type TYPE         Test type: all, unit, integration, performance, benchmark
    -c, --coverage          Generate coverage report
    -v, --verbose           Verbose output
    -p, --parallel          Run tests in parallel (requires pytest-xdist)
    -b, --benchmark         Run performance benchmarks
    -h, --help              Show this help

EXAMPLES:
    $0                      # Run all tests
    $0 -t unit -c           # Run unit tests with coverage
    $0 -t integration -v    # Run integration tests with verbose output
    $0 -t performance -b    # Run performance tests with benchmarks
    $0 -t benchmark         # Run only benchmark tests

TEST CATEGORIES:
    unit                    Fast unit tests (< 30s total)
    integration            Integration tests (2-5 min)
    performance            Performance and load tests (5-15 min)
    benchmark              Performance benchmarks only
    all                    All test categories

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            TEST_TYPE="$2"
            shift 2
            ;;
        -c|--coverage)
            COVERAGE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -p|--parallel)
            PARALLEL=true
            shift
            ;;
        -b|--benchmark)
            BENCHMARK=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option $1"
            show_help
            exit 1
            ;;
    esac
done

# Setup environment
export TESTING=true
export PYTHONPATH=$(pwd)
export LOG_LEVEL=DEBUG

# Create test directories
mkdir -p /tmp/test_vault
mkdir -p /tmp/test_uploads  
mkdir -p /tmp/test_sessions

echo -e "${BLUE}Dialtone Test Runner${NC}"
echo -e "${BLUE}===================${NC}"
echo "Test type: $TEST_TYPE"
echo "Coverage: $COVERAGE"
echo "Verbose: $VERBOSE"
echo "Parallel: $PARALLEL"
echo "Benchmark: $BENCHMARK"
echo ""

# Build pytest command
PYTEST_CMD="pytest"

# Add parallel execution if requested
if [ "$PARALLEL" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -n auto"
fi

# Add verbose output if requested
if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

# Add coverage if requested
if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=app --cov-report=html --cov-report=term"
fi

# Add benchmark options if requested
if [ "$BENCHMARK" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --benchmark-only --benchmark-sort=mean"
fi

# Execute tests based on type
case $TEST_TYPE in
    "unit")
        echo -e "${GREEN}Running unit tests...${NC}"
        $PYTEST_CMD tests/ -m "not integration and not slow and not benchmark" --maxfail=10
        ;;
    "integration")
        echo -e "${GREEN}Running integration tests...${NC}"
        $PYTEST_CMD tests/integration/ -m integration --maxfail=5
        ;;
    "performance")
        echo -e "${GREEN}Running performance tests...${NC}"
        $PYTEST_CMD tests/performance/ -m "performance or load" --maxfail=3
        ;;
    "benchmark")
        echo -e "${GREEN}Running benchmark tests...${NC}"
        $PYTEST_CMD tests/performance/test_benchmarks.py -m benchmark --benchmark-only --benchmark-sort=mean
        ;;
    "all")
        echo -e "${GREEN}Running all tests...${NC}"
        
        # Unit tests first (fast)
        echo -e "${YELLOW}Step 1/3: Unit tests${NC}"
        $PYTEST_CMD tests/ -m "not integration and not slow and not benchmark" --maxfail=10
        
        # Integration tests
        echo -e "${YELLOW}Step 2/3: Integration tests${NC}"
        $PYTEST_CMD tests/integration/ -m integration --maxfail=5
        
        # Performance tests (if benchmarks not explicitly disabled)
        if [ "$BENCHMARK" != false ]; then
            echo -e "${YELLOW}Step 3/3: Performance tests${NC}"
            $PYTEST_CMD tests/performance/ -m "not benchmark" --maxfail=3
        fi
        ;;
    *)
        echo -e "${RED}Error: Unknown test type '$TEST_TYPE'${NC}"
        echo "Valid types: unit, integration, performance, benchmark, all"
        exit 1
        ;;
esac

# Check test results
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    
    # Show coverage report location if generated
    if [ "$COVERAGE" = true ]; then
        echo -e "${BLUE}Coverage report: htmlcov/index.html${NC}"
    fi
    
    # Show benchmark results if generated
    if [ "$BENCHMARK" = true ] && [ -f ".benchmarks/Linux-*/benchmark.json" ]; then
        echo -e "${BLUE}Benchmark results: .benchmarks/Linux-*/benchmark.json${NC}"
    fi
else
    echo -e "${RED}❌ Tests failed with exit code $EXIT_CODE${NC}"
fi

# Cleanup
echo -e "${BLUE}Cleaning up test directories...${NC}"
rm -rf /tmp/test_vault/* /tmp/test_uploads/* /tmp/test_sessions/*

exit $EXIT_CODE