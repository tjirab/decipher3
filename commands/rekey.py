import sys
from decipher.beacon import BeaconAPIException


def rekey(api, args):
    ":type api: BeaconAPI"
    try:
        api._ensureKey()
        if api.keySource != 'ini':
            print >> sys.stderr, "Your beacon keys must be stored on the config file for this to be possible"
            print >> sys.stderr, "Your current storage method is %r" % api.keySource
            return 1

        print "Rekeying..."
        api.rekey()

    except BeaconAPIException, e:
        print >> sys.stderr, "ERROR: %s" % e
    else:
        print "Complete. New secret key saved."
