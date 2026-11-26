from app.models.enums import OrganizationAccessLevel
from app.services.organization_service import _level_value


def test_level_value_accepts_enum_and_string():
    assert _level_value(OrganizationAccessLevel.EDIT) == "edit"
    assert _level_value("edit") == "edit"
    assert _level_value(None) == "view"
