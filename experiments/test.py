import threading
import queue
import time

q = queue.Queue()


def producer():
    for i in range(3):
        print("put", i)
        q.put(i)

    print("Producer finished")


def consumer():
    while True:
        item = q.get()

        print("got", item)

        q.task_done()


producer_thread = threading.Thread(target=producer)
consumer_thread = threading.Thread(target=consumer, daemon=True)


producer_thread.start()
consumer_thread.start()


# Step 1: wait until producer stops creating tasks
producer_thread.join()

# Step 2: wait until all created tasks are completed
q.join()

print("Everything finished")