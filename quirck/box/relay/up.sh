#!/bin/bash

source /run/network.env

ip link set $dev up
ip link set $dev promisc on
