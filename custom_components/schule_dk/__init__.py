# custom_components/schule_dk/__init__.py

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setzt schule.dk über einen Konfigurationseintrag auf."""
    _LOGGER.info("=== SCHULE.DK: Setup Entry gestartet für Eintrag ID: %s ===", entry.entry_id)
    
    hass.data.setdefault(DOMAIN, {})

    # Korrigiert: async_forward_entry_setups mit 'async_' am Anfang
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Entlädt die Integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)