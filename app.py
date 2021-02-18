import threading, sched, time, requests, os, re, glob, logging
from datetime import datetime
from pythonjsonlogger import jsonlogger

logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO').upper())

logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter('%(levelname)%(message)')
logHandler.setFormatter(formatter)
logging.getLogger().handlers = []
logging.getLogger().addHandler(logHandler)

def convert_to_seconds(duration):
    seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    return int(duration[:-1]) * seconds_per_unit[duration[-1].lower()]

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
        records.append({
            'name': name,
            'type': values['TYPE'],
            'url': values['URL'],
            'schedule': values['SCHEDULE'],
            'keepTime': values['KEEP_TIME'], # None to disable ? We will see ...
            'pruneSchedule': values['PRUNE_SCHEDULE'],
            'fileFormat': values['FILE_FORMAT']
        })

    return records

def record(record_config):
    if record_config['type'] != 'snapshot':
        raise Exception('Only snapshots for the moment')

    s = sched.scheduler(time.time, time.sleep)

    def do_snapshot():
        s.enter(convert_to_seconds(record_config['schedule']), 1, do_snapshot)
        try:
            logging.info('Snaphot start', extra={'action': 'snapshot', 'status': 'starting', 'record': record_config['name']})
            now = datetime.now()
            filename = record_config['fileFormat'].format(
                date=now.strftime("%Y-%m-%d"),
                time=now.strftime("%H-%M-%S"),
                datetime=now.strftime("%Y-%m-%dT%H-%M-%S")
            )
            dirname = os.path.dirname(filename)
            response = requests.get(record_config['url'])
            response.raise_for_status()
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            f = open(filename, "wb")
            f.write(response.content)
            f.close()
            logging.info('Snaphot end ; file {}'.format(filename), extra={'action': 'snapshot', 'status': 'success', 'record': record_config['name']})
        except Exception as e:
            logging.exception('Snaphot error', extra={'action': 'snapshot', 'status': 'failure', 'record': record_config['name']})
    do_snapshot()
    s.run()

def prune(record_config):
    s = sched.scheduler(time.time, time.sleep)

    def do_prune():
        s.enter(convert_to_seconds(record_config['pruneSchedule']), 1, do_prune)
        try:
            logging.info('Prune start', extra={'action': 'prune', 'status': 'starting', 'record': record_config['name']})
            glob_ = re.compile('{[^}]+}').sub('*', record_config['fileFormat'])

            max = time.time() - convert_to_seconds(record_config['keepTime'])
            totalFile = 0
            totalDir = 0
            directories = []

            for file in glob.iglob(glob_):
                if os.stat(file).st_mtime < max:
                    os.remove(file)
                    totalFile += 1
                    logging.debug('Deleted file ' + file, extra={'action': 'prune', 'status': 'running', 'record': record_config['name']})
                    dirname = os.path.dirname(file)
                    if dirname not in directories:
                        directories.append(dirname)

            for directory in directories:
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
