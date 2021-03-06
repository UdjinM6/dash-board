from firebase import firebase
import subprocess
import json
import datetime
import requests
import config

CONFIG_FILE_PATH = "/root/firebase/init/config.ini"


def chunks(s, n):
    for start in range(0, len(s), n):
        yield s[start:start+n]


def get_price_cryptsy(request, market):
    try:
        v = float(request["return"]["markets"][market]["lasttradeprice"])
        return v
    except KeyError:
        return None


def get_price_bittrex(request, market):
    try:
        v = float(request["result"]["Last"])
        return v
    except KeyError:
        return None


def get_price_bitfinex(request, market):
    try:
        v = float(request["last_price"])
        return v
    except KeyError:
        return None


def get_price_btce(request, market):
    try:
        v = float(request[market]["last"])
        return v
    except KeyError:
        return None


def get_price_bitstamp(request, market):
    try:
        v = float(request["last"])
        return v
    except KeyError:
        return None


def main():
    appconfig = config.getConfiguration(CONFIG_FILE_PATH)
    if appconfig is None:
        message = "Error parsing config file"
        raise Exception(message)

    print appconfig
    required_config_keys = ['firebase']
    for key in required_config_keys:
        if key not in appconfig:
            message = "*** ERROR: key \'%s\' is required" % key
            raise Exception(message)

    a = firebase.FirebaseAuthentication(appconfig['firebase']['token'], "mjsrs@sapo.pt")
    f = firebase.FirebaseApplication(appconfig['firebase']['url'], a)

    #run dash-cli getmininginfo
    #dashd should already been started
    getmininginfo = subprocess.check_output(["dash-cli", "getmininginfo"])
    getmininginfo = json.loads(getmininginfo)
    print getmininginfo

    #run dash-cli masternode count
    masternodecount = subprocess.check_output(["dash-cli", "masternode", "count"])
    print "masternode: %s" % masternodecount

    #update firebase values
    f.put("", "masternodecount", masternodecount)
    f.put("", "lastblock", getmininginfo["blocks"])
    f.put("", "difficulty", round(getmininginfo["difficulty"], 2))
    hashrate = round(float(getmininginfo["networkhashps"])/1000000000, 2)
    f.put("", "hashrate", hashrate)

    #run dash-cli spork show
    spork = subprocess.check_output(["dash-cli", "spork", "show"])
    spork = json.loads(spork)
    payment_enforcement = "On"
    unix_time_now = datetime.datetime.utcnow()
    unix_time_now = unix_time_now.strftime("%s")
    print "unix_time_now: %s" % unix_time_now
    print "SPORK_1_MASTERNODE_PAYMENTS_ENFORCEMENT: %s" % spork["SPORK_1_MASTERNODE_PAYMENTS_ENFORCEMENT"]

    #check if masternode payments enforcement is enabled
    if int(spork["SPORK_1_MASTERNODE_PAYMENTS_ENFORCEMENT"]) > int(unix_time_now):
        payment_enforcement = "Off"

    #update firebase values
    f.put("", "enforcement", payment_enforcement)
    #timestamp is given by firebase server
    f.put("", "timestamp", {".sv": "timestamp"})

    #get average DASH-BTC from cryptsy, bittrex and bitfinex
    DashBtc = {
        'cryptsy': {'url': 'http://pubapi2.cryptsy.com/api.php?method=singlemarketdata&marketid=155', 'fn_price': get_price_cryptsy, 'marketSymbol': 'DRK'},
        'bittrex':  {'url': 'https://bittrex.com/api/v1.1/public/getticker?market=btc-dash', 'fn_price': get_price_bittrex, 'marketSymbol': 'DRK'},
        'bitfinex': {'url':  'https://api.bitfinex.com/v1/pubticker/DRKBTC', 'fn_price': get_price_bitfinex, 'marketSymbol': 'DRK'}
        }

    avg_price_dashbtc = []
    for key, value in DashBtc.iteritems():
        try:
            r = requests.get(value['url'])
            output = json.loads(r.text)
            price = value['fn_price'](output, value['marketSymbol'])
            if price is not None:
                avg_price_dashbtc.append(price)
        except requests.exceptions.RequestException as e:
            print e

    DASHBTC = reduce(lambda x, y: x+y, avg_price_dashbtc)/len(avg_price_dashbtc)
    print avg_price_dashbtc
    print "AVG DASHBTC: %s" % round(DASHBTC, 8)
    f.put("", "priceBTC", round(DASHBTC, 8))

    #get average BTC-USD from btce, bitstamp, bitfinex
    BtcUsd = {
        'btce': {'url': 'https://btc-e.com/api/3/ticker/btc_usd', 'fn_price': get_price_btce, 'marketSymbol': 'btc_usd'},
        'bitstamp': {'url': 'https://www.bitstamp.net/api/ticker/', 'fn_price': get_price_bitstamp, 'marketSymbol': 'BTCUSD'},
        'bitfinex': {'url': 'https://api.bitfinex.com/v1/pubticker/BTCUSD', 'fn_price': get_price_bitfinex, 'marketSymbol': 'BTCUSD'},
    }
    avg_price_btcusd = []
    for key, value in BtcUsd.iteritems():
        try:
            r = requests.get(value['url'])
            output = json.loads(r.text)
            price = value['fn_price'](output, value['marketSymbol'])
            if price is not None:
                avg_price_btcusd.append(price)
        except requests.exceptions.RequestException as e:
            print e

    BTCUSD = reduce(lambda x, y: x+y, avg_price_btcusd)/len(avg_price_btcusd)
    print avg_price_btcusd
    print "AVG BTCUSD: %s" % round(BTCUSD, 8)
    DASHUSD = "$%s" % round(float(BTCUSD * DASHBTC), 2)
    print "DASHUSD: %s" % DASHUSD
    f.put("", "price", DASHUSD)

    #get total coins supply from Chainz
    try:
        r = requests.get("http://chainz.cryptoid.info/dash/api.dws?q=totalcoins")
        int_total_coins = r.text.split(".")[0]
        inv_total_coins = int_total_coins[::-1]
        availablesupply = ",".join(chunks(inv_total_coins, 3))[::-1]
        print "Available supply: %s" % availablesupply
        f.put("", "availablesupply", availablesupply)
    except requests.exceptions.RequestException as e:
        print e


if __name__ == "__main__":
    main()
