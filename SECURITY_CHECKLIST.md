# Security Hardening Checklist

## Pre-Launch Verification

### Authentication & Sessions
- [ ] AUTH_PROVIDER environment variable set (auth0/clerk/supabase)
- [ ] Auth provider credentials configured (API keys, domain, etc.)
- [ ] FLASK_SECRET_KEY generated and set
- [ ] Session timeout configured (24 hours default)
- [ ] Secure cookies enabled (HttpOnly=true, Secure=true in prod)
- [ ] CSRF protection enabled
- [ ] Multi-factor authentication (MFA) enabled in auth provider

### Data Protection
- [ ] ENCRYPTION_KEY generated and set for sensitive data
- [ ] Database credentials stored in secrets manager (NOT .env or code)
- [ ] Database backups encrypted
- [ ] Database backups tested for recovery
- [ ] API keys and tokens encrypted at rest
- [ ] PII (Personally Identifiable Information) minimized
- [ ] Data retention policy implemented
- [ ] GDPR compliance verified (if applicable)

### Network & Transport
- [ ] SSL/TLS certificate installed
- [ ] HTTPS enforced for all endpoints
- [ ] HSTS header enabled (Strict-Transport-Security)
- [ ] Security headers verified and enabled:
  - [ ] X-Content-Type-Options: nosniff
  - [ ] X-Frame-Options: DENY
  - [ ] Content-Security-Policy: strict
  - [ ] Referrer-Policy: strict-origin-when-cross-origin
  - [ ] Permissions-Policy: restrictive
- [ ] CORS policy configured and tested
- [ ] Mixed content (HTTP/HTTPS) eliminated

### Input Validation & Output Encoding
- [ ] All user inputs validated on server-side
- [ ] Input validators used: validate_ticker, validate_email, etc.
- [ ] All outputs sanitized/escaped
- [ ] XSS protections enabled
- [ ] SQL injection prevention verified (parameterized queries)
- [ ] JSON payload size limits enforced (10MB default)
- [ ] File upload restrictions implemented (if applicable)

### Access Control & Authorization
- [ ] User authentication required for all protected endpoints
- [ ] Role-based access control (RBAC) implemented
- [ ] Per-user data isolation verified
- [ ] Admin functions protected
- [ ] API rate limiting configured:
  - [ ] 100 req/min for general endpoints
  - [ ] 10 req/min for sensitive operations
  - [ ] 1 req/sec for auth endpoints
- [ ] Rate limit bypass not possible
- [ ] Account lockout after failed attempts (if applicable)

### Logging & Monitoring
- [ ] Security logger configured (SECURITY_LOG_LEVEL set)
- [ ] Audit trails enabled for:
  - [ ] Authentication events
  - [ ] Data access (READ, WRITE, DELETE)
  - [ ] Configuration changes
  - [ ] Error conditions
- [ ] Sensitive data redaction verified in logs
- [ ] Log retention policy set (min 90 days)
- [ ] Log analysis automated (alerts for suspicious activity)
- [ ] Intrusion detection system monitoring active

### Error Handling & Debugging
- [ ] Stack traces disabled in production
- [ ] Generic error messages in production
- [ ] Detailed error logging server-side
- [ ] Debug mode disabled in production
- [ ] Exception handling covers all code paths
- [ ] Graceful degradation on errors

### Dependency Management
- [ ] All dependencies pinned to specific versions
- [ ] Vulnerability scanning enabled (safety, bandit)
- [ ] No vulnerable dependencies in use
- [ ] Regular dependency updates scheduled
- [ ] Breaking changes in updates tested
- [ ] Outdated versions of Python/frameworks updated

### Testing & Validation
- [ ] Security unit tests passing (test_security.py)
- [ ] Input validation tests passing (test_validators.py)
- [ ] CSRF tests passing
- [ ] Rate limiting tests passing
- [ ] SQL injection tests passing
- [ ] XSS tests passing
- [ ] Authentication flow tests passing
- [ ] Penetration testing scheduled

### Deployment & Infrastructure
- [ ] Application runs with minimal privileges (non-root)
- [ ] File permissions restricted (600 for secrets, 755 for code)
- [ ] Temporary files cleaned up automatically
- [ ] No hardcoded secrets in code/config
- [ ] Environment variables documented (not in repo)
- [ ] Docker image (if used) scanned for vulnerabilities
- [ ] WAF (Web Application Firewall) configured
- [ ] DDoS protection enabled

