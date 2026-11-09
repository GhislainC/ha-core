"""Test entity functions for Home Assistant templates."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)

from tests.helpers.template.helpers import assert_result_info, render, render_to_info


def test_entity_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test entity_name method."""
    assert render(hass, "{{ entity_name('sensor.fake') }}") is None

    entry = entity_registry.async_get_or_create(
        "sensor", "test", "unique_1", original_name="Registry Sensor"
    )
    assert render(hass, f"{{{{ entity_name('{entry.entity_id}') }}}}") == (
        "Registry Sensor"
    )
    assert render(hass, f"{{{{ '{entry.entity_id}' | entity_name }}}}") == (
        "Registry Sensor"
    )

    entity_registry.async_update_entity(entry.entity_id, name="My Custom Sensor")
    assert render(hass, f"{{{{ entity_name('{entry.entity_id}') }}}}") == (
        "My Custom Sensor"
    )

    # Falls back to state for entities not in the registry
    hass.states.async_set(
        "light.no_unique_id", "on", {"friendly_name": "No Unique ID Light"}
    )
    assert render(hass, "{{ entity_name('light.no_unique_id') }}") == (
        "No Unique ID Light"
    )

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        name="My Device",
    )
    entry2 = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique_2",
        config_entry=config_entry,
        device_id=device_entry.id,
        has_entity_name=True,
        original_name="Temperature",
    )
    assert render(hass, f"{{{{ entity_name('{entry2.entity_id}') }}}}") == (
        "Temperature"
    )
    assert (
        render(hass, f"{{{{ entity_name('{entry2.entity_id}', fallback=True) }}}}")
        == "Temperature"
    )

    # The main entity of a device has no name of its own
    entry3 = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique_3",
        config_entry=config_entry,
        device_id=device_entry.id,
        has_entity_name=True,
    )
    assert render(hass, f"{{{{ entity_name('{entry3.entity_id}') }}}}") == ""
    assert (
        render(hass, f"{{{{ entity_name('{entry3.entity_id}', fallback=True) }}}}")
        == "My Device"
    )
    assert (
        render(hass, f"{{{{ '{entry3.entity_id}' | entity_name(fallback=True) }}}}")
        == "My Device"
    )

    device_registry.async_update_device(device_entry.id, name_by_user="User Device")
    assert (
        render(hass, f"{{{{ entity_name('{entry3.entity_id}', fallback=True) }}}}")
        == "User Device"
    )

    entity_registry.async_update_entity(entry3.entity_id, name="")
    assert (
        render(hass, f"{{{{ entity_name('{entry3.entity_id}', fallback=True) }}}}")
        == "User Device"
    )

    entity_registry.async_update_entity(entry3.entity_id, name="Own Name")
    assert (
        render(hass, f"{{{{ entity_name('{entry3.entity_id}', fallback=True) }}}}")
        == "Own Name"
    )


