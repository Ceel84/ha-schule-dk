# custom_components/schule_dk/sensor.py

import logging
from datetime import timedelta
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity

from .const import DOMAIN, CONF_SCHOOL, CONF_USERNAME, CONF_PASSWORD

CONF_CHILD_ID = "child_id"
_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=15)

async def async_setup_entry(hass, config_entry, async_add_entities):
    config = config_entry.data
    child_id = config.get(CONF_CHILD_ID)
    child_name = config.get("child_name", "Stundenplan")
    subdomain = config.get("subdomain", "alstergym")

    class SchuleDkApiClient:
        def __init__(self):
            self.session = requests.Session()
            
            # Retry-Strategie bei Verbindungsabbrüchen
            retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
            adapter = HTTPAdapter(max_retries=retries)
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)

            # Echte Browser-Header mitsenden
            self.headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
                "Origin": "https://schule.dk",
                "Referer": "https://schule.dk/",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "Connection": "keep-alive",
            }

        def fetch_plan(self):
            try:
                # 1. Login durchführen
                login_url = f"https://{subdomain}.schule.dk/auth/authenticate"
                login_payload = {
                    "username": config[CONF_USERNAME],
                    "password": config[CONF_PASSWORD],
                }
                
                res = self.session.post(login_url, json=login_payload, headers=self.headers, timeout=15)
                
                if not res.ok:
                    _LOGGER.error("Login fehlgeschlagen! Status: %s, Antwort: %s", res.status_code, res.text)
                    return None

                data = res.json()
                token = data.get("token") or data.get("jwt") or data.get("accessToken")
                if token:
                    self.headers["Authorization"] = f"Bearer {token}"

                # 2. Stundenplan / Vertretungsplan abrufen
                url_w1 = f"https://{subdomain}.schule.dk/personal/module/plan/vertretungsplan?kind={child_id}&offset=0"
                url_w2 = f"https://{subdomain}.schule.dk/personal/module/plan/vertretungsplan?kind={child_id}&offset=1"

                res_w1 = self.session.get(url_w1, headers=self.headers, timeout=15)
                res_w2 = self.session.get(url_w2, headers=self.headers, timeout=15)

                json_w1 = res_w1.json() if res_w1.ok else {}
                json_w2 = res_w2.json() if res_w2.ok else {}

                return {
                    "woche_aktuell": self._parse_schule_dk_json(json_w1, child_name),
                    "woche_naechste": self._parse_schule_dk_json(json_w2, child_name),
                    "raw_w1": json_w1,
                }

            except Exception as err:
                _LOGGER.error("Ausnahme beim Abruf des Stundenplans für %s: %s", child_name, err)
                return None

        def _parse_schule_dk_json(self, raw_data, child_name):
            """Liest das schule.dk Objekt-Format aus und loggt die Struktur."""
            stundenplan_woche = []
            
            if not isinstance(raw_data, dict):
                _LOGGER.warning("[%s] raw_data ist kein Dictionary, sondern: %s", child_name, type(raw_data))
                return stundenplan_woche

            _LOGGER.info("[%s] API Schlüssel vorhanden: %s", child_name, list(raw_data.keys()))

            wochen_liste = raw_data.get("wochen", [])
            _LOGGER.info("[%s] Anzahl Wochen in API-Antwort: %s", child_name, len(wochen_liste))

            for woche in wochen_liste:
                tage_liste = woche.get("tage", [])
                _LOGGER.info("[%s] Gefundene Tage in Woche: %s", child_name, len(tage_liste))
                for tag in tage_liste:
                    datum = tag.get("datum", "")
                    units = tag.get("units", [])
                    
                    tages_eintraege = []
                    for stunden_index, unit in enumerate(units, start=1):
                        lines = unit.get("lines", [])
                        for line in lines:
                            text = line.get("text", "").strip()
                            if text:
                                tages_eintraege.append({
                                    "stunde": stunden_index,
                                    "text": text,
                                    "typ": line.get("type", "stunde"),
                                })

                    if tages_eintraege:
                        stundenplan_woche.append({
                            "datum": datum,
                            "heute": tag.get("heute", False),
                            "eintraege": tages_eintraege,
                        })

            return stundenplan_woche

    api_client = SchuleDkApiClient()

    async def async_update_data():
        return await hass.async_add_executor_job(api_client.fetch_plan)

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
        data = self.coordinator.data or {}
        if data.get("woche_aktuell") or data.get("raw_w1"):
            return "Aktiv"
        return "Keine Daten"

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {
            "kind": self._child_name,
            "schule": self._config_entry.data[CONF_SCHOOL],
            "diese_woche": data.get("woche_aktuell"),
            "naechste_woche": data.get("woche_naechste"),
            "raw_w1": data.get("raw_w1"),
        }