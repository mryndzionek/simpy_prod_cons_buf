import simpy
import random
import logging

from functools import partial, wraps
import matplotlib.pyplot as plt

TICKS_IN_SEC = 1000000  # 1us sim. resolution
NUM_TASKS = 10
BUF_SIZE = 2048  # bytes
UART_SPEED_MBITS = 1  # 1Mbit/s in bytes
SIM_LEN = TICKS_IN_SEC * 3.0


def plot_data(ring_data, uart_data, ring_lost, description):
    f = plt.figure()
    f.set_figwidth(40)
    f.set_figheight(5)

    plt.plot([], [], ' ', label="\n".join(description))
    plt.step(*zip(*ring_data), where='post', label='ring buffer occupancy',
             marker=".", markersize=6, color='tab:green')
    plt.step(*zip(*uart_data), where='post', label='uart buffer occupancy',
             marker=".", markersize=4, color='tab:blue')
    if len(ring_lost) > 0:
        plt.step(*zip(*ring_lost), where='post', label='ring buffer data discarded',
                 marker=".", markersize=4, color='tab:red')
    plt.grid()
    plt.legend(labelcolor='blue')
    plt.locator_params(axis='x', nbins=20)
    plt.xlabel('time [us]')
    plt.ylabel('size [bytes]')
    plt.ylim(0, BUF_SIZE + 100)
    plt.show()


def patch_container(container, pre=None, post=None):
    def get_wrapper(func):

        @wraps(func)
        def wrapper(*args, **kwargs):
            if pre:
                pre(container)

            ret = func(*args, **kwargs)

            if post:
                post(container)

            return ret
        return wrapper

    for name in ['put', 'get']:
        if hasattr(container, name):
            setattr(container, name, get_wrapper(getattr(container, name)))


def monitor(data, container):
    item = (
        container._env.now,
        container.level,
    )
    data.append(item)


def task(env, ring_b, n, ms, num_bytes):
    global ring_lost_sum
    global ring_lost

    dt = (ms * 1000)
    phase = random.randint(0, dt - 1)
    yield env.timeout(phase)
    while(True):
        jitter = random.randint(-10, 10)
        yield env.timeout(dt + jitter)
        if (ring_b.level + num_bytes) <= BUF_SIZE:
            logging.debug('[{}] Task {} sending {} bytes (queue level {})'.format(
                env.now, n, num_bytes, ring_b.level))
            yield ring_b.put(num_bytes)
        else:
            ring_lost_sum += num_bytes
            ring_lost.append((env.now, ring_lost_sum))
            logging.warning('[{}] Task {} discarded {} bytes (queue level {}) !!!'.format(
                env.now, n, num_bytes, ring_b.level))


def uart_task(env, uart_b):
    ticks_per_byte = TICKS_IN_SEC / (UART_SPEED_MBITS * 1000000 / 8)

    while(True):
        if uart_b.level > 0:
            logging.debug('[{}] UART buffer level {}'.format(
                env.now, uart_b.level))
        yield uart_b.get(1)
        yield env.timeout(ticks_per_byte)


def clock_src(env, clock, tick_ms=10):
    while True:
        with clock.request() as req:
            yield req
            yield env.timeout(tick_ms * 1000)


def drain_polled(env, ring_b, uart_b, poll_period_ms=10):

    if poll_period_ms <= 0:
        raise ValueError('poll_period_ms must be greater than zero')

    clock = simpy.Resource(env)
    env.process(clock_src(env, clock, poll_period_ms))

    while(True):
        with clock.request() as req:
            yield req
        assert(env.now % (poll_period_ms * 1000) == 0)

        if (ring_b.level > 0):
            logging.debug('[{}] Draining Queue level: {}'.format(
                env.now, ring_b.level))
            amount = ring_b.level
            yield uart_b.put(amount)
            yield ring_b.get(amount)
        else:
            logging.debug('[{}] Queue empty'.format(env.now))


def drain_async(env, ring_b, uart_b):

    while(True):
        logging.debug('[{}] Draining Queue level: {}'.format(
            env.now, ring_b.level))
        yield ring_b.get(1)
        amount = ring_b.level + 1
        yield ring_b.get(ring_b.level)
        yield uart_b.put(amount)


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M:%S',
                    filemode='w')

random.seed(666)

env = simpy.Environment()

ring_buf = simpy.Container(env)
uart_buf = simpy.Container(env, BUF_SIZE)

# setup monitoring
ring_data = []
uart_data = []

ring_mon = partial(monitor, ring_data)
uart_mon = partial(monitor, uart_data)

patch_container(ring_buf, post=ring_mon)
patch_container(uart_buf, post=uart_mon)

ring_lost = []
ring_lost_sum = 0

task_burst_size = 127  # bytes
task_avg_intrvl = 10  # ms
task_data_rate = task_burst_size * (1000 / task_avg_intrvl)
logging.info(
    'Average production rate: {} bits/s'.format(NUM_TASKS * task_data_rate * 8))

description = ['mode: {}'.format('polled'),
               'num_tasks: {}'.format(NUM_TASKS),
               'buffer size: {} B'.format(BUF_SIZE),
               'UART speed: {} Mbits/s'.format(UART_SPEED_MBITS),
               'production rate: {} Mbits/s'.format(NUM_TASKS * task_data_rate * 8 / 1000000)]

env.process(drain_polled(env, ring_buf, uart_buf, 10))
#env.process(drain_async(env, ring_buf, uart_buf))

for i in range(0, NUM_TASKS):
    env.process(task(env, ring_buf, i, task_avg_intrvl, task_burst_size))

env.process(uart_task(env, uart_buf))

env.run(until=SIM_LEN)

plot_data(ring_data, uart_data, ring_lost, description)
