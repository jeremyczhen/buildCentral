#!/bin/bash


# sleep 10
currentPath=`pwd`
killall -9 component-host
killall omniNames
rm -rf ~/omniorb/names/*
mkdir -p ~/omniorb/names

export OMNINAMES_LOGDIR=~/omniorb/names
export OMNIORB_CONFIG=$currentPath/omniORB.cfg
export LD_LIBRARY_PATH=$currentPath/../lib:$LD_LIBRARY_PATH

kill $(pgrep omniNames)
$currentPath/omniNames -start -always &

export CORBAFW_CONFIGDIR=$currentPath
$currentPath/service-manager
