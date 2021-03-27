"""
1. User can enter host, port, username, password from GUI
2. User can set host, port, username, password in YAML
5. If authorization through YAML does not work, user can continue it through
   the GUI.
"""
import logging
from functools import lru_cache

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from . import DOMAIN
from .core.utorrent import ListTorrent, LoginResponse

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema({
    vol.Required('host'): str,
    vol.Required('port'): str,
    vol.Required('username'): str,
    vol.Required('password'): str,
})



class YandexStationFlowHandler(ConfigFlow, domain=DOMAIN):
    @property
    @lru_cache()
    def utorrent(self):
        session = async_create_clientsession(self.hass)
        return ListTorrent(session)

    async def async_step_import(self, data: dict):
        """Init by component setup. Forward YAML login/pass to auth."""
        await self.async_set_unique_id(data['username'])
        self._abort_if_unique_id_configured()

        
        else:
            return await self.async_step_auth(data)

    async def async_step_user(self, user_input=None):
        """Init by user via GUI"""
        if user_input is None:
            return self.async_show_form(
                step_id='user',
                data_schema=vol.Schema({
                    vol.Required('method', default='auth'): vol.In({
                        'auth': "Логин, пароль или одноразовый ключ",
                        'cookies': "Cookies",
                        'token': "Токен"
                    })
                })
            )

        method = user_input['method']
        if method == 'auth':
            return self.async_show_form(
                step_id=method, data_schema=AUTH_SCHEMA
            )
        else:  # cookies, token
            return self.async_show_form(
                step_id=method, data_schema=vol.Schema({
                    vol.Required(method): str,
                })
            )

    async def async_step_auth(self, user_input):
        """User submited username and password. Or YAML error."""
        resp = await self.utorrent.login_username(user_input['host'],
                                                  user_input['port'],
                                                  user_input['username'],
                                                  user_input['password'])
        return await self._check_utorrent_response(resp)

    async def async_step_cookies(self, user_input):
        resp = await self.utorrent.login_cookies(user_input['cookies'])
        return await self._check_utorrent_response(resp)

    async def async_step_external(self, user_input):
        return await self.async_step_auth(user_input)

    async def _check_utorrent_response(self, resp: LoginResponse):
        """Check Utorrent response. Do not create entry for the same login. Show
        captcha form if captcha required. Show auth form with error if error.
        """
        if resp.ok:
            # set unique_id or return existing entry
            entry = await self.async_set_unique_id(resp.display_login)
            if entry:
                # update existing entry with same login
                self.hass.config_entries.async_update_entry(
                    entry,
                    ()
                )
                return self.async_abort(reason='account_updated')

            else:
                # create new entry for new login
                return self.async_create_entry(
                    title=resp.display_login,
                    )

        
        elif resp.error:
            _LOGGER.debug(f"Config error: {resp.error}")
            return self.async_show_form(
                step_id='auth',
                data_schema=AUTH_SCHEMA,
                errors={'base': resp.error}
            )

        raise NotImplemented
