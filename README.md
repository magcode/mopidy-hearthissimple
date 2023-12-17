# mopidy-hearthissimple
This is simple Hearthis.at backend for [Mopidy V3](https://github.com/mopidy/mopidy).

It gives you quick access your feed and the artist you follow.

# install
```
cd ~
git clone https://github.com/magcode/mopidy-hearthissimple.git
sudo python3 pip install -e mopidy-hearthissimple
# you can also try 'sudo pip3 install -e mopidy-hearthissimple' in case the last command does not work
```
# uninstall
```
cd ~/mopidy-hearthissimple
sudo python3 setup.py develop -u
```
# configuration in mopidy.conf
```
[hearthissimple]
enabled = true
username = <your Hearthis.at account email>
password = <your Hearthis.at account password>
