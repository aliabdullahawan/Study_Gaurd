import time
import threading
import queue
from dataclasses import dataclass

# --- TASK 3.2: The Dataclasses ---
@dataclass
class ActivitySnapshot:
    timestamp: str
    is_active: bool
    # (Leaving out the mouse/key variables for this minimal test)

@dataclass
class DetectionEvent:
    timestamp: str
    event_type: str
    description: str

# --- THE QUEUE (Detection Event Bus) ---
# This is a thread-safe pipeline. Multiple threads can add/remove items safely.
event_bus = queue.Queue()

# --- THE PRODUCER (Simulating your CombinedActivityMonitor) ---
def simulate_sensors():
    print("[PRODUCER] Sensor thread started.")
    
    # Simulate a sudden event (like an inactivity alert)
    time.sleep(2)
    alert = DetectionEvent(time.strftime("%H:%M:%S"), "INACTIVITY_ALERT", "User stopped moving.")
    event_bus.put(alert)
    print("[PRODUCER] Dropped an Event into the queue!")

    # Simulate a 5-second snapshot
    time.sleep(3)
    snapshot = ActivitySnapshot(time.strftime("%H:%M:%S"), False)
    event_bus.put(snapshot)
    print("[PRODUCER] Dropped a Snapshot into the queue!")

# --- THE CONSUMER (Simulating your Database/UI writer) ---
def process_queue_data():
    print("[CONSUMER] Database processor thread started, waiting for data...")
    
    while True:
        # .get() will safely pause this thread until an item appears in the queue
        data_item = event_bus.get() 
        
        # Check what kind of dataclass we just pulled out of the queue
        if isinstance(data_item, DetectionEvent):
            print(f"\n[CONSUMER] SAVING EVENT TO DATABASE: {data_item.event_type} - {data_item.description}")
        elif isinstance(data_item, ActivitySnapshot):
            print(f"\n[CONSUMER] SAVING SNAPSHOT TO DATABASE: Active={data_item.is_active} at {data_item.timestamp}")
            
        # Tell the queue that the task is finished
        event_bus.task_done()

# --- EXECUTION ---
def main():
    # 1. Start the Consumer thread in the background
    consumer_thread = threading.Thread(target=process_queue_data, daemon=True)
    consumer_thread.start()

    # 2. Start the Producer thread
    producer_thread = threading.Thread(target=simulate_sensors)
    producer_thread.start()

    # Keep the main program alive long enough for the simulation to run
    try:
        producer_thread.join()
        event_bus.join()
        print("\nSimulation complete.")
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()