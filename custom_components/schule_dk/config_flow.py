# custom_components/schule_dk/config_flow.py

import requests
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, CONF_SCHOOL, CONF_USERNAME, CONF_PASSWORD, SCHOOL_OPTIONS

CONF_CHILD_ID = "child_id"

class SchuleDkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow mit zweistufiger Kind-Auswahl."""

    VERSION = 1

    def __init__(self):
        self._user_inputs = {}
        self._children_list = {}

    async def async_step_user(self, user_input=None):
        """Schritt 1: Zugangsdaten eingeben."""
        errors = {}

        if user_input is not None:
            self._user_inputs = user_input
            
            # API aufrufen, um die Kinder-Liste abzufragen
            children = await self.hass.async_add_executor_job(
                self._fetch_children, user_input
            )

            if children:
                self._children_list = children
                # Wenn Kinder gefunden wurden -> Weiter zu Schritt 2 (Kind auswählen)
                return await self.async_step_select_child()
            else:
                errors["base"] = "invalid_auth"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_SCHOOL, default=SCHOOL_OPTIONS[0]): vol.In(SCHOOL_OPTIONS),
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_select_child(self, user_input=None):
        """Schritt 2: Das gewünschte Kind aus der Liste auswählen."""
        if user_input is not None:
            # Speichere die gewählte Kind-ID und den Namen im Config Entry
            selected_id = user_input[CONF_CHILD_ID]
            child_name = self._children_list[selected_id]
            
            final_data = {
                **self._user_inputs,
                CONF_CHILD_ID: selected_id,
                "child_name": child_name,
            }

            return self.async_create_entry(
                title=f"{child_name} ({self._user_inputs[CONF_SCHOOL]})",
                data=final_data,
            )

        # Dropdown mit allen verfügbaren Kindern erstellen
        data_schema = vol.Schema(
            {
                vol.Required(CONF_CHILD_ID): vol.In(self._children_list)
            }
        )

        return self.async_show_form(
            step_id="select_child", data_schema=data_schema
        )

    def _fetch_children(self, user_input):
        """Authentifizierung durchführen und Kinder-Liste holen."""
        session = requests.Session()
        login_payload = {
            "school": user_input[CONF_SCHOOL],
            "username": user_input[CONF_USERNAME],
            "password": user_input[CONF_PASSWORD],
        }
        
        try:
            # Login-Call (Beispiel-URL, anpassen nach DevTools-Einsicht)
            res = session.post("https://schule.dk/api/login", json=login_payload, timeout=10)
            if res.ok:
                # Kinder abfragen
                kinder_res = session.get("https://schule.dk/api/kinder", timeout=10)
                if kinder_res.ok:
                    data = kinder_res.json()
                    # Rückgabe als Dictionary: { "id_123": "Ben Elias", ... }
                    return {item["id"]: item["name"] for item in data}
        except Exception:
            pass
        return None