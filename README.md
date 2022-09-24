This is a discrete-event simulation (DES) of a simple polled
double-buffering system (multiple producers, single consumer)
in [SimPy](https://simpy.readthedocs.io/en/latest/).
Created in order to evaluate the impact of polled vs. asynchronous
'draining' methods. With the same memory allocated to buffers
and data producers the asynchronous 'draining' is almost twice
as capable when it comes to accommodating temporary data bursts.

![1_lost_polled_10ms](plots/1_lost_polled_10ms.png)

![2_lost_async](plots/2_lost_async.png)

![3_lost_async_single_buf_2k](plots/3_lost_async_single_buf_2k.png)

![plots/4_lost_async_single_buf_4k](plots/4_lost_async_single_buf_4k.png)
