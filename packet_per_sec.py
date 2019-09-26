#!/usr/bin/python3

# Use this script to monitor the bytes/s and packet/s on a specified interface, for example lo.
# The values are monitored every sec.

import time

def get_bytes(t, iface='lo'):
    with open('/sys/class/net/' + iface + '/statistics/' + t + '_bytes', 'r') as f:
        data = f.read();
    return int(data)

def get_packets(t, iface='lo'):
    with open('/sys/class/net/' + iface + '/statistics/' + t + '_packets', 'r') as f:
        data = f.read();
    return int(data)


if __name__ == '__main__':
    (tx_prev, rx_prev) = (0, 0)
    (tx_prev_pack, rx_prev_pack) = (0, 0)

    while(True):
        tx = get_bytes('tx')
        rx = get_bytes('rx')
        tx_pack = get_packets('tx')
        rx_pack = get_packets('rx')


        if tx_prev > 0:
            tx_speed = tx - tx_prev
            tx_speed_pack = tx_pack - tx_prev_pack
            print('TX: ', tx_speed, 'bps, packet/s: ', tx_speed_pack)

        if rx_prev > 0:
            rx_speed = rx - rx_prev
            rx_speed_pack = rx_pack - rx_prev_pack            
            print('RX: ', rx_speed, 'bps, packet/s: ', rx_speed_pack)


        time.sleep(1)

        tx_prev = tx
        rx_prev = rx
        tx_prev_pack = tx_pack
        rx_prev_pack = rx_pack

