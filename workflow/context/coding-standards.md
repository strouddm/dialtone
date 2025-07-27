# Coding Standards

## Style Guide

### Python
```python
# Black formatter (88 char lines)
# snake_case functions/variables
# PascalCase classes
# UPPER_CASE constants

# Type hints required
async def process_audio(path: Path) -> dict:
    """One-line summary."""
    pass
```

### JavaScript
```javascript
// 2 spaces, semicolons required
// camelCase functions/variables
// Use const > let, no var
// Template literals for strings
```

## Best Practices
- Early returns to reduce nesting
- Descriptive names (no comments needed)
- Handle errors explicitly
- Use async/await over callbacks
- Context managers for resources

## Testing
- Minimum 80% coverage
- Test naming: `test_function_scenario`
- Critical paths need 95% coverage
- Integration tests for full workflows

## Documentation
- Docstrings for all public functions
- API endpoints need OpenAPI specs
- README must include quick start

## PR Requirements
1. Conventional commits (`feat:`, `fix:`, `docs:`)
2. Tests pass
3. No secrets
4. Reviewed by team

## Quality Gates
- Black/isort/mypy must pass
- No security vulnerabilities
- Docker builds successfully
- Performance benchmarks met