#!/bin/bash

source /run/network.env
ip=${trusted_ip:-$trusted_ip6}
interface=mv-$(echo "${trusted_ip:-$trusted_ip6}:$trusted_port" | md5sum | head -c 12)
network=${UV_NETWORK:-$NETWORK_DEFAULT}
var_name="NETWORK_HWADDR_$network"

ip link del $interface || true
