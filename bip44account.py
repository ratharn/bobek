import sys

from twisted.python import log
from twisted.internet import reactor, defer

from bip32utils import BIP32Key
from treq import post, json_content

class BIP44Account(object):
    INSIGHT_API = "https://insight.bitpay.com"
    GAP_EXTERNAL = 20
    GAP_INTERNAL = 5

    def __init__(self, xpub):
        self.xpub = xpub
        acc_node = BIP32Key.fromExtendedKey(xpub)
        self.ext_node = acc_node.ChildKey(0)
        self.int_node = acc_node.ChildKey(1)

        self.ext_next_index = 0
        self.int_next_index = 0

        # Contains all known addresses for given account
        self.addrs = []

        # Contain unused addresses on external or internal chain
        # If any balance appears here, further discovery is triggered
        self.ext_unused = []
        self.int_unused = []

    def is_affected(self, changed_addrs):
        # Checks if changes on given addresses affect this account in any way
        if set(self.addrs).intersection(changed_addrs):
            return True
        return False

    @defer.inlineCallbacks
    def mark_used(self, used_addrs):
        # Mark given address as used and do partial discovery if needed
        affected = False

        if set(self.ext_unused).intersection(used_addrs):
            yield self.discover_external()
            affected = True

        if set(self.int_unused).intersection(used_addrs):
            yield self.discover_internal()
            affected = True

        defer.returnValue(affected)

    @defer.inlineCallbacks
    def discover(self):
        # Do initial account discovery
        yield self.discover_external()
        yield self.discover_internal()

    @defer.inlineCallbacks
    def discover_external(self):
        (next_index, used, unused) = yield self._discover_node(self.ext_node, self.GAP_EXTERNAL, initial=self.ext_next_index)
        self.addrs += used + unused
        self.ext_unused = unused
        self.ext_next_index = next_index

    @defer.inlineCallbacks
    def discover_internal(self):
        (next_index, used, unused) = yield self._discover_node(self.int_node, self.GAP_INTERNAL, initial=self.int_next_index)
        self.addrs += used + unused
        self.int_unused = unused
        self.int_next_index = next_index

    @defer.inlineCallbacks
    def _discover_node(self, node, gap, initial=0):
        # Returns 3-tuple of (next_index, used_addresses, unused_addresses)

        used = []
        addresses = []
        i = initial

        while True:
            addr_node = node.ChildKey(i)
            addresses.append(addr_node.Address())

            if i > 0 and i % gap == 0:
                total_items = yield self._get_total_items(addresses)

                if total_items == 0:
                    defer.returnValue((i + 1, used, addresses))
                else:
                    used += addresses
                    addresses = []

            i += 1
        
    @defer.inlineCallbacks
    def _get_total_items(self, addresses):
        data = yield post(self.INSIGHT_API + '/api/addrs/txs',
                          {'addrs': ','.join(addresses),
                           'from': 0,
                           'to': 0
                           })
        cont = yield json_content(data)
        defer.returnValue(cont['totalItems'])

@defer.inlineCallbacks
def main():
    log.startLogging(sys.stdout)

    account = BIP44Account('xpub6BhPoCyVJgAh9YHxKfu46kGtq6iGetbLwCuTbVAuMusQreM21nEGiiB3TDfqfhu92seYnWTRhdXhrmsChrZdPfUh7VAm6tryfBvYdMWgsCp')

    import time
    start = time.time()

    yield account.discover()

    print "addresses", account.addrs
    print "UNUSED", account.ext_unused, account.int_unused

    affected = yield account.mark_used(['15wJeYZfhg1XiAcGvoLyTAvgTHQ2Ee4FuH'])
    print "NEW DISCOVERY?", affected
    print "UNUSED", account.ext_unused, account.int_unused

    affected = yield account.mark_used(['15wJeYZfhg1XiAcGvoLyTAvgTHQ2Ee4FuH'])
    print "NEW DISCOVERY?", affected
    print "UNUSED", account.ext_unused, account.int_unused

    print time.time() - start

if __name__ == '__main__':
    main()
    reactor.run()
