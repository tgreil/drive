"""
Test moving items within the item tree via an detail action API endpoint.
"""

import random
from uuid import uuid4

from django.utils import timezone

import pytest
from rest_framework.test import APIClient

from core import enums, factories, models

pytestmark = pytest.mark.django_db


def test_api_items_move_anonymous_user():
    """Anonymous users should not be able to move items."""
    item = factories.ItemFactory()
    target = factories.ItemFactory()

    response = APIClient().post(
        f"/api/v1.0/items/{item.id!s}/move/",
        data={"target_item_id": str(target.id)},
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication credentials were not provided."
    }


@pytest.mark.parametrize("role", [None, "reader", "editor"])
def test_api_items_move_authenticated_item_no_permission(role):
    """
    Authenticated users should not be able to move items with insufficient
    permissions on the origin item.
    """
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    item = factories.ItemFactory()
    target = factories.UserItemAccessFactory(user=user, role="owner").item

    if role:
        factories.UserItemAccessFactory(item=item, user=user, role=role)

    response = client.post(
        f"/api/v1.0/items/{item.id!s}/move/",
        data={"target_item_id": str(target.id)},
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "You do not have permission to perform this action."
    }


def test_api_items_move_invalid_target_string():
    """Test for moving a item to an invalid target as a random string."""
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    item = factories.UserItemAccessFactory(user=user, role="owner").item

    response = client.post(
        f"/api/v1.0/items/{item.id!s}/move/",
        data={"target_item_id": "non-existent-id"},
    )

    assert response.status_code == 400
    assert response.json() == {"target_item_id": ["Must be a valid UUID."]}


def test_api_items_move_invalid_target_uuid():
    """Test for moving a item to an invalid target that looks like a UUID."""
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    item = factories.UserItemAccessFactory(user=user, role="owner").item

    response = client.post(
        f"/api/v1.0/items/{item.id!s}/move/",
        data={"target_item_id": str(uuid4())},
    )

    assert response.status_code == 400
    assert response.json() == {"target_item_id": "Target parent item does not exist."}


