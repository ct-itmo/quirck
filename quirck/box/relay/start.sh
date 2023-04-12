#!/bin/bash

set -e

sed -i 's:$cert:'"$CERT"':g' /app/openvpn.conf
sed -i 's:$key:'"$KEY"':' /app/openvpn.conf

mkdir -p /logs

mkdir -p /dev/net
mknod /dev/net/tun c 10 200 || true

echo "Configuration:"
env | grep NETWORK | tee /run/network.env
echo ""
echo "Interfaces:"
ip -br link show

for network in $NETWORK_LIST; do
    mac_name="NETWORK_HWADDR_$network"
    mac=${!mac_name}
    iface=$(ip -o link | grep -i $mac | cut -d':' -f 2 | cut -d'@' -f 1)
    echo "Interface $iface corresponds to network $network"

    ip link set $iface up
    ip link set $iface promisc on
    ip link add name br-$network type bridge
    ip link set $iface master br-$network
    ip link set br-$network up
    ip link set br-$network promisc on
done

openvpn --config /app/openvpn.conf --daemon

shutdown() {
  echo "Shutting down"
  exit 0
}

trap 'shutdown' SIGTERM
echo "It's alive, sleeping..."

while true; do
    sleep 123456 & wait $!
done
