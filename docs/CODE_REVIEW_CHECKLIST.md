# Code Review Checklist

> Use for every Pull Request. Mark each item as `Pass / Fail / N/A`. Request changes if any critical item fails.

## 1. Code Structure & Design
- [ ] Single Responsibility: Functions/classes do one thing well, no god files/methods
- [ ] DRY: No duplicated logic - reusable code extracted to shared functions/modules
- [ ] SOLID / Architecture: Follows project architecture, patterns, and layer separation (`DESIGN.md`)
- [ ] Dependencies: No unnecessary dependencies, correct use of dependency injection
- [ ] Complexity: No overly complex logic, deep nesting (>3 levels), or long functions (>50 lines)
- [ ] Dead code: No commented-out, unreachable, or unused code

## 2. Readability & Maintainability
- [ ] Naming: Variables, functions, classes are descriptive, consistent, and meaningful
- [ ] Formatting: Consistent indentation, spacing, and file organization (passes `ruff format`)
- [ ] Simplicity: Code is straightforward - no clever hacks where simple solution works
- [ ] Size: PR is focused and reasonably sized (<400 lines), easy to review
- [ ] Imports: Organized, no unused imports, follows project conventions

## 3. Error Handling
- [ ] Edge cases handled: Null/empty inputs, boundary conditions, and invalid states
- [ ] Exceptions: Errors caught and handled appropriately, not silently swallowed
- [ ] User-facing errors: Clear, non-technical error messages for users
- [ ] Logging: Errors logged with sufficient context (no sensitive data), correct log levels
- [ ] Fail safely: System fails gracefully, resources (files, connections, DB sessions) are properly released

## 4. Documentation
- [ ] Comments: Complex logic explained with *why*, not just *what*
- [ ] Public API: Functions/classes have docstrings with params, returns, and examples
- [ ] README/Docs updated: API changes, setup, or architecture changes documented in `docs/` or `README.md`
- [ ] Self-documenting: Code is clear enough that comments aren't needed for obvious logic

## 5. Performance
- [ ] Efficient algorithms: Appropriate data structures, no O(n²) where O(n) is possible
- [ ] Database: No N+1 queries, queries are indexed, pagination used for large datasets
- [ ] Resources: No memory leaks, unnecessary loops, or synchronous blocking calls
- [ ] Caching: Caching used where appropriate, cache invalidation considered
- [ ] Scalability: Handles large payloads, concurrent requests, and rate limits

## 6. Security
- [ ] Input validation: All user inputs sanitized and validated (client + server)
- [ ] Injection: Protected against SQL/NoSQL injection, XSS, CSRF
- [ ] Authentication/Authorization: Access controls checked, no privilege escalation
- [ ] Secrets: No hardcoded credentials, API keys, or tokens. Secrets in env vars / vault
- [ ] Data exposure: No sensitive data in logs, URLs, or error responses. PII handled correctly
- [ ] Dependencies: No known vulnerabilities in libraries (`uv audit` / `pip audit`)

## 7. Coding Standards & Best Practices
- [ ] Style guide: Follows team linter/formatter (passes `ruff check` and `pyproject.toml` rules)
- [ ] Version control: Meaningful commits, no large binary files or secrets committed
- [ ] Tests: Unit/integration tests added/updated, edge cases covered, all tests pass (`pytest`)
- [ ] No warnings: No linter, compiler, or build warnings introduced

## 8. Testing (Verification)
- [ ] Tests exist and pass locally and in CI
- [ ] Coverage for new code meets team threshold
- [ ] Manual testing steps provided in PR description

---

### How to Use This Checklist

**Author (Before Requesting Review):**
1. Self-review with this checklist
2. Run `ruff check . && ruff format --check . && pytest`
3. Fill checklist in PR description

**Reviewer (During Review):**
1. Review for understanding first, then functionality, then quality
2. Comment with `Suggestion`, `Question`, or `Required Fix`
3. Check out branch and test if needed

**Approver:**
- Approve only if all critical items pass. At least one approval required before merge.

### Review Template (Copy into PR)

```markdown
#### Code Review Checklist
- [ ] Structure & Design reviewed
- [ ] Readability & Maintainability reviewed
- [ ] Error Handling reviewed
- [ ] Documentation reviewed
- [ ] Performance reviewed
- [ ] Security reviewed
- [ ] Coding Standards & Tests reviewed
```
