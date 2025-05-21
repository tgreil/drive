"""Unit tests for the Authentication Views."""

from unittest import mock

from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.test.utils import override_settings

import posthog
import pytest
from mozilla_django_oidc.auth import (
    OIDCAuthenticationBackend as MozillaOIDCAuthenticationBackend,
)

from core import factories
from core.authentication.backends import OIDCAuthenticationBackend
from core.authentication.views import (
    OIDCAuthenticationCallbackView,
)

pytestmark = pytest.mark.django_db


@override_settings(
    FEATURES_ALPHA=True,
    LOGIN_REDIRECT_URL_FAILURE="/auth/failure",
    LOGIN_REDIRECT_URL="/auth/success",
)
@mock.patch.object(
    MozillaOIDCAuthenticationBackend,
    "get_token",
    return_value={"id_token": "mocked_id_token", "access_token": "mocked_access_token"},
)
@mock.patch.object(
    MozillaOIDCAuthenticationBackend, "verify_token", return_value={"not": "needed"}
)
@mock.patch.object(
    OIDCAuthenticationBackend,
    "get_userinfo",
    return_value={"sub": "mocked_sub", "email": "not_allowed@example.com"},
)
@mock.patch.object(posthog, "feature_enabled", return_value=False)
def test_view_login_callback_alpha_not_authorized(
    mocked_feature_enabled, mocked_get_userinfo, mocked_verify_token, mocked_get_token
):
    """When FEATURE_ALPHA is enabled, non-alpha authorized users via posthog should
    be redirected with auth error.
    """

    user = factories.UserFactory(email="not_allowed@example.com")

    request = RequestFactory().get(
        "/callback/", data={"state": "mocked_state", "code": "mocked_code"}
    )
    request.user = user

    middleware = SessionMiddleware(get_response=lambda x: x)
    middleware.process_request(request)

    mocked_state = "mocked_state"
    request.session["oidc_states"] = {mocked_state: {"nonce": "mocked_nonce"}}
    request.session.save()

    callback_view = OIDCAuthenticationCallbackView.as_view()

    response = callback_view(request)
    mocked_get_token.assert_called_once()
    mocked_verify_token.assert_called_once()
    mocked_get_userinfo.assert_called_once()
    mocked_feature_enabled.assert_called_once()
    assert response.status_code == 302
    assert response.url == "/auth/failure?auth_error=alpha"


@override_settings(
    FEATURES_ALPHA=True,
    LOGIN_REDIRECT_URL_FAILURE="/auth/failure",
    LOGIN_REDIRECT_URL="/auth/success",
)
@mock.patch.object(
    MozillaOIDCAuthenticationBackend,
    "get_token",
    return_value={"id_token": "mocked_id_token", "access_token": "mocked_access_token"},
)
@mock.patch.object(
    MozillaOIDCAuthenticationBackend, "verify_token", return_value={"not": "needed"}
)
@mock.patch.object(
    OIDCAuthenticationBackend,
    "get_userinfo",
    return_value={"sub": "mocked_sub", "email": "allowed@example.com"},
)
@mock.patch.object(posthog, "feature_enabled", return_value=True)
def test_view_login_callback_alpha_authorized(
    mocked_feature_enabled, mocked_get_userinfo, mocked_verify_token, mocked_get_token
):
    """When FEATURE_ALPHA is enabled, alpha authorized users via posthog should
    be authorized to login.
    """

    user = factories.UserFactory(email="allowed@example.com")

    request = RequestFactory().get(
        "/callback/", data={"state": "mocked_state", "code": "mocked_code"}
    )
    request.user = user

    middleware = SessionMiddleware(get_response=lambda x: x)
    middleware.process_request(request)

    mocked_state = "mocked_state"
    request.session["oidc_states"] = {mocked_state: {"nonce": "mocked_nonce"}}
    request.session.save()

    callback_view = OIDCAuthenticationCallbackView.as_view()

    response = callback_view(request)
    mocked_get_token.assert_called_once()
    mocked_verify_token.assert_called_once()
    mocked_get_userinfo.assert_called_once()
    mocked_feature_enabled.assert_called_once()
    assert response.status_code == 302
    assert response.url == "/auth/success"


@override_settings(
    FEATURES_ALPHA=False,
    LOGIN_REDIRECT_URL_FAILURE="/auth/failure",
    LOGIN_REDIRECT_URL="/auth/success",
)
@mock.patch.object(
    MozillaOIDCAuthenticationBackend,
    "get_token",
    return_value={"id_token": "mocked_id_token", "access_token": "mocked_access_token"},
)
@mock.patch.object(
    MozillaOIDCAuthenticationBackend, "verify_token", return_value={"not": "needed"}
)
@mock.patch.object(
    OIDCAuthenticationBackend,
    "get_userinfo",
    return_value={"sub": "mocked_sub", "email": "allowed@example.com"},
)
@mock.patch.object(posthog, "feature_enabled", return_value=False)
def test_view_login_callback_alpha_authorized_by_default(
    mocked_feature_enabled, mocked_get_userinfo, mocked_verify_token, mocked_get_token
):
    """By default, all users are authorized to login."""

    user = factories.UserFactory(email="allowed@example.com")

    request = RequestFactory().get(
        "/callback/", data={"state": "mocked_state", "code": "mocked_code"}
    )
    request.user = user

    middleware = SessionMiddleware(get_response=lambda x: x)
    middleware.process_request(request)

    mocked_state = "mocked_state"
    request.session["oidc_states"] = {mocked_state: {"nonce": "mocked_nonce"}}
    request.session.save()

    callback_view = OIDCAuthenticationCallbackView.as_view()

    response = callback_view(request)
    mocked_get_token.assert_called_once()
    mocked_verify_token.assert_called_once()
    mocked_get_userinfo.assert_called_once()
    mocked_feature_enabled.assert_not_called()
    assert response.status_code == 302
    assert response.url == "/auth/success"
