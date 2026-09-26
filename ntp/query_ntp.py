"""Query and validate an IPv4 NTP response without adjusting the local clock."""
import argparse
import datetime
import json
import socket
import struct
import time


def query(host, source=None):
    epoch = 2208988800
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(5)
        if source:
            sock.bind((source, 0))
        sock.connect((host, 123))
        packet = bytearray(48)
        packet[0] = 0x23  # NTPv4 client.
        sent = time.time()
        stamp = sent + epoch
        struct.pack_into('!II', packet, 40, int(stamp), int((stamp % 1) * 2**32))
        sock.send(packet)
        reply = sock.recv(512)
        received = time.time()
        if len(reply) < 48 or reply[0] & 7 != 4:
            raise ValueError('Invalid NTP server response')
        if reply[24:32] != packet[40:48]:
            raise ValueError('Response does not match the request timestamp')
        if reply[0] >> 6 == 3 or not 1 <= reply[1] <= 15:
            raise ValueError('Server is not synchronized or returned a kiss-of-death')

        def timestamp(start):
            sec, frac = struct.unpack_from('!II', reply, start)
            if sec == 0:
                raise ValueError('Missing server timestamp')
            return sec - epoch + frac / 2**32

        server_received, server_sent = timestamp(32), timestamp(40)
        return {
            'server': host,
            'client': sock.getsockname()[0],
            'stratum': reply[1],
            'leap': reply[0] >> 6,
            'offset_ms': round(((server_received - sent) + (server_sent - received)) * 500, 3),
            'delay_ms': round(((received - sent) - (server_sent - server_received)) * 1000, 3),
            'server_utc': datetime.datetime.fromtimestamp(server_sent, datetime.timezone.utc).isoformat(),
        }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host')
    parser.add_argument('--source')
    args = parser.parse_args()
    print(json.dumps(query(args.host, args.source), indent=2))
