from decipher.beacon import BeaconAPIException, FULLKEY
import requests
import time


def login(api, args):
    oldHost = 'v2.decipherinc.com'
    oldUsername = None

    try:
        key, oldHost, oldUsername = api._load(api.section)
    except KeyError:
        pass
    else:
        if not key.startswith('session '):
            print "You already have defined an API key for section %r." % api.section
            print "(You can use beacon -s section to define and use multiple keys and hosts)"
            if raw_input("Overwrite this key? Y/N ").lower() != 'y':
                return

    print "If you are using the Beacon API for automation, you should generate and enter"
    print " an API key. If you only need temporary access, to e.g. upload/download files"
    print " you can enter your username/password below"

    s = None
    while 1:
        print
        print "How do you want to authenticate?"
        print "1. Enter the %d-character API key (valid until deactivated)" % FULLKEY
        print "2. Enter your username/password (temporary login)"
        print "3. Enter a long code (visible on the API key page)"
        print "q. Quit"
        s = raw_input("Select 1, 2, 3 or q: ")
        if s not in '123q':
            print "Not a valid option. Select 1,2, 3, or q"
            continue
        if s == 'q':
            return
        break

    if s == '1':
        print """
    Enter your API key
    See https://decipher.zendesk.com/hc/en-us/articles/360010277813
        """

        key = None
        while 1:
            key = raw_input("API KEY: ")
            if len(key) != FULLKEY:
                print "An API key is exactly %d characters long" % FULLKEY
                print "If you lost your secret key part, you must rekey your key."
            else:
                break
    elif s == '2':
        print "Enter your full username (email address)",
        if oldUsername:
            print "(default %s)" % oldUsername
        else:
            print
        username = raw_input('Username: ') or oldUsername
        print "Enter your password"
        import getpass
        password = getpass.getpass("Password: ")
    elif s == '3':
        print
        print "Visit https://v2.decipherinc.com/apps/api/keys (or private server equivalent)"
        print "Select 'generate temporary key' then paste it below"
        print
        tkey = raw_input('Temporary Key: ')
        if len(tkey) % 3:
            tkey += '=' * (3-(len(tkey)%3))
        try:
            skey, fkey, host = tkey.decode('base64').split(';')
        except ValueError:
            print "Not a valid temporary key."
            return
        key = 'session 1234-%s %s' % (fkey, skey)

    if s != '3':
        print """Enter your host, or press Enter for the default %s""" % oldHost
        host = raw_input("Host: ") or oldHost
        if not host.startswith('http'):
            host = 'https://%s' % host

    print "Testing your new settings..."
    if s == '2':
        response = requests.request('GET', '%s/api/session' % host,  auth=(username, password), headers=api.headers, verify=True)
        if response.status_code != 200:
            print "Sorry, that username/password was not correct."
            return
        try:
            expires = int(response.cookies['HERMES_FKEY'].split('-')[1])
            key = 'session %s %s' % (response.cookies['HERMES_FKEY'], response.cookies['BEACON_LOGIN'])
        except KeyError:
            print "Could not login to %s. Are you sure this is a current Beacon server?" % host
            return
        print "Acquired a temporary session key. It will be expire after %d minutes of idle time." % (expires / 60)

    api.login(key, host)
    try:
        api.get('hello', name='Beacon')
    except BeaconAPIException, e:
        print "Could not use these settings. Error", e
        print "Settings NOT saved"
        return

    api._save(api.section, key, host)
    print "Looks good. Settings were saved to the file %s" % api.inifile




