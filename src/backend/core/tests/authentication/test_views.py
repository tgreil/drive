"""Unit tests for the Authentication Views."""

from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import SuspiciousOperation
from django.test import RequestFactory
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import crypto

import posthog
import pytest
from mozilla_django_oidc.auth import (
    OIDCAuthenticationBackend as MozillaOIDCAuthenticationBackend,
)
from rest_framework.test import APIClient

from core import factories
from core.authentication.backends import OIDCAuthenticationBackend
from core.authentication.views import (
    OIDCAuthenticationCallbackView,
    OIDCLogoutCallbackView,
    OIDCLogoutView,
)

pytestmark = pytest.mark.django_db


@override_settings(LOGOUT_REDIRECT_URL="/example-logout")
def test_view_logout_anonymous():
    """Anonymous users calling the logout url,
    should be redirected to the specified LOGOUT_REDIRECT_URL."""

    url = reverse("oidc_logout_custom")
    response = APIClient().get(url)

    assert response.status_code == 302
    assert response.url == "/example-logout"


@mock.patch.object(
    OIDCLogoutView, "construct_oidc_logout_url", return_value="/example-logout"
)
def test_view_logout(mocked_oidc_logout_url):
    """Authenticated users should be redirected to OIDC provider for logout."""

    user = factories.UserFactory()

    client = APIClient()
    client.force_login(user)

    url = reverse("oidc_logout_custom")
    response = client.get(url)

    mocked_oidc_logout_url.assert_called_once()

    assert response.status_code == 302
    assert response.url == "/example-logout"


@override_settings(LOGOUT_REDIRECT_URL="/default-redirect-logout")
@mock.patch.object(
    OIDCLogoutView, "construct_oidc_logout_url", return_value="/default-redirect-logout"
)
def test_view_logout_no_oidc_provider(mocked_oidc_logout_url):
    """Authenticated users should be logged out when no OIDC provider is available."""

    user = factories.UserFactory()

    client = APIClient()
    client.force_login(user)

    url = reverse("oidc_logout_custom")

    with mock.patch("mozilla_django_oidc.views.auth.logout") as mock_logout:
        response = client.get(url)
        mocked_oidc_logout_url.assert_called_once()
        mock_logout.assert_called_once()

    assert response.status_code == 302
    assert response.url == "/default-redirect-logout"


@override_settings(LOGOUT_REDIRECT_URL="/example-logout")
def test_view_logout_callback_anonymous():
    """Anonymous users calling the logout callback url,
    should be redirected to the specified LOGOUT_REDIRECT_URL."""

    url = reverse("oidc_logout_callback")
    response = APIClient().get(url)

    assert response.status_code == 302
    assert response.url == "/example-logout"


@pytest.mark.parametrize(
    "initial_oidc_states",
    [{}, {"other_state": "foo"}],
)
def test_view_logout_persist_state(initial_oidc_states):
    """State value should be persisted in session's data."""

    user = factories.UserFactory()

    request = RequestFactory().request()
    request.user = user

    middleware = SessionMiddleware(get_response=lambda x: x)
    middleware.process_request(request)

    if initial_oidc_states:
        request.session["oidc_states"] = initial_oidc_states
        request.session.save()

    mocked_state = "mock_state"

    OIDCLogoutView().persist_state(request, mocked_state)

    assert "oidc_states" in request.session
    assert request.session["oidc_states"] == {
        "mock_state": {},
        **initial_oidc_states,
    }


@override_settings(OIDC_OP_LOGOUT_ENDPOINT="/example-logout")
@mock.patch.object(OIDCLogoutView, "persist_state")
@mock.patch.object(crypto, "get_random_string", return_value="mocked_state")
def test_view_logout_construct_oidc_logout_url(
    mocked_get_random_string, mocked_persist_state
):
    """Should construct the logout URL to initiate the logout flow with the OIDC provider."""

    user = factories.UserFactory()

    request = RequestFactory().request()
    request.user = user

    middleware = SessionMiddleware(get_response=lambda x: x)
    middleware.process_request(request)

    request.session["oidc_id_token"] = "mocked_oidc_id_token"
    request.session.save()

    redirect_url = OIDCLogoutView().construct_oidc_logout_url(request)

    mocked_persist_state.assert_called_once()
    mocked_get_random_string.assert_called_once()

    params = parse_qs(urlparse(redirect_url).query)

    assert params["id_token_hint"][0] == "mocked_oidc_id_token"
    assert params["state"][0] == "mocked_state"

    url = reverse("oidc_logout_callback")
    assert url in params["post_logout_redirect_uri"][0]


@override_settings(LOGOUT_REDIRECT_URL="/")
def test_view_logout_construct_oidc_logout_url_none_id_token():
    """If no ID token is available in the session,
    the user should be redirected to the final URL."""

    user = factories.UserFactory()

    request = RequestFactory().request()
    request.user = user

    middleware = SessionMiddleware(get_response=lambda x: x)
    middleware.process_request(request)

    redirect_url = OIDCLogoutView().construct_oidc_logout_url(request)

    assert redirect_url == "/"


@pytest.mark.parametrize(
    "initial_state",
    [None, {"other_state": "foo"}],
)
def test_view_logout_callback_wrong_state(initial_state):
    """Should raise an error if OIDC state doesn't match session data."""

    user = factories.UserFactory()

    request = RequestFactory().request()
    request.user = user

    middleware = SessionMiddleware(get_response=lambda x: x)
    middleware.process_request(request)

    if initial_state:
        request.session["oidc_states"] = initial_state
        request.session.save()

    callback_view = OIDCLogoutCallbackView.as_view()

    with pytest.raises(SuspiciousOperation) as excinfo:
        callback_view(request)

    assert (
        str(excinfo.value) == "OIDC callback state not found in session `oidc_states`!"
    )


@override_settings(LOGOUT_REDIRECT_URL="/example-logout")
def test_view_logout_callback():
    """If state matches, callback should clear OIDC state and redirects."""

    user = factories.UserFactory()

    request = RequestFactory().get("/logout-callback/", data={"state": "mocked_state"})
    request.user = user

    middleware = SessionMiddleware(get_response=lambda x: x)
    middleware.process_request(request)

    mocked_state = "mocked_state"

    request.session["oidc_states"] = {mocked_state: {}}
    request.session.save()

    callback_view = OIDCLogoutCallbackView.as_view()

    with mock.patch("mozilla_django_oidc.views.auth.logout") as mock_logout:

        def clear_user(request):
            # Assert state is cleared prior to logout
            assert request.session["oidc_states"] == {}
            request.user = AnonymousUser()

        mock_logout.side_effect = clear_user
        response = callback_view(request)
        mock_logout.assert_called_once()

    assert response.status_code == 302
    assert response.url == "/example-logout"


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
