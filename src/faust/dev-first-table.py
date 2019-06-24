import faust
import pywt
import numpy as np
import entropy
from datetime import datetime



class EegReading(faust.Record, serializer='json'):
    time: float
    potential: float
    channel: str


app = faust.App(
    'helloworld-by-country',
    broker='kafka://ip-10-0-0-4.ec2.internal:9092'
)

my_topic = app.topic('greetings', key_type=str, value_type=EegReading)

table_counts = app.Table('mycount', default=int).tumbling(5.0, expires=5.0)
table_sum = app.Table('mysum', default=float).tumbling(5.0, expires=5.0)


# from StackExchange -- generate surrogate series!
def generate_surrogate_series(ts):  # time-series is an array
    ts_fourier  = np.fft.rfft(ts)
    random_phases = np.exp(np.random.uniform(0,np.pi,len(ts)//2+1)*1.0j)
    ts_fourier_new = ts_fourier*random_phases
    new_ts = np.fft.irfft(ts_fourier_new)
    return new_ts


def get_delta_apen(ts): # time-series is an array
    # Perform discrete wavelet transform to get A3, D3, D2, D1 coefficient time series,
    # and create corresponding surrogate time series
    (cA1, cD1) = pywt.dwt(ts, 'db4')
    (cA2, cD2) = pywt.dwt(cA1, 'db4')
    cD2_surrogate = generate_surrogate_series(cD2)
    app_entropy_sample = entropy.app_entropy(cD2, order=2, metric='chebyshev')
    app_entropy_surrogate = entropy.app_entropy(cD2_surrogate, order=2, metric='chebyshev')

    # Return the delta
    delta_ApEns = app_entropy_surrogate - app_entropy_sample
    return delta_ApEns


@app.agent(my_topic)
async def count_readings(readings):
    async for reading in readings.group_by(reading.channel):
        print(f"Received message with timestamp: {reading.time}")
        table_counts[reading.channel] += 1
        table_sum[reading.channel] += reading.potential

@app.timer(2.0)
async def report_every_other_second():
    print(f"   --- {datetime.now()}: we have the following state in table_counts:")
    print(table_counts)
    print("   --- and in table_sum:")
    print(table_sum)


if __name__ == '__main__':
    app.main()