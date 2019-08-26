#!/usr/bin/env python
"""
Decipher Beacon 2.0 API access library
"""

# The API version we'll be accessing
from configparser import RawConfigParser, NoSectionError, DuplicateSectionError, NoOptionError
from functools import partial
import hmac
import json
import os, requests
import pwd
import datetime
import pkg_resources
import sys, time

KEYLEN = 32 # per part
FULLKEY = KEYLEN * 2
DEFAULT_HOST = "v2.decipherinc.com"

def date_to_isoformat(o):
    # convert local timestap to iso8601 format
    return time.strftime("%FT%TZ", time.gmtime(int(o.strftime("%s"))))

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return date_to_isoformat(o)


class BeaconAPIException(Exception):
    def __init__(self, code, message, body=None):
        assert isinstance(code, int)
        self.code, self.message, self.body = code, message, body
        Exception.__init__(self, "%s: %s" % (code, message))

class BeaconAPI(object):
    verbose = xml = False
    version = 'v1'
    section = 'main'    # name of section in INI file we are using
    keySource = None
    timeout = None
    verifySSL = True
    impersonate = None

    def __init__(self, host=None, key=None, retry=None):
        self.host, self.key = host, key
        self.session = requests.Session()
        self.session.verify = self.verifySSL
        if retry is not None:
            from requests.packages.urllib3.util.retry import Retry
            from requests.adapters import HTTPAdapter
            retry = Retry(total=retry, read=retry, connect=retry,
                          backoff_factor=1.0,
                          status_forcelist=(500, 502, 503, 504),
                          method_whitelist=('POST',))
            adapter = HTTPAdapter(max_retries=retry)
            self.session.mount('https://', adapter)
            self.session.mount('http://', adapter)

    def _debug(self, what):
        if self.verbose:
            print(what, file=sys.stderr)


    def login(self, key, host=DEFAULT_HOST):
        """
        Set the API key and optionally the API host.
        :param key: a 32-characters long retrieved from your API keys page
        :param host: optional; uses v2.decipherinc.com if not specified
        :return:
        """
        if not key.startswith('session '):
            assert len(key) == FULLKEY, "API key specified is not exactly %d characters long" % FULLKEY
        self.key, self.host  = key, host

    @property
    def inifile(self):
        DIR = os.path.expanduser("~/.config")
        try:            os.makedirs(DIR)
        except OSError: pass
        return DIR + '/decipher'

    @property
    def parser(self):
        parser = RawConfigParser()
        parser.read(self.inifile)
        return parser

    @property
    def headers(self):
        return {"x-requested-with" : "decipher.beacon %s" % pkg_resources.require("decipher")[0].version }


    def _load(self, section):
        "attempt to load key data from ~/.config/decipher file"
        parser = self.parser
        try:
            key = parser.get(section, 'key')
            host = parser.get(section, 'host')
            try:
                username = parser.get(section, 'username')
            except NoOptionError:
                username = None
        except NoSectionError:
            raise KeyError
        return key, host, username

    def _save(self, section, key, host, username=None):
        parser = self.parser
        try:
            parser.add_section(section)
        except DuplicateSectionError:
            pass
        parser.set(section, "key", key)
        parser.set(section, "host", host)
        if username:
            parser.set(section, "username", username)
        parser.write(open(self.inifile, "w"))
        os.chmod(self.inifile, 0o600)


    def _ensureKey(self):
        "Ensure key / host are configured"
        if self.host is None:
            if 'BEACON_KEY' in os.environ:
                self._debug("+ BEACON_KEY set, using environment key")
                self.key = os.environ['BEACON_KEY']
                self.host = os.environ.get('BEACON_HOST') or 'v2.decipherinc.com'
                if not self.host.startswith('http'):
                    self.host = 'https://%s' % self.host
                self.keySource = 'environment'

            # BEACON_KEY & BEACON_HOST specified?
            elif 'HERMES2_HOME' in os.environ or os.path.isdir("/home/jaminb/v2"):
                home = os.environ['HERMES2_HOME'] = os.environ.get('HERMES2_HOME', '/home/jaminb/v2')
                self._debug("+ HERMES2_HOME set, trying to call v2conf")
                try:
                    ekey, self.host = list(map(str.strip, os.popen("%s/scripts/v2conf.py localapi localurl" % home).readlines()))
                except ValueError:
                    raise BeaconAPIException(500, "Could not call v2conf to determine local API key")
                self._debug('+ v2conf response: %r / %r' % (ekey, self.host))
                if len(ekey) != 64:
                    raise BeaconAPIException(500, "Invalid local API key")

                # convert key to API key
                username = pwd.getpwuid(os.getuid()).pw_name
                self.key = 'local %s %s' % (username, hmac.new(ekey, username).hexdigest())
                self.keySource = 'local'
            else:
                self._debug("+ Environment unset, using INI file section %s" % self.section)
                try:
                    self.key, self.host, _ = self._load(self.section)
                except KeyError:
                    raise BeaconAPIException(code=500, message="No key has been defined in environment. Either use 'beacon login' or set BEACON_KEY and optionally BEACON_HOST")
                self.keySource = 'ini'

    @property
    def publicPart(self):
        return self.key[:32]

    def rekey(self):
        "Ask for a new secret key and save it"
        if self.keySource != 'ini':
            raise BeaconAPIException(code=500, message="Rekeying can only be done if your API key came from the INI file (not %s)" % self.keySource)
        r = self.post('rh/apikeys/%s' % self.publicPart)
        self._save(self.section, self.publicPart + r['secret'], self.host)


    @property
    def _requestAuthHeaders(self):
        if self.key.startswith('session '):
            _, formkey, rest = self.key.split()
            d = {"x-apikey" : 'session %s' % formkey, "Cookie" : 'BEACON_LOGIN="%s"' % rest}
        else:
            d = {"x-apikey" : self.key}
        if self.impersonate:
            d['x-impersonate'] = self.impersonate
        return d

    def do(self, action, name, args, asynchronous=False):
        "Perform action"
        if args.pop('__meta', None):
            return (dict(
                api = '/api/%s/%s' % (self.version, name),
                method = action.upper(),
                args = args
            ))

        self._ensureKey()
        url = '%s/api/%s/%s' % (self.host, self.version, name)
        self._debug('> %s %s' % (action.upper(), url))

        kw = {}
        if action == 'get':
            body = kw['params'] = args
        else:
            body = kw['data'] = json.dumps(args, indent=1,cls=JSONEncoder)
        if self.timeout: kw['timeout'] = self.timeout


        headers = {'content-type': 'application/json'}
        headers.update(self._requestAuthHeaders)
        for k,v in list(self._requestAuthHeaders.items()):
            self._debug('>> %s: %s' % (k, v))
        if body:
            self._debug("\n%s\n" % body)

        if self.xml:
            headers['accept'] = 'application/xml'
        kw['verify'] = self.verifySSL

        headers.update(self.headers)
        if asynchronous:
            import grequests
            return grequests.AsyncRequest(action, url, headers=headers, **kw)

        try:
            r = self.session.request(action, url, headers=headers, **kw)
        except requests.ConnectionError as e:
            raise BeaconAPIException(code=500, message="Could not connect to server (%s): %s" % (url, e))
        self._debug('<< %s %s' % (r.status_code, r.reason))
        if 'x-typehint' in r.headers:
            self._debug('< x-typehint: %s' % r.headers['x-typehint'])
        if r.status_code != 200:
            raise BeaconAPIException(code=r.status_code, message=r.reason, body=r.content)
        if r.headers['content-type'] == 'application/json':
            return r.json()
        return r.content

    def get(self, _name, **args):      return self.do('get', _name, args)
    def post(self, _name, **args):     return self.do('post', _name, args)
    def put(self, _name, **args):      return self.do('put', _name, args)
    def delete(self, _name, **args):   return self.do('delete', _name, args)


api = BeaconAPI()
