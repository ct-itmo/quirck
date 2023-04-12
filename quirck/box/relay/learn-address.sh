#!/bin/bash

ip=${trusted_ip:-$trusted_ip6}
interface=mv-${trusted_ip//[\.:]/}-$(printf '%04x' $trusted_port)

if [[ "$1" == "delete" ]]; then
    ip link set link dev $interface type macvlan macaddr del ${2%%@*}
else
    ip link set link dev $interface type macvlan macaddr add ${2%%@*}
fi
