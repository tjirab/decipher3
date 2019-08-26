import code
from functools import partial
import sys, readline
from decipher.beacon import BeaconAPIException

class RemoteInteractiveConsole(code.InteractiveConsole):
    def __init__(self, api, state):
        self.api, self.state = api, state
        code.InteractiveConsole.__init__(self)

    def runsource(self, source, filename="<input>", symbol="single"):
        try:
            code = self.compile(source, filename, symbol)
        except (OverflowError, SyntaxError, ValueError):
            self.showsyntaxerror(filename)
            return False

        if code is None:         return True
        if not source:           return False

        try:
            r = self.api(cond=source, state=self.state)
        except BeaconAPIException, e:
            print "ERROR", e
            return False

        print r['stdout'].rstrip()
        if self.state is None:
            print >> sys.stderr, "NOTE: reusing state=%s from now on" % r['state']
            self.state = r['state']
        return False





def eval(api, args):
    ":type api: decipher.beacon.BeaconAPI"
    args.pop(0)
    if not args:
        print >> sys.stderr, "Must supply survey path"
        return
    survey = args.pop(0)

    if args:
        state = args[0]
    else:
        print >> sys.stderr, "NOTE: using the last submitted state. Specify explicit state for live surveys."
        state = None

    c = RemoteInteractiveConsole(api = partial(api.post, "surveys/%s/evaluate" % survey), state=state)
    c.interact(banner="Using Decipher survey %s." % survey)




