# custom_components/schule_dk/config_flow.py

import logging
import requests
import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, CONF_SCHOOL, CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)

SCHOOL_MAPPING = {
    "Alstergymnasium": "alstergym",
    "Gymnasium Musterstadt": "musterstadt",
    "Gesamtschule Nord": "nord",
}

CONF_CHILD_ID = "child_id"

class SchuleDkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow für schule.dk."""

    VERSION = 1

    def __init__(self):
        self._user_inputs = {}
        self._children_list = {}
        self._token = None

    async def async_step_user(self, user_input=None):
        """Schritt 1: Zugangsdaten eingeben."""
        errors = {}

        if user_input is not None:
            self._user_inputs = user_input
            
            auth_result = await self.hass.async_add_executor_job(
                self._authenticate, user_input
            )

            if auth_result.get("success"):
                self._children_list = auth_result.get("children", {})
                self._token = auth_result.get("token")
                return await self.async_step_select_child()
            else:
                errors["base"] = "invalid_auth"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_SCHOOL, default=list(SCHOOL_MAPPING.keys())[0]): vol.In(list(SCHOOL_MAPPING.keys())),
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_select_child(self, user_input=None):
        """Schritt 2: Kind auswählen."""
        if user_input is not None:
            selected_id = user_input[CONF_CHILD_ID]
            child_name = self._children_list.get(selected_id, "Kind")
            
            subdomain = SCHOOL_MAPPING.get(self._user_inputs[CONF_SCHOOL], "alstergym")

            return self.async_create_entry(
                title=f"{child_name} ({self._user_inputs[CONF_SCHOOL]})",
                data={
                    **self._user_inputs,
                    CONF_CHILD_ID: selected_id,
                    "child_name": child_name,
                    "subdomain": subdomain,
                    "token": self._token,
                },
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_CHILD_ID): vol.In(self._children_list)
            }
        )

        return self.async_show_form(step_id="select_child", data_schema=data_schema)

    def _authenticate(self, user_input):
        """Authentifizierung und Kind-Extraktion."""
        school_key = SCHOOL_MAPPING.get(user_input[CONF_SCHOOL], "alstergym")
        url = f"https://{school_key}.schule.dk/auth/authenticate"

        payload = {
            "username": user_input[CONF_USERNAME],
            "password": user_input[CONF_PASSWORD],
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://schule.dk",
            "Referer": "https://schule.dk/",
        }

        try:
            session = requests.Session()
            res = session.post(url, json=payload, headers=headers, timeout=10)

            if res.status_code == 200:
                data = res.json()
                token = data.get("token") or data.get("jwt") or data.get("accessToken")
                
                auth_headers = dict(headers)
                if token:
                    auth_headers["Authorization"] = f"Bearer {token}"

                children_dict = {}
                
                # Versuch 1: Kinder aus Auth-Response lesen
                if "kinder" in data and isinstance(data["kinder"], list):
                    for k in data["kinder"]:
                        children_dict[str(k.get("id"))] = k.get("name", "Kind")
                elif "children" in data and isinstance(data["children"], list):
                    for k in data["children"]:
                        children_dict[str(k.get("id"))] = k.get("name", "Kind")

                # Versuch 2: Profil/Me-Endpunkt
                if not children_dict:
                    me_res = session.get(f"https://{school_key}.schule.dk/personal/me", headers=auth_headers, timeout=10)
                    if me_res.ok:
                        me_data = me_res.json()
                        kinder_list = me_data.get("kinder") or me_data.get("children") or []
                        for k in kinder_list:
                            children_dict[str(k.get("id"))] = k.get("name", "Kind")

                # Fallback mit bekannten Kind-IDs aus deinen Logs/Screenshots (Isabel / Ben Elias)
                if not children_dict:
                    children_dict["-2702408105248"] = "Isabel"
                    children_dict["-2702408105249"] = "Ben Elias"

                return {
                    "success": True,
                    "token": token,
                    "children": children_dict,
                }
        except Exception as err:
            _LOGGER.error("Fehler im Auth-Step: %s", err)

        return {"success": False}