import csv
import sys
import re
from decipher.beacon import BeaconAPIException


def replace(s, env):
    return re.sub("%(\w+)", lambda m: env.get(m.group(1), ""), s)

def batch(api, args, env, batchfile):
    usage = env["usage"]
    decode = env["decode"]
    fatal = env["fatal"]

    try:
        (verb, resource), rest = args[:2], args[2:]
    except ValueError:
        return usage("too few parameters")

    try:
        records = list(csv.DictReader(open(batchfile), delimiter="\t", quotechar='"'))
    except IOError, err:
        return fatal("Could not open batch file %s", err)

    verb = verb.lower()
    if verb not in ('get', 'put', 'post', 'delete'):
        return usage('invalid verb %r' % verb)

    try:
        args = dict(x.split('=', 1) for x in rest)
    except ValueError:
        print >> sys.stderr, "Unexpected argument format; arguments must have key=value format"
        raise SystemExit(1)

    method = getattr(api, verb)

    for index, record in enumerate(records):
        nargs = {k: replace(v, record) for k,v in args.items()}
        if verb != 'get':
            nargs = {k: decode(k, v) for k, v in nargs.items()}
        nargs = {k:v for k,v in nargs.items() if v != ""}
        nresource = replace(resource, record)
        try:
            res = method(nresource, **nargs)
            print >> sys.stderr, "%d: OK" % (index+1)
        except BeaconAPIException, err:
            print >> sys.stderr, "%d: ERROR: %s" % (index+1, err)
