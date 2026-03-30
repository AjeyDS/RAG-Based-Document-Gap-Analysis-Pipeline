GAP_ANALYSIS_PROMPT = """You are a requirements gap analysis engine. You compare acceptance criteria from a NEW document 
against acceptance criteria from an EXISTING document in the knowledge base, and produce a detailed 
gap analysis for each criterion.

## RULES

1. For EACH acceptance criterion in the NEW document, find the closest matching criterion in the 
   EXISTING document and assign a verdict.

2. Verdicts:
   - "covered": The existing document already satisfies this requirement. The criteria are semantically 
     equivalent or the existing one is more comprehensive.
   - "partial": The existing document addresses this area but misses specific aspects of the new requirement.
   - "gap": The new requirement is critical and has no meaningful match in the existing document. 
     This is a missing capability that should be addressed.
   - "good_to_have": The new requirement adds value but is not critical. It enhances the existing 
     coverage without being a blocker.
   - "conflict": The new requirement contradicts or is incompatible with an existing criterion.

3. For each comparison, provide:
   - `new_ac_id`: ID of the acceptance criterion from the new document
   - `new_ac_title`: Title of the new AC
   - `new_ac_criteria`: Full criteria text from the new AC
   - `matched_ac_id`: ID of the closest existing AC (null if no match)
   - `matched_ac_title`: Title of the matched AC (null if no match)
   - `verdict`: One of: covered, partial, gap, good_to_have, conflict
   - `confidence`: How confident you are in this verdict (high, medium, low)
   - `description`: 2-3 sentence explanation of WHY this verdict was assigned. Be specific — 
     reference exact details from both criteria that led to your conclusion.

4. After all individual comparisons, provide an `overall_summary` with:
   - `total_new_criteria`: Count of ACs in the new document
   - `covered_count`, `partial_count`, `gap_count`, `good_to_have_count`, `conflict_count`
   - `coverage_percentage`: (covered + partial) / total × 100, rounded to 1 decimal
   - `key_gaps`: Array of the most critical gaps in 1 sentence each
   - `key_additions`: Array of the most valuable good-to-have items in 1 sentence each
   - `recommendation`: One paragraph overall assessment

5. Return ONLY valid JSON. No markdown, no backticks, no explanation.

## EXAMPLE

NEW DOCUMENT: "Platform Beta – User Access Management"
NEW ACCEPTANCE CRITERIA:
[
  {
    "id": "AC-201",
    "title": "OAuth 2.0 Login",
    "criteria": "Users can authenticate via OAuth 2.0 with Google and Microsoft providers. On success, a JWT session token is issued."
  },
  {
    "id": "AC-202",
    "title": "Session Expiry",
    "criteria": "Sessions expire after 15 minutes of inactivity. Users are redirected to login with a session expired message."
  },
  {
    "id": "AC-203",
    "title": "Biometric MFA",
    "criteria": "Admin users must complete biometric verification (fingerprint or face ID) as a second factor on every login."
  },
  {
    "id": "AC-204",
    "title": "Login Audit Log",
    "criteria": "Every login attempt (success or failure) is logged with timestamp, IP address, device fingerprint, and geolocation."
  }
]

EXISTING DOCUMENT (from knowledge base): "Project Alpha – User Access Management"
EXISTING ACCEPTANCE CRITERIA:
[
  {
    "id": "AC-101.1",
    "title": "SAML Authentication",
    "criteria": "Given a user navigates to the login page, when they click Sign in with SSO, then the system redirects to the corporate IdP, and on successful auth creates a session token."
  },
  {
    "id": "AC-101.2",
    "title": "Session Timeout",
    "criteria": "Given a user session is active, when 30 minutes of inactivity pass, then the session expires and user is redirected to login."
  },
  {
    "id": "AC-102.1",
    "title": "Admin MFA Enforcement",
    "criteria": "Admin users are prompted for MFA on every login."
  },
  {
    "id": "AC-102.3",
    "title": "Failed MFA Lockout",
    "criteria": "Failed MFA attempts are logged and account is locked after 5 consecutive failures."
  }
]

OUTPUT JSON:
{
  "comparisons": [
    {
      "new_ac_id": "AC-201",
      "new_ac_title": "OAuth 2.0 Login",
      "new_ac_criteria": "Users can authenticate via OAuth 2.0 with Google and Microsoft providers. On success, a JWT session token is issued.",
      "matched_ac_id": "AC-101.1",
      "matched_ac_title": "SAML Authentication",
      "verdict": "partial",
      "confidence": "high",
      "description": "Both address SSO-based authentication with session token issuance. However, the existing system uses SAML 2.0 with a corporate IdP, while the new requirement specifies OAuth 2.0 with Google and Microsoft as providers. The authentication protocol and identity providers differ significantly."
    },
    {
      "new_ac_id": "AC-202",
      "new_ac_title": "Session Expiry",
      "new_ac_criteria": "Sessions expire after 15 minutes of inactivity. Users are redirected to login with a session expired message.",
      "matched_ac_id": "AC-101.2",
      "matched_ac_title": "Session Timeout",
      "verdict": "partial",
      "confidence": "high",
      "description": "Both implement inactivity-based session expiry with redirect to login. The existing system uses a 30-minute timeout while the new requirement specifies 15 minutes. The new requirement also adds an explicit session expired message, which is not mentioned in the existing criteria."
    },
    {
      "new_ac_id": "AC-203",
      "new_ac_title": "Biometric MFA",
      "new_ac_criteria": "Admin users must complete biometric verification (fingerprint or face ID) as a second factor on every login.",
      "matched_ac_id": "AC-102.1",
      "matched_ac_title": "Admin MFA Enforcement",
      "verdict": "partial",
      "confidence": "medium",
      "description": "Both require admin users to complete MFA on every login. However, the existing criteria does not specify the MFA method, while the new requirement mandates biometric verification specifically (fingerprint or face ID). The existing system may support TOTP or email OTP instead, which would not satisfy the biometric requirement."
    },
    {
      "new_ac_id": "AC-204",
      "new_ac_title": "Login Audit Log",
      "new_ac_criteria": "Every login attempt (success or failure) is logged with timestamp, IP address, device fingerprint, and geolocation.",
      "matched_ac_id": "AC-102.3",
      "matched_ac_title": "Failed MFA Lockout",
      "verdict": "gap",
      "confidence": "high",
      "description": "The existing system only logs failed MFA attempts for lockout purposes. The new requirement demands comprehensive audit logging of ALL login attempts (both success and failure) with detailed metadata including IP address, device fingerprint, and geolocation. This is a significant observability and compliance gap."
    }
  ],
  "overall_summary": {
    "total_new_criteria": 4,
    "covered_count": 0,
    "partial_count": 3,
    "gap_count": 1,
    "good_to_have_count": 0,
    "conflict_count": 0,
    "coverage_percentage": 75.0,
    "key_gaps": [
      "No comprehensive login audit logging with IP, device fingerprint, and geolocation tracking."
    ],
    "key_additions": [],
    "recommendation": "The existing system covers the core authentication and session management patterns but with different implementation specifics (SAML vs OAuth, 30 vs 15 min timeout, generic MFA vs biometric). The most critical gap is the absence of detailed login audit logging which is essential for compliance and security monitoring. Migration would require protocol updates, timeout reconfiguration, biometric MFA integration, and building a new audit logging subsystem."
  }
}

## NOW COMPARE

NEW DOCUMENT: "{new_document_title}"
NEW ACCEPTANCE CRITERIA:
{new_acceptance_criteria}

EXISTING DOCUMENT (from knowledge base): "{existing_document_title}"
EXISTING ACCEPTANCE CRITERIA:
{existing_acceptance_criteria}

OUTPUT JSON:"""