### Compliance & Legal
- [ ] Privacy policy updated and published
- [ ] Terms of Service reviewed by legal
- [ ] GDPR compliance verified (if EU users)
- [ ] CCPA compliance verified (if California users)
- [ ] PCI DSS compliance verified (if processing cards)
- [ ] Data processing agreement (DPA) signed with vendors
- [ ] Breach notification plan documented

## After-Launch Monitoring

### Ongoing Security
- [ ] Daily log review for anomalies
- [ ] Weekly security vulnerability scan
- [ ] Monthly penetration testing (if high-value targets)
- [ ] Quarterly security training for team
- [ ] Quarterly dependency updates
- [ ] Quarterly access review (remove unnecessary permissions)
- [ ] Annual comprehensive security audit

### Incident Response
- [ ] Incident response plan documented
- [ ] Team trained on incident response
- [ ] Escalation procedures defined
- [ ] Communication templates prepared
- [ ] Legal team contacted (if breach occurs)
- [ ] Law enforcement notification procedures ready
- [ ] Customer notification procedures ready

### Metrics & KPIs
Track these security metrics:
- [ ] MTTR (Mean Time To Remediate) vulnerabilities
- [ ] Failed authentication attempts (unusual spike = alert)
- [ ] Rate limit violations (detect attacks)
- [ ] Invalid input attempts (detect injection attacks)
- [ ] SSL/TLS certificate expiration date (reminder set)
- [ ] Backup integrity verification (weekly)
- [ ] Uptime and availability (target 99.9%)

## Configuration Examples

### Environment Variables (Production)
```bash
# Authentication
AUTH_PROVIDER=auth0
AUTH0_DOMAIN=your-domain.auth0.com
AUTH0_CLIENT_ID=<your-client-id>
AUTH0_CLIENT_SECRET=<your-client-secret>
CALLBACK_URL=https://yourapp.com/callback

# Security
FLASK_ENV=production
FLASK_SECRET_KEY=<generated-64-char-secret>
ENCRYPTION_KEY=<fernet-key-from-cryptography>

# Database
DATABASE_URL=postgresql://user:secure_password@host:5432/dbname

# Logging
SECURITY_LOG_LEVEL=INFO

# Feature Flags
DISABLE_CSRF_DEV=0  # Should be 0 in production
```

### Docker Security Configuration
```dockerfile
# Run as non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Read-only filesystem where possible
RUN chmod 755 /app && chmod 500 /app/codes

# No secrets in image
# Use secrets from environment/volume mount
```

### Kubernetes Security (if applicable)
```yaml
# Pod Security Policy
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsReadOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop: [ALL]

# Network Policy
podSelector: {}
ingress:
  - from:
      - podSelector:
          matchLabels:
            app: graham-app
  - ports:
      - protocol: TCP
        port: 8050

# Secret Management
volumeMounts:
  - name: secrets
    mountPath: /etc/secrets
    readOnly: true
```

## Red Flags During Audit

🚨 **STOP if you find:**
1. Database passwords in code or .env files
2. API keys/secrets in git history
3. SQL query strings with string concatenation
4. Eval() or exec() calls on user input
5. Disabled CSRF protection
6. Disabled authentication/authorization
7. Debug mode enabled in production
8. Plaintext passwords or tokens in logs
9. No rate limiting on sensitive endpoints
10. Stack traces exposed to users

## Quick Start for New Developers

1. **Local Development Setup**
   ```bash
   # Clone repo
   git clone <repo>
   cd graham-app
   
   # Copy environment template
   cp .env.example .env
   
   # Generate secrets for local dev
   python -c "import secrets; print(secrets.token_hex(32))" # FLASK_SECRET_KEY
   
   # Install dependencies with security scanning
   pip install -r codes/requirements.txt
   safety check
   
   # Run security tests
   pytest tests/test_security.py -v
   
   # Start app
   python -m codes.app
   ```

2. **Before Committing Code**
   ```bash
   # Scan for secrets
   pip install detect-secrets
   detect-secrets scan
   
   # Lint with security checks
   bandit -r codes/
   
   # Check dependencies
   safety check
   
   # Run tests
   pytest tests/ -v
   ```

3. **Before Deployment**
   ```bash
   # Run full security audit
   ./scripts/security-audit.sh
   
   # Verify environment variables
   ./scripts/verify-secrets.sh
   
   # Run penetration tests
   ./scripts/pentest.sh
   ```

---

**Last Updated:** 2026-07-02  
**Maintenance Schedule:** Reviewed quarterly, updated as needed  
**Responsibility:** Security team with engineering oversight
