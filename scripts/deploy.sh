#!/bin/bash
cd "$(dirname "$0")"

cd .. 
cp working.md _posts/$(date +%F)-comic.md
mkdir assets/images/$(date +%F)
cp assets/images/serialnumber/*.*  assets/images/$(date +%F)
