import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_admin_page(client):
    """Test that the admin page is accessible to the superuser."""
    # Get the user model
    # pylint: disable=invalid-name
    User = get_user_model()

    # Create a superuser
    User.objects.create_superuser("admin", "admin@example.com", "password")

    # Log in as the superuser
    client.login(username="admin", password="password")

    # Get the admin page
    url = reverse("admin:index")
    response = client.get(url)

    # Check that the response is 200 OK
    assert response.status_code == 200
