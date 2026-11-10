"""The pilot's front door (done, not a ticket): HTTP Basic sign-in with the password Terraform put in Secrets Manager.

The browser asks for the user name (analyst) and password once, then sends them with every request.
The password is fetched from Secrets Manager through the VPC endpoint the first time it is needed and kept
in memory: it is never in the code, the environment or the logs.
"""

import base64
import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

USER = "analyst"


class PilotPassword(BaseHTTPMiddleware):
    def __init__(self, app, secret_arn: str, fetch=None):
        super().__init__(app)
        self.secret_arn = secret_arn
        self._fetch = fetch
        self._password: str | None = None

    def password(self) -> str:
        if self._password is None:
            if self._fetch is not None:
                self._password = self._fetch(self.secret_arn)
            else:
                import boto3

                self._password = boto3.client("secretsmanager").get_secret_value(SecretId=self.secret_arn)["SecretString"]
        return self._password

    async def dispatch(self, request, call_next):
        header = request.headers.get("authorization", "")
        if header.startswith("Basic "):
            try:
                user, _, given = base64.b64decode(header[6:]).decode().partition(":")
            except ValueError:
                user, given = "", ""
            if user == USER and hmac.compare_digest(given, self.password()):
                return await call_next(request)
        return Response("Sign in as analyst with the pilot password.", status_code=401,
                        headers={"WWW-Authenticate": 'Basic realm="UC1 pilot"'})