def test_api_items_move_invalid_position():
    """Test moving a item to an invalid position."""
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    item = factories.UserItemAccessFactory(user=user, role="owner").item
    target = factories.UserItemAccessFactory(user=user, role="owner").item

    response = client.post(
        f"/api/v1.0/items/{item.id!s}/move/",
        data={
            "target_item_id": str(target.id),
            "position": "invalid-position",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "position": ['"invalid-position" is not a valid choice.']
    }


@pytest.mark.parametrize("position", enums.MoveNodePositionChoices.values)
@pytest.mark.parametrize("target_parent_role", models.RoleChoices.values)
@pytest.mark.parametrize("target_role", models.RoleChoices.values)
def test_api_items_move_authenticated_target_roles_mocked(
    target_role, target_parent_role, position
):
    """
    Authenticated users with insufficient permissions on the target item (or its
    parent depending on the position chosen), should not be allowed to move items.
    """

    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    power_roles = ["administrator", "owner"]

    item = factories.ItemFactory(
        users=[(user, random.choice(power_roles))], type=models.ItemTypeChoices.FOLDER
    )
    children = factories.ItemFactory.create_batch(
        3, parent=item, type=models.ItemTypeChoices.FOLDER
    )

    target_parent = factories.ItemFactory(
        users=[(user, target_parent_role)], type=models.ItemTypeChoices.FOLDER
    )
    sibling1, target, sibling2 = factories.ItemFactory.create_batch(
        3, parent=target_parent, type=models.ItemTypeChoices.FOLDER
    )
    models.ItemAccess.objects.create(item=target, user=user, role=target_role)
    target_children = factories.ItemFactory.create_batch(2, parent=target)

    response = client.post(
        f"/api/v1.0/items/{item.id!s}/move/",
        data={"target_item_id": str(target.id), "position": position},
    )

    item.refresh_from_db()

    if (
        position in ["first-child", "last-child"]
        and (target_role in power_roles or target_parent_role in power_roles)
    ) or (
        position in ["first-sibling", "last-sibling", "left", "right"]
        and target_parent_role in power_roles
    ):
        assert response.status_code == 200
        assert response.json() == {"message": "item moved successfully."}

        match position:
            case "first-child":
                assert list(target.get_children()) == [item, *target_children]
            case "last-child":
                assert list(target.get_children()) == [*target_children, item]
            case "first-sibling":
                assert list(target.get_siblings()) == [
                    item,
                    sibling1,
                    target,
                    sibling2,
                ]
            case "last-sibling":
                assert list(target.get_siblings()) == [
                    sibling1,
                    target,
                    sibling2,
                    item,
                ]
            case "left":
                assert list(target.get_siblings()) == [
                    sibling1,
                    item,
                    target,
                    sibling2,
                ]
            case "right":
                assert list(target.get_siblings()) == [
                    sibling1,
                    target,
                    item,
                    sibling2,
                ]
            case _:
                raise ValueError(f"Invalid position: {position}")

        # Verify that the item's children have also been moved
        assert list(item.get_children()) == children
    else:
        assert response.status_code == 400
        assert (
            "You do not have permission to move items"
            in response.json()["target_item_id"]
        )
        assert item.is_root() is True


def test_api_items_move_authenticated_deleted_item():
    """
    It should not be possible to move a deleted item or its descendants, even
    for an owner.
    """
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    item = factories.ItemFactory(
        users=[(user, "owner")],
        deleted_at=timezone.now(),
        type=models.ItemTypeChoices.FOLDER,
    )
    child = factories.ItemFactory(parent=item, users=[(user, "owner")])

    target = factories.ItemFactory(users=[(user, "owner")])

    # Try moving the deleted item
    response = client.post(
        f"/api/v1.0/items/{item.id!s}/move/",
        data={"target_item_id": str(target.id)},
    )
    assert response.status_code == 403
    assert response.json() == {
        "detail": "You do not have permission to perform this action."
    }

    # Verify that the item has not moved
    item.refresh_from_db()
    assert item.is_root() is True

    # Try moving the child of the deleted item
    response = client.post(
        f"/api/v1.0/items/{child.id!s}/move/",
        data={"target_item_id": str(target.id)},
    )
    assert response.status_code == 403
    assert response.json() == {
        "detail": "You do not have permission to perform this action."
    }

    # Verify that the child has not moved
    child.refresh_from_db()
    assert child.is_child_of(item) is True


def test_api_items_move_authenticated_target_not_folder_should_fail():
    """Moving an item to a target that is not a folder is not allowed."""
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    item = factories.ItemFactory(
        users=[(user, "owner")], type=models.ItemTypeChoices.FILE
    )
    target = factories.ItemFactory(
        users=[(user, "owner")], type=models.ItemTypeChoices.FILE
    )

    # trying to move the item to a not folder target
    response = client.post(
        f"/api/v1.0/items/{item.id!s}/move/",
        data={"target_item_id": str(target.id)},
    )

    assert response.status_code == 400
    assert response.json() == {
        "target": ["Only folders can be targeted when moving an item"]
    }


@pytest.mark.parametrize(
    "position",
    enums.MoveNodePositionChoices.values,
)
def test_api_items_move_authenticated_deleted_target_as_child(position):
    """
    It should not be possible to move a item as a child of a deleted target
    even for a owner.
    """
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    item = factories.ItemFactory(users=[(user, "owner")])

    target = factories.ItemFactory(
        users=[(user, "owner")],
        deleted_at=timezone.now(),
        type=models.ItemTypeChoices.FOLDER,
    )
    child = factories.ItemFactory(parent=target, users=[(user, "owner")])

    # Try moving the item to the deleted target
    response = client.post(
        f"/api/v1.0/items/{item.id!s}/move/",
        data={"target_item_id": str(target.id), "position": position},
    )

    assert response.status_code == 400
    assert response.json() == {"target_item_id": "Target parent item does not exist."}

    # Verify that the item has not moved
    item.refresh_from_db()
    assert item.is_root() is True

    # Try moving the item to the child of the deleted target
    response = client.post(
        f"/api/v1.0/items/{item.id!s}/move/",
        data={"target_item_id": str(child.id), "position": position},
    )
    assert response.status_code == 400
    assert response.json() == {"target_item_id": "Target parent item does not exist."}

    # Verify that the item has not moved
    item.refresh_from_db()
    assert item.is_root() is True


@pytest.mark.parametrize(
    "position",
    ["first-sibling", "last-sibling", "left", "right"],
)
def test_api_items_move_authenticated_deleted_target_as_sibling(position):
    """
    It should not be possible to move a item as a sibling of a deleted target item
    if the user has no rigths on its parent.
    """
    user = factories.UserFactory()
    client = APIClient()
    client.force_login(user)

    item = factories.ItemFactory(users=[(user, "owner")])

    target_parent = factories.ItemFactory(
        users=[(user, "owner")],
        deleted_at=timezone.now(),
        type=models.ItemTypeChoices.FOLDER,
    )
    target = factories.ItemFactory(users=[(user, "owner")], parent=target_parent)

    # Try moving the item as a sibling of the target
    response = client.post(
        f"/api/v1.0/items/{item.id!s}/move/",
        data={"target_item_id": str(target.id), "position": position},
    )

    assert response.status_code == 400
    assert response.json() == {"target_item_id": "Target parent item does not exist."}

    # Verify that the item has not moved
    item.refresh_from_db()
    assert item.is_root() is True
