"""Read/write example. Start the sample PLC service in S7 Studio first."""
import argparse
import struct
import time

import snap7

parser = argparse.ArgumentParser()
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=1102)
parser.add_argument("--rack", type=int, default=0)
parser.add_argument("--slot", type=int, default=1)
parser.add_argument("--watch", action="store_true", help="Keep the connection open and poll temperature")
args = parser.parse_args()

client = snap7.Client()
try:
    client.connect(args.host, args.rack, args.slot, tcp_port=args.port)
    raw = client.db_read(1, 0, 16)
    print("DB1 raw:", raw.hex(" "))
    print("System_Running:", bool(raw[0] & 1))
    print("Temperature:", struct.unpack_from(">f", raw, 2)[0])
    print("Pressure:", struct.unpack_from(">f", raw, 6)[0])
    client.db_write(1, 12, bytearray(struct.pack(">i", 2026)))
    print("Batch_Count written:", struct.unpack(">i", client.db_read(1, 12, 4))[0])
    if args.watch:
        print("Polling every second. Press Ctrl+C to disconnect.")
        while True:
            print("Temperature:", struct.unpack(">f", client.db_read(1, 2, 4))[0])
            time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    client.disconnect()
    client.destroy()
