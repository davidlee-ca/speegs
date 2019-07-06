from confluent_kafka import Producer
from time import time, sleep
import boto3
import sys


broker = "10.0.1.62:9092,10.0.1.24:9092,10.0.1.17:9092"

if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.stderr.write('Usage: %s <subject_id> <replay file number>\n' % sys.argv[0])
        sys.exit(1)

    subject_id = sys.argv[1]
    replay_file_number = sys.argv[2]
    topic = "eeg-signal-" + subject_id

    # Producer configuration
    # See https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md
    conf = {'bootstrap.servers': broker,
            'group.id': 'eeg-player'}

    # Create Producer instance
    p = Producer(**conf)

    # Open the EEG file from the S3 bucket
    mybucket = 'speegs-source-chbmit'
    mykey = f"{subject_id}/{subject_id}_{replay_file_number}.csv"

    s3 = boto3.client('s3')
    obj = s3.get_object(Bucket=mybucket, Key=mykey)['Body']

    start_time = time()
    channels = (
        'FP1-F7', 'F7-T7', 'T7-P7', 'P7-O1', 'FP1-F3', 'F3-C3', 'C3-P3', 'P3-O1', 'FP2-F4', 'F4-C4', 'C4-P4', 'P4-O2',
        'FP2-F8', 'F8-T8', 'T8-P8', 'P8-O2', 'FZ-CZ', 'CZ-PZ', 'P7-T7', 'T7-FT9', 'FT9-FT10', 'FT10-T8', 'T8-P8.1')

    line = obj._raw_stream.readline() # throw away the first line

    count = 0
    heartbeat = time()
    for line in obj._raw_stream:
        readings = str(line.decode().strip()).split(',')

        for i in range(23):
            key = '{"ch": "%s"}' % (channels[i])
            value = '{"timestamp": %.6f, "v": %.6f}' % (start_time + float(readings[0]), float(readings[i + 1]))
            p.produce(topic, value=value, key=key)
        sleep(0.0033)  # tunable -- 2ms worked well for 4, see if 1ms sleep will reduce the deviation
        p.flush()

        count += 1
        if count == 2560:
            new_heartbeat = time()
            duration = new_heartbeat - heartbeat
            deviation = (10.0 - duration) * 1000
            print(f"10-second check in for {subject_id}. Took {duration} sec to send 2560 x 23 messages. Deviation: {deviation:.2f} milliseconds.")
            count = 0
            heartbeat = new_heartbeat