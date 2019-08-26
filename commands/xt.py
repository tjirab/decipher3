import sys
from decipher.beacon import BeaconAPIException


def U(s, char='-'):
    s = s[:72]
    print s
    print char * len(s)
UU = lambda s: U(s, '=')

def xt(api, args):
    ":type api: BeaconAPI"
    args.pop(0)
    if not args:
        print >> sys.stderr, "Must supply survey path"
        return

    survey = args.pop(0)
    segmentList = filters = None
    tables = []

    if args:
        segmentList = [dict(cond=x) for x in args.pop(0).split(',')]
    if args:
        filters = args.pop(0).split(',')
    if args:
        tables = args.pop(0).split(',')

    try:
        r = Struct.fromNested(api.post('surveys/%s/crosstabs/execute' % survey, segments=segmentList, filters=filters, tables=tables))
    except BeaconAPIException, e:
        print >> sys.stderr, e
        return

    print "Segments"
    print "--------"
    stitles = []
    useTitle = max(len(s['title'] or '*') for s in r.segments) <= 10
    for i, s in enumerate(r.segments):
        if useTitle:
            stitles.append('{:^10}'.format(s.get('title') or '*'))
        else:
            stitles.append('#%d' % (i+1))
        print " %3s %-40s (%d)" % (stitles[-1], s.title, s.count)
    print

    W = sys.stdout.write

    def segments(l, us=False, title=""):
        W("%-25.25s" % title)
        for x in l:
            W("%10.10s " % x)
        W("\n")
        if us:
            segments(["-" * 10] * len(l), False, "")

    lastq = None
    for t in r.objects:
        if t.qlabel != lastq:
            UU("[%s] %s" % (t.qlabel, t.title))
            lastq = t.qlabel
        if t.subtitle:
            U("[%s] %s" % (t.get('obj', '').split(',')[-1], t.subtitle))

        segments(stitles, True, "")

        for r, data in zip(t.rows, t.data):
            if r.type != 'numeric':
                segments(("%8d" % x[1] for x in data), title=r.title)
                if r.get('pct', -1) != None:
                    segments(("%8.0f%%" % round(x[0],0) for x in data), title='')
                print
            else:
                segments(("%8.2f" % x[0] for x in data), title=r.title)
                print

            if r.intent == 'total':
                print
        print




class Struct(dict):
    "A class that can e initialized with a keyword list"
    def __init__(self, **entries):
        self.update(entries)
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError, name

    def __setattr__(self, name, value):
        self[name] = value

    def __hash__(self):
        return id(self)

    @classmethod
    def fromNested(cls, d):
        "Create from a nested dictionary which may have other dicts to convert as keys"
        if isinstance(d, dict):
            return cls(**{k: cls.fromNested(v) for k,v in d.items()})
        elif isinstance(d, (list, tuple)):
            return map(cls.fromNested, d)
        else:
            return d
