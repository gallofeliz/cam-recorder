import threading, sched, time, requests, os, re, glob
from datetime import datetime

def convert_to_seconds(duration):
    seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    return int(duration[:-1]) * seconds_per_unit[duration[-1].lower()]

records_config = [
    {
        'type': 'snapshot',
        'url': 'http://user:pass@192.168.1.50/api/v1/snap.cgi?chn=1',
        'schedule': '1m',
        'keepTime': '15m',
        'fileFormat': '/tmp/records/cam1/{date}/{datetime}.jpg'
    }
]

def record(record_config):
    if record_config['type'] != 'snapshot':
        raise Exception('Only snapshots for the moment')

    s = sched.scheduler(time.time, time.sleep)

    def do_snapshot():
        s.enter(convert_to_seconds(record_config['schedule']), 1, do_snapshot)
        print('Snaphot start')
        now = datetime.now()
        filename = record_config['fileFormat'].format(
            date=now.strftime("%Y-%m-%d"),
            time=now.strftime("%H-%M-%S"),
            datetime=now.strftime("%Y-%m-%dT%H-%M-%S")
        )
        dirname = os.path.dirname(filename)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        response = requests.get(record_config['url'])
        response.raise_for_status()

        f = open(filename, "wb")
        f.write(response.content)
        f.close()
        print('Snaphot done')

    do_snapshot()
    s.run()


for record_config in records_config:
    threading.Thread(target=record, args=(record_config,)).start()

def prune(records_config):
    s = sched.scheduler(time.time, time.sleep)

    def do_prune():
        s.enter(convert_to_seconds('30m'), 1, do_prune)
        for record_config in records_config:
            glob_ = re.compile('{[^}]+}').sub('*', record_config['fileFormat'])

            max = time.time() - convert_to_seconds(record_config['keepTime'])

            for file in glob.iglob(glob_):
                if os.stat(file).st_mtime < max:
                    print('delete ' + file)
                    os.remove(file)

            # todo remove empty directory

    do_prune()
    s.run()

threading.Thread(target=prune, args=(records_config,)).start()
