#!/usr/bin/env python

import urllib2
from tempfile import mkstemp
from shutil import move, rmtree
from os import remove, close, path, rename, umask, symlink, unlink, walk, makedirs
import subprocess
import math
import time
import argparse
import re

parser = argparse.ArgumentParser(description='Installs and configures Puppet on OS X')
parser.add_argument('--server', help='The URL of the Puppet Server.)
parser.add_argument('--certname', help='The certname of the client.')
parser.add_argument('--serial', action='store_true', help='Use the Mac\'s serial number as the certname')
parser.add_argument('--clean_serial', action='store_true', help='Use the Mac\'s serial number as the certname, with aaa prepended to it if the first character is a digit.')
parser.add_argument('--appendhosts', action='store_true', help='If using with the Vagrant-based Puppet Master, appends the hosts file with the default IP address')
args = vars(parser.parse_args())

if args['server']:
    puppetserver = args['server']
else:
    puppetserver = ''
def downloadChunks(url):
    """Helper to download large files
        the only arg is a url
       this file will go to a temp directory
       the file will also be downloaded
       in chunks and print out how much remains
    """

    baseFile = path.basename(url)

    #move the file to a more uniq path
    umask(0002)

    try:
        temp_path='/tmp'
        file = path.join(temp_path,baseFile)

        req = urllib2.urlopen(url)
        total_size = int(req.info().getheader('Content-Length').strip())
        downloaded = 0
        CHUNK = 256 * 10240
        with open(file, 'wb') as fp:
            while True:
                chunk = req.read(CHUNK)
                downloaded += len(chunk)
                print math.floor( (downloaded / total_size) * 100 )
                if not chunk: break
                fp.write(chunk)
    except urllib2.HTTPError, e:
        print "HTTP Error:",e.code , url
        return False
    except urllib2.URLError, e:
        print "URL Error:",e.reason , url
        return False

    return file

def forget_pkg(pkgid):
    cmd = ['/usr/sbin/pkgutil', '--forget', pkgid]
    proc = subprocess.Popen(cmd, bufsize=1,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    (output, unused_err) = proc.communicate()
    return output

def internet_on():
    try:
        response=urllib2.urlopen(puppetserver,timeout=1)
        return True
    except urllib2.URLError as err: pass
    return False

def chown_r(path):
    makedirs(path)
    the_command = "chown -R root:wheel "+path
    serial = subprocess.Popen(the_command,shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE).communicate()[0]
    the_command = "chmod -R 777 "+path
    serial = subprocess.Popen(the_command,shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE).communicate()[0]

if internet_on:
    if args['certname']:
        certname = args['certname']
    else:
        certname = 'client.grahamgilbert.dev'

    if args['serial']:
        the_command = "ioreg -c \"IOPlatformExpertDevice\" | awk -F '\"' '/IOPlatformSerialNumber/ {print $4}'"
        serial = subprocess.Popen(the_command,shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE).communicate()[0]
        serial = re.sub(r'\s', '', serial)
        # remove the silly characters that VMware likes to put in occasionally
        serial = serial.replace("+", "")
        serial = serial.replace("/", "")
        certname = serial.lower()

    if args['clean_serial']:
        the_command = "ioreg -c \"IOPlatformExpertDevice\" | awk -F '\"' '/IOPlatformSerialNumber/ {print $4}'"
        serial = subprocess.Popen(the_command,shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE).communicate()[0]
        serial = re.sub(r'\s', '', serial)
        # remove the silly characters that VMware likes to put in occasionally
        serial = serial.replace("+", "")
        serial = serial.replace("/", "")
        if serial[0].isdigit():
            serial = "aaa"+serial
        certname = serial.lower()

    if args['appendhosts']:
        with open("/etc/hosts", "a") as myfile:
            myfile.write("192.168.33.10 puppet.grahamgilbert.dev")

    import platform
    v, _, _ = platform.mac_ver()
    v = float('.'.join(v.split('.')[:2]))
    print v
    # 10.8 needs json_pure instaling now. Harrumph.
    if v == 10.8:
        print 'Installing json_pure gem'
        the_command = '/usr/bin/gem install json_pure'
        p=subprocess.Popen(the_command,shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        p.wait()

    if path.isdir('/var/lib/puppet'):
        print "Binning old Puppet installation"
        rmtree('/var/lib/puppet')
    if path.isdir('/etc/puppet'):
        rmtree('/etc/puppet')

    # forget about the previously installed packages - we might not be installing the latest version

    forget_pkg('com.puppetlabs.facter')
    forget_pkg('com.puppetlabs.hiera')
    forget_pkg('com.puppetlabs.puppet')


    print "Downloading Puppet"
    the_dmg = downloadChunks("https://downloads.puppetlabs.com/mac/10.13/PC1/x86_64/puppet-agent-1.10.12-1.osx10.13.dmg")
    ##mount the dmg
    print "Mounting Puppet DMG"
    the_command = "/usr/bin/hdiutil attach "+the_dmg
    p=subprocess.Popen(the_command,shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    p.wait()
    time.sleep(10)
    print "Installing Puppet"
    the_command = "/usr/sbin/installer -pkg /Volumes/puppet-agent-1.10.12-1.osx10.13/puppet-agent-1.10.12-1-installer.pkg -target /"
    p=subprocess.Popen(the_command,shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    p.wait()
    time.sleep(20)
    print "Ejecting Puppet"
    the_command = "hdiutil eject /Volumes/puppet-agent-1.10.12-1.osx10.13"
    subprocess.Popen(the_command,shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE).communicate()[0]



    data = "[agent]\nserver="+puppetserver+"\ncertname="+certname+""
    the_command = "/usr/bin/touch /etc/puppetlabs/puppet/puppet.conf"
    p=subprocess.Popen(the_command,shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    print "writing the puppet configuration"
    file = open("/etc/puppetlabs/puppet/puppet.conf", "w")
    file.write(data)
    file.close()

    print "All done!"
