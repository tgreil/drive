"""Authentication Backends for the Drive core app."""

import logging

from django.conf import settings
from django.core.exceptions import SuspiciousOperation

import posthog
from lasuite.oidc_login.backends import (
    OIDCAuthenticationBackend as LaSuiteOIDCAuthenticationBackend,
)

from core.authentication.exceptions import EmailNotAlphaAuthorized
from core.models import DuplicateEmailError

logger = logging.getLogger(__name__)


class OIDCAuthenticationBackend(LaSuiteOIDCAuthenticationBackend):
    """Custom OpenID Connect (OIDC) Authentication Backend.

    This class overrides the default OIDC Authentication Backend to accommodate differences
    in the User and Identity models, and handles signed and/or encrypted UserInfo response.
    """

    def get_extra_claims(self, user_info):
        """
        Return extra claims from user_info.

        Args:
          user_info (dict): The user information dictionary.

        Returns:
          dict: A dictionary of extra claims.
        """
        return {
            "full_name": self.compute_full_name(user_info),
            "short_name": user_info.get(settings.OIDC_USERINFO_SHORTNAME_FIELD),
        }

    def get_existing_user(self, sub, email):
        """Fetch existing user by sub or email."""

        if settings.FEATURES_ALPHA:
            if not posthog.feature_enabled("alpha", email):
                raise EmailNotAlphaAuthorized()

        try:
            return self.UserModel.objects.get_user_by_sub_or_email(sub, email)
        except DuplicateEmailError as err:
            raise SuspiciousOperation(err.message) from err
