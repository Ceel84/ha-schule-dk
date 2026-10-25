# custom_components/schule_dk/sensor.py

import logging
from datetime import timedelta
import requests

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity

from .const import DOMAIN, CONF_SCHOOL, CONF_USERNAME, CONF_PASSWORD

CONF_CHILD_ID = "child_id"
_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=30)

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = config_entry.data
    child_id = config.get(CONF_CHILD_ID)
    child_name = config.get("child_name", "Stundenplan")

    class SchuleDkApiClient:
        def __init__(self):
            self.session = requests.Session()

        def update(self):
            try:
                # 1. Login
                self.session.post(
                    "https://schule.dk/api/login",
                    json={
                        "school": config[CONF_SCHOOL],
                        "username": config[CONF_USERNAME],
                        "password": config[CONF_PASSWORD],
                    },
                    timeout=10,
                )
                
                # 2. Stundenplan gezielt für das ausgewählte Kind abrufen
                response = self.session.get(
                    f"https://schule.dk/api/klassenbuch?kid={child_id}",
                    timeout=10
                )
                if response.ok:
                    return response.json()
            except Exception as err:
                _LOGGER.error("Fehler beim Abruf von schule.dk: %s", err)
            return None

    api_client = SchuleDkApiClient()

    async def async_update_data():
        return await hass.async_add_executor_job(api_client.update)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"schule_dk_{child_id}",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()
    async_add_entities([SchuleDkStundenplanSensor(coordinator, config_entry, child_name)], True)


class SchuleDkStundenplanSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, config_entry, child_name):
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._child_name = child_name
        self._attr_name = f"Stundenplan {child_name}"
        self._attr_unique_id = f"schule_dk_{config_entry.data[CONF_CHILD_ID]}"
        self._attr_icon = "mdi:account-school"

    @property
    def state(self):
        return self._child_name

    @property
    def extra_state_attributes(self):
        return {
            "kind": self._child_name,
            "schule": self._config_entry.data[CONF_SCHOOL],
            "stundenplan": self.coordinator.data,
        }