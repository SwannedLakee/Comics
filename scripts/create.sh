#!/bin/bash
cd "$(dirname "$0")"

echo $1

cd ..
mkdir $1 
cp template.html $1.html 
perl -pi -e "s/serialnumber/$1/g" $1.html  # Updating the number (but NOT the date) 
perl -pi -e "s/imagedirectory/$1/g" $1.html  # Updating the number (but NOT the date) 

# todo 
# * update the directory 
