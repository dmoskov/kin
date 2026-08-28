"""Shared Anthropic client factory with Workload Identity Federation support.

Credential resolution order:

1. ``ANTHROPIC_API_KEY`` — static key, kept for local development. Note that
   inside the SDK a set API key also shadows federation, so production task
   definitions must NOT set it (even to an empty string).
2. Workload Identity Federation — when the ``ANTHROPIC_FEDERATION_RULE_ID``,
   ``ANTHROPIC_ORGANIZATION_ID``, and ``ANTHROPIC_SERVICE_ACCOUNT_ID``
   environment variables are present, the ECS task role mints an AWS-signed
   JWT via STS ``GetWebIdentityToken`` and the SDK exchanges it for a
   short-lived Anthropic access token, refreshing it automatically before
   expiry. No static secret exists anywhere in this path.

Raises loudly when neither source is configured rather than letting callers
construct a client that fails on first use.
"""

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import anthropic

_FEDERATION_VARS = (
    "ANTHROPIC_FEDERATION_RULE_ID",
    "ANTHROPIC_ORGANIZATION_ID",
    "ANTHROPIC_SERVICE_ACCOUNT_ID",
)

# GetWebIdentityToken is only served by regional STS endpoints.
_STS_REGION = "us-east-1"

# Reused across calls in the federation path so the SDK's cached access token
# survives between completions — otherwise every Claude call pays a fresh STS
# mint + /v1/oauth/token exchange. The API-key path stays per-call: tests stub
# the SDK module and must see a fresh construction each time.
_federation_client = None


def federation_configured() -> bool:
    """Return True when all required federation environment variables are set."""
    return all(os.environ.get(var) for var in _FEDERATION_VARS)


def anthropic_available() -> bool:
    """Return True when some Anthropic credential source is configured."""
    return bool(os.environ.get("ANTHROPIC_API_KEY")) or federation_configured()


def _sts_web_identity_token() -> str:
    """Mint an AWS-signed OIDC JWT asserting this workload's IAM role.

    The SDK re-invokes this callable on every token refresh, so each
    exchange presents a fresh JWT.
    """
    import boto3

    # Local dev: set ANTHROPIC_STS_ROLE_ARN (e.g. the neutral `local-dev`
    # role) so the JWT asserts that role instead of your personal IAM
    # identity — the federation rule pins the role ARN.
    kwargs = {}
    role_arn = os.environ.get("ANTHROPIC_STS_ROLE_ARN")
    if role_arn:
        assumed = boto3.client("sts", region_name=_STS_REGION).assume_role(
            RoleArn=role_arn, RoleSessionName="anthropic-wif"
        )["Credentials"]
        kwargs = {
            "aws_access_key_id": assumed["AccessKeyId"],
            "aws_secret_access_key": assumed["SecretAccessKey"],
            "aws_session_token": assumed["SessionToken"],
        }

    sts = boto3.client("sts", region_name=_STS_REGION, **kwargs)
    response = sts.get_web_identity_token(
        Audience=["https://api.anthropic.com"],
        SigningAlgorithm="RS256",
        DurationSeconds=900,
    )
    return response["WebIdentityToken"]


def get_anthropic_client() -> "anthropic.Anthropic":
    """Build an Anthropic client from the strongest available credential source.

    ``anthropic`` is imported lazily (matching the repo's local-import idiom)
    so tests that stub the SDK via ``patch.dict(sys.modules, ...)`` keep
    working.
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return anthropic.Anthropic(api_key=api_key)

    if federation_configured():
        global _federation_client
        if _federation_client is not None:
            return _federation_client

        from anthropic import WorkloadIdentityCredentials

        _federation_client = anthropic.Anthropic(
            credentials=WorkloadIdentityCredentials(
                identity_token_provider=_sts_web_identity_token,
                federation_rule_id=os.environ["ANTHROPIC_FEDERATION_RULE_ID"],
                organization_id=os.environ["ANTHROPIC_ORGANIZATION_ID"],
                service_account_id=os.environ["ANTHROPIC_SERVICE_ACCOUNT_ID"],
                workspace_id=os.environ.get("ANTHROPIC_WORKSPACE_ID"),
            ),
        )
        return _federation_client

    raise RuntimeError(
        "No Anthropic credentials configured: set ANTHROPIC_API_KEY (local dev) "
        "or the workload identity federation variables "
        "(ANTHROPIC_FEDERATION_RULE_ID, ANTHROPIC_ORGANIZATION_ID, "
        "ANTHROPIC_SERVICE_ACCOUNT_ID)."
    )
