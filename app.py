import threading, sched, time, requests, os, re, glob, logging
from datetime import datetime
from pythonjsonlogger import jsonlogger
from PIL import Image
from gallocloud_utils.scheduling import get_next_schedule_time

logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO').upper())

logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter('%(levelname)%(message)')
logHandler.setFormatter(formatter)
logging.getLogger().handlers = []
logging.getLogger().addHandler(logHandler)

def convert_to_seconds(duration):
    seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    return int(duration[:-1]) * seconds_per_unit[duration[-1].lower()]

"""
    {
        name: 'cam1-snapshot',
        type: 'snapshot',
        url: 'http://user:pass@192.168.1.50/api/v1/snap.cgi?chn=1',
        schedule: '30s',
        keepTime: '15d',
        pruneSchedule: '1d',
        fileFormat: '/tmp/records/cam1/{date}/{datetime}.jpg',
        thumbs: {
            size: [768, 5000],
            fileFormat: '/tmp/records/cam1/{date}/thumbs/{datetime}.jpg'
        }
    }
"""
def load_config():
    records = []

    env_records = {}

    for k, v in os.environ.items():
        if k[0:7] == 'RECORD_':
            name, *rest = k[7:].split('_')
            name = name.lower()
            rest = '_'.join(rest)

            if name not in env_records:
                env_records[name] = {}

            env_records[name][rest] = v

    for name in env_records:
        values = env_records[name]
        o = {
            'name': name,
            'type': values['TYPE'],
            'url': values['URL'],
            'schedule': values['SCHEDULE'].split(';'),
            'keepTime': values['KEEP_TIME'], # None to disable ? We will see ...
            'pruneSchedule': values['PRUNE_SCHEDULE'].split(';'),
            'fileFormat': os.path.join('/data', values['FILE_FORMAT'])
        }
        if 'THUMBS_SIZE' in values or 'THUMBS_FILE_FORMAT' in values or 'THUMBS_QUALITY' in values:
            o['thumbs'] = {
                'size': list(map(lambda x: int(x) if x else 5000, values['THUMBS_SIZE'].split(','))),
                'fileFormat': os.path.join('/data', values['THUMBS_FILE_FORMAT']),
                'quality': int(values.get('THUMBS_QUALITY', '75'))
            }

        records.append(o)

    return records

def record(record_config):
    if record_config['type'] != 'snapshot':
        raise Exception('Only snapshots for the moment')

    s = sched.scheduler(time.time, time.sleep)

    def do_thumb(filename, filenameParams):
        try:
            logging.info('Thumb start', extra={'action': 'snapshot-thumb', 'status': 'starting', 'record': record_config['name']})
            im = Image.open(filename)
            im.thumbnail(record_config['thumbs']['size'])
            thumbFilename = record_config['thumbs']['fileFormat'].format(**filenameParams)
            dirname = os.path.dirname(thumbFilename)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            im.save(thumbFilename, "JPEG", quality=record_config['thumbs']['quality'], optimize=True, progressive=True)
            logging.info('Thumb end ; file {}'.format(thumbFilename), extra={'action': 'snapshot-thumb', 'status': 'success', 'record': record_config['name']})
        except Exception as e:
            logging.exception('Thumb error', extra={'action': 'snapshot-thumb', 'status': 'failure', 'record': record_config['name']})

    def do_snapshot():
        s.enterabs(get_next_schedule_time(record_config['schedule']), 1, do_snapshot)
        try:
            logging.info('Snaphot start', extra={'action': 'snapshot', 'status': 'starting', 'record': record_config['name']})
            now = datetime.now()
            filenameParams = {
                'date': now.strftime("%Y-%m-%d"),
                'time': now.strftime("%H-%M-%S"),
                'datetime': now.strftime("%Y-%m-%dT%H-%M-%S")
            }
            filename = record_config['fileFormat'].format(**filenameParams)
            dirname = os.path.dirname(filename)
            response = requests.get(record_config['url'], timeout=30)
            response.raise_for_status()
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            f = open(filename, "wb")
            f.write(response.content)
            f.close()
            logging.info('Snaphot end ; file {}'.format(filename), extra={'action': 'snapshot', 'status': 'success', 'record': record_config['name']})
            if 'thumbs' in record_config:
                do_thumb(filename, filenameParams)
        except Exception as e:
            logging.exception('Snaphot error', extra={'action': 'snapshot', 'status': 'failure', 'record': record_config['name']})
    do_snapshot()
    s.run()

def prune(record_config):
    s = sched.scheduler(time.time, time.sleep)

    def do_prune():
        s.enterabs(get_next_schedule_time(record_config['pruneSchedule']), 1, do_prune)
        try:
            logging.info('Prune start', extra={'action': 'prune', 'status': 'starting', 'record': record_config['name']})
            globs_ = [
                re.compile('{[^}]+}').sub('*', record_config['fileFormat'])
            ]

            if 'thumbs' in record_config:
                globs_.append(
                    re.compile('{[^}]+}').sub('*', record_config['thumbs']['fileFormat'])
                )

            max = time.time() - convert_to_seconds(record_config['keepTime'])
            totalFile = 0
            totalDir = 0
            directories = []

            for glob_ in globs_:
                for file in glob.iglob(glob_):
                    if os.stat(file).st_mtime < max:
                        os.remove(file)
                        totalFile += 1
                        logging.debug('Deleted file ' + file, extra={'action': 'prune', 'status': 'running', 'record': record_config['name']})
                        dirname = os.path.dirname(file)
                        if dirname not in directories:
                            directories.append(dirname)

            for directory in reversed(sorted(directories, key=len)):
                # I don't do parents directory but why not ...
                # We can image take the no dynamic part of the path and check parents directories
                if not os.listdir(directory):
                    os.rmdir(directory)
                    totalDir += 1
                    logging.debug('Deleted directory ' + directory, extra={'action': 'prune', 'status': 'running', 'record': record_config['name']})

            logging.info('Prune end ; {} files deleted ; {} directories deleted'.format(totalFile, totalDir), extra={'action': 'prune', 'status': 'success', 'record': record_config['name']})

        except Exception as e:
            logging.exception('Prune error', extra={'action': 'prune', 'status': 'failure', 'record': record_config['name']})

    do_prune()
    s.run()

records_config = load_config()

for record_config in records_config:
    threading.Thread(target=record, args=(record_config,)).start()
    threading.Thread(target=prune, args=(record_config,)).start()
