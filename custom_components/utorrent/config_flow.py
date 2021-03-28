import requests
import base64
import json
from lxml import html

from aiohttp import ClientSession


class LoginResponse:
    """"
    status: ok
    status: error
       errors: [captcha.required]
       captcha_image_url: XXX
    status: error
       errors: [account.not_found]
       errors: [password.not_matched]
    """

    def __init__(self, resp):
        print(resp)
        self.raw = resp

    @property
    def ok(self):
        return self.raw == '200'

    @property
    def error(self):
        return self.raw


class StatusInfo:
    def __init__(self, data):
        mask = 1
        self.started = (data & mask) != 0
        mask *= 2
        self.checking = (data & mask) != 0
        mask *= 2
        self.start_after_check = (data & mask) != 0
        mask *= 2
        self.checked = (data & mask) != 0
        mask *= 2
        self.error = (data & mask) != 0
        mask *= 2
        self.paused = (data & mask) != 0
        mask *= 2
        self.queued = (data & mask) != 0
        mask *= 2
        self.loaded = (data & mask) != 0
        mask *= 2

class TorrentInfo:
    def __init__(self, data):
        ind = 0
        self.hash = data[0]
        self.status = StatusInfo(data[1])
        self.name = data[2]
        self.size = data[3] # in bytes
        self.percent_progress = data[4] # in mils
        self.downloaded = data[5] # in bytes
        self.uploaded = data[6] # in bytes
        self.ratio = data[7] # in mils
        self.upload_speed = data[8] # in bytes per second
        self.download_speed = data[9] # in bytes per second
        self.eta = data[10] # in seconds
        self.label = data[11]
        self.peers_connected = data[12]
        self.peers_in_swarm = data[13]
        self.seeds_connected = data[14]
        self.seeds_in_swarm = data[15]
        self.availability = data[16] # int in 1/65535
        self.torrent_queue_order = data[17]
        self.remaining = data[18] # in bytes

class LabelInfo:
    def __init__(self, data):
        self.label = data[0]
        self.torrents_in_label = data[1]

class TorrentListInfo:
    def __init__(self, data):
        self.build = data['build']
        self.labels = [LabelInfo(x) for x in data['label']]
        self.torrents = [TorrentInfo(x) for x in data['torrents']]
        self.torrent_cache_id = data['torrentc']


class UTorrentAPI(object):

    base_url = None
    port = '35653'
    username = None
    password = None
    auth     = None
    token = None
    cookies  = None


    def __init__(self, session):
        self.session = session
        self._update_torrent_list = []

    async def login_user(self, base_url, username, password, port = None):
        self.base_url = 'http://' + base_url + ':' + (port if port else self.port) + '/gui'
        if port:
            self.port = port
        self.username = username
        self.password = password
        self.auth     = await requests.auth.HTTPBasicAuth(self.username, self.password)
        self.token, self.cookies = await self._get_token()
        return self._action('list=1')[0]


    async def login_cookies(self, cookies, token):
        self.token = token
        self.cookies = cookies
        return self._action('list=1')[0]

    async def _get_token(self):
        url = self.base_url + '/token.html'

        token    = -1
        cookies  = -1

        try:
            response = await requests.get(url, auth=self.auth)

            token = -1

            if response.status_code == 200:
                xtree = html.fromstring(response.content)
                token = xtree.xpath('//*[@id="token"]/text()')[0]
                guid  = response.cookies['GUID']
            else:
                token = -1

            cookies = dict(GUID = guid)

        except requests.ConnectionError as error:
            token = 0
            cookies = 0
            print(error)
        except:
            print('error')

        return token, cookies

    def is_online(self):
        if self.token != -1 and self.token != 0:
            return True
        else:
            return False

# public sectin -->
    async def get_list(self):
        torrents = []
        try:
            status, response = self._action('list=1')
            if status.ok():
                torrents = response.json()
            else:
                print(status)

        except requests.ConnectionError as error:
            print(error)
        except:
            print('error')

        return torrents

    async def get_files(self, torrentid):
        path = 'action=getfiles&hash=%s' % (torrentid)
        status, response = self._action(path)

        files = []

        if status.ok():
            files = response.json()
        else:
            print(status)

        return files

    async def start(self, torrentid):
        return self._torrentaction('start', torrentid)

    async def stop(self, torrentid):
        return self._torrentaction('stop', torrentid)

    async def pause(self, torrentid):
        return self._torrentaction('pause', torrentid)

    async def forcestart(self, torrentid):
        return self._torrentaction('forcestart', torrentid)

    async def unpause(self, torrentid):
        return self._torrentaction('unpause', torrentid)

    async def recheck(self, torrentid):
        return self._torrentaction('recheck', torrentid)

    async def remove(self, torrentid):
        return self._torrentaction('remove', torrentid)

    async def removedata(self, torrentid):
        return self._torrentaction('removedata', torrentid)

    async def recheck(self, torrentid):
        return self._torrentaction('recheck', torrentid)

    async def set_priority(self, torrentid, fileindex, priority):
        # 0 = Don't Download
        # 1 = Low Priority
        # 2 = Normal Priority
        # 3 = High Priority
        path = 'action=%s&hash=%s&p=%s&f=%s' % ('setprio', torrentid, priority, fileindex)
        status, response = self._action(path)

        files = []

        if status.ok():
            files = response.json()
        else:
            print(status)

        return files

    async def add_file(self, file_path):

        file = []

        url = '%s/?%s&token=%s' % (self.base_url, 'action=add-file', self.token)
        headers = {
        'Content-Type': "multipart/form-data"
        }

        files = {'torrent_file': open(file_path, 'rb')}

        try:
            if files:
                response = await requests.post(url, files=files, auth=self.auth, cookies=self.cookies)
                if response.status_code == 200:
                    file = response.json()
                    print('file added')
                else:
                    print(response.status_code)
            else:
                print('file not found')

            pass
        except requests.ConnectionError as error:
            print(error)
        except Exception as e:
            print(e)

        return file

    async def add_url(self, fiel_path):
        path = 'action=add-url&s=%s' % (fiel_path)
        status, response = self._action(path)

        files = []

        try:
            if status.ok():
                files = response.json()
            else:
                print(response.status_code)

            pass
        except requests.ConnectionError as error:
            print(error)
        except Exception as e:
            print(e)

        return files

    def add_update_torrent_list(self, coro):
        """Listeners to handle automatic cookies update."""
        self._update_torrent_list.append(coro)

# private section -->
    async def _torrentaction(self, action, torrentid):
        path = 'action=%s&hash=%s' % (action, torrentid)

        files = []

        try:
            status, response = self._action(path)

            if status.ok():
                files = response.json()
            else:
                print(response.status_code)

        except requests.ConnectionError as error:
            print(error)
        except:
            print('error')

        return files

    async def _action(self, path):
        response = None
        url = '%s/?%s&token=%s' % (self.base_url, path, self.token)
        headers = {
        'Content-Type': "application/json"
        }
        try:
            response = await requests.get(url, auth=self.auth, cookies=self.cookies, headers=headers)
            # use utf8 for multi-language
            # default is ISO-8859-1
            response.encoding = 'utf8'
        except requests.ConnectionError as error:
            print(error)
        except:
            pass
        return LoginResponse(response.status_code), response

    async def _handle_update(self):
        for coro in self._update_torrent_list:
            await coro(token=self.token
                       cookie=self.cookie)
