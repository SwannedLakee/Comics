#!/bin/bash
cd "$(dirname "$0")"

echo 

cd ../assets/images
mkdir $1  #Okay so $1 is a datestring 
cd ../../_posts
cp template.md $1-comic.md
perl -pi -e "s/serialnumber/$1/g" $1-comic.md  # Updating the number (but NOT the date) 
perl -pi -e "s/imagedirectory/$1/g" $1-comic.md  # Updating the number (but NOT the date) 

# todo 
# * update the directory 