def test_is_hidden_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test is_hidden_entity method."""
    hidden_entity = entity_registry.async_get_or_create(
        "sensor", "mock", "hidden", hidden_by=er.RegistryEntryHider.USER
    )
    visible_entity = entity_registry.async_get_or_create("sensor", "mock", "visible")
    assert render(hass, f"{{{{ is_hidden_entity('{hidden_entity.entity_id}') }}}}")

    assert not render(hass, f"{{{{ is_hidden_entity('{visible_entity.entity_id}') }}}}")

    assert not render(
        hass,
        f"{{{{ ['{visible_entity.entity_id}']"
        f" | select('is_hidden_entity') | first }}}}",
    )


async def test_expand_target(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    floor_registry: fr.FloorRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test expand_target function and filter."""
    # Test invalid / empty target
    assert render(hass, "{{ expand_target(none) }}") == []
    assert render(hass, "{{ expand_target(56) }}") == []
    assert render(hass, "{{ expand_target('light.test') }}") == []
    assert render(hass, "{{ expand_target({}) }}") == []
    assert render(hass, "{{ {} | expand_target }}") == []

    # Setup floor, area, label, config entry, device, entities
    floor = floor_registry.async_create("Ground Floor")
    area_kitchen = area_registry.async_create("Kitchen")
    area_kitchen = area_registry.async_update(area_kitchen.id, floor_id=floor.floor_id)

    area_living = area_registry.async_create("Living Room")

    label = label_registry.async_create("test_label")

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    device_kitchen = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:01")},
        suggested_area=area_kitchen.id,
    )
    device_living = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:02")},
        suggested_area=area_living.id,
    )

    # Entities
    # 1. Kitchen primary entity (inherits area from device_kitchen)
    e1 = entity_registry.async_get_or_create(
        "light",
        "test",
        "kitchen_light",
        config_entry=config_entry,
        device_id=device_kitchen.id,
        original_name="Kitchen Light",
    )

    # 2. Kitchen config entity (entity_category, inherits area from device_kitchen)
    e2 = entity_registry.async_get_or_create(
        "switch",
        "test",
        "kitchen_config",
        config_entry=config_entry,
        device_id=device_kitchen.id,
        original_name="Kitchen Config",
        entity_category=EntityCategory.CONFIG,
    )

    # 3. Living room entity with label (inherits area from device_living)
    e3 = entity_registry.async_get_or_create(
        "light",
        "test",
        "living_light",
        config_entry=config_entry,
        device_id=device_living.id,
        original_name="Living Light",
    )
    entity_registry.async_update_entity(e3.entity_id, labels={label.label_id})
    # 4. Standalone entity
    e4 = entity_registry.async_get_or_create(
        "light",
        "test",
        "standalone_light",
    )

    # Set states in state machine
    hass.states.async_set(e1.entity_id, "on")
    hass.states.async_set(e2.entity_id, "off")
    hass.states.async_set(e3.entity_id, "on")
    hass.states.async_set(e4.entity_id, "off")

    target_e1 = {"entity_id": e1.entity_id}
    info = render_to_info(
        hass,
        "{{ expand_target(target) | map(attribute='entity_id') | list }}",
        variables={"target": target_e1},
    )
    assert_result_info(info, [e1.entity_id], [e1.entity_id])

    # Filter syntax
    target_e1_e4 = {"entity_id": [e1.entity_id, e4.entity_id]}
    info = render_to_info(
        hass,
        "{{ target | expand_target | map(attribute='entity_id') | sort | list }}",
        variables={"target": target_e1_e4},
    )
    assert_result_info(
        info,
        sorted([e1.entity_id, e4.entity_id]),
        {e1.entity_id, e4.entity_id},
    )

    # Area targeting with primary_entities_only default (True) -> excludes e2 (config category)
    target_kitchen = {"area_id": area_kitchen.id}
    info = render_to_info(
        hass,
        "{{ expand_target(target) | map(attribute='entity_id') | list }}",
        variables={"target": target_kitchen},
    )
    assert_result_info(info, [e1.entity_id], [e1.entity_id])

    # Area targeting with primary_entities_only=False -> includes e2
    info = render_to_info(
        hass,
        "{{ expand_target(target, primary_entities_only=false) | map(attribute='entity_id') | sort | list }}",
        variables={"target": target_kitchen},
    )
    assert_result_info(
        info,
        sorted([e1.entity_id, e2.entity_id]),
        {e1.entity_id, e2.entity_id},
    )

    # Filter with primary_entities_only argument
    info = render_to_info(
        hass,
        "{{ target | expand_target(primary_entities_only=false) | map(attribute='entity_id') | sort | list }}",
        variables={"target": target_kitchen},
    )
    assert_result_info(
        info,
        sorted([e1.entity_id, e2.entity_id]),
        {e1.entity_id, e2.entity_id},
    )

    # Floor targeting (resolves kitchen area)
    target_floor = {"floor_id": floor.floor_id}
    info = render_to_info(
        hass,
        "{{ expand_target(target) | map(attribute='entity_id') | list }}",
        variables={"target": target_floor},
    )
    assert_result_info(info, [e1.entity_id], [e1.entity_id])

    # Device targeting
    target_device = {"device_id": device_living.id}
    info = render_to_info(
        hass,
        "{{ expand_target(target) | map(attribute='entity_id') | list }}",
        variables={"target": target_device},
    )
    assert_result_info(info, [e3.entity_id], [e3.entity_id])

    # Label targeting
    target_label = {"label_id": label.label_id}
    info = render_to_info(
        hass,
        "{{ expand_target(target) | map(attribute='entity_id') | list }}",
        variables={"target": target_label},
    )
    assert_result_info(info, [e3.entity_id], [e3.entity_id])

    # Exclude block targeting
    target_with_exclude = {
        "entity_id": [e1.entity_id, e3.entity_id],
        "exclude": {"entity_id": e1.entity_id},
    }
    info = render_to_info(
        hass,
        "{{ expand_target(target) | map(attribute='entity_id') | list }}",
        variables={"target": target_with_exclude},
    )
    assert_result_info(info, [e3.entity_id], [e3.entity_id])
