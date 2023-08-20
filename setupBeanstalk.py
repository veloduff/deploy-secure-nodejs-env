#!/usr/bin/env python
#
# Copyright 2023 Mark Duffield
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file
# except in compliance with the License. A copy of the License is located at
#
#     http://www.apache.org/licenses/LICENSE-2.0 
#
# or in the "license" file accompanying this file. This file is distributed on an "AS IS"
# BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under the License.
#


import sys, os
import shutil
import argparse
import subprocess
from pathlib import Path
import ebFileTemplates as ebt

_PRINT_SP = 39

def runcmd(cmdlist):

    try:
        proc = subprocess.Popen(cmdlist, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate()
    except Exception as e:
        raise ValueError(e)

    if proc.returncode != 0:
        log = out + err
    else:
        log = out
    return (log, proc.returncode)


def create_pass_phrase(passFile):
    cmd = ['openssl', 'rand', '-base64', '32', '-out', passFile]
    (log, cmd_rc) = runcmd(cmd)

    return cmd_rc


def create_ssl_file(passFile, webKey, webCert, appKey, appCert, bstalk_SSL_file):

    create_pass_phrase(passFile)

    print('  Creating Beanstalk SSL file'.ljust(_PRINT_SP, ' '), bstalk_SSL_file)
    sslCertsFile =  open(bstalk_SSL_file, 'w')

    # Write the header
    sslCertsFile.write(ebt._SSL_FILE_HEADER)

    # Create the web server key
    cmd = ['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:4096', '-out', webKey]
    if runcmd(cmd):
        sslCertsFile.write(ebt._SSL_WEB_SRV_KEY_INFO)
        print('  Creating web server key'.ljust(_PRINT_SP, ' '), webKey)
        webKeyFile = open(webKey, 'r')
        for l in webKeyFile.readlines():
            sslCertsFile.write('      ' + l)
        webKeyFile.close()
    else:
        msg = 'failed to create the web server key'
        print(msg)
        sys.exit(1)
    
    # Create the web server certificate
    cmd = ['openssl', 'req', '-x509', '-new', '-sha256', '-key', webKey, 
           '-out', webCert, '-subj', '/C=US/ST=California/L=Sunnyvale/O=MyWebServer1/CN=*.elasticbeanstalk.com']
    if runcmd(cmd):
        sslCertsFile.write(ebt._SSL_WEB_SRV_CRT_INFO)
        print('  Creating web server certificate'.ljust(_PRINT_SP, ' '), webCert)
        webCertFile = open(webCert, 'r')
        for l in webCertFile.readlines():
            sslCertsFile.write('      ' + l)
        webCertFile.close()
    else:
        msg = 'failed to create the web server certificate'
        print(msg)
        sys.exit(1)

    # Create the application key 
    cmd = ['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:4096', 
           '-aes-256-cbc', '-pass', 'file:' + passFile, '-out', appKey]
    if runcmd(cmd):
        sslCertsFile.write(ebt._SSL_APP_KEY_INFO)
        print('  Creating application key'.ljust(_PRINT_SP, ' '), appKey)
        appKeyFile = open(appKey, 'r')
        for l in appKeyFile.readlines():
            sslCertsFile.write('      ' + l)
        appKeyFile.close()
    else:
        msg = 'failed to create the app key'
        print(msg)
        sys.exit(1)
    
    # Create the application certificate 
    cmd = ['openssl', 'req', '-x509', '-new', '-sha256', '-key', appKey, 
           '-out', appCert, '-passin', 'file:' +  passFile, 
           '-subj', '/C=US/ST=California/L=Sunnyvale/O=MyApp1/CN=*.elasticbeanstalk.com']
    if runcmd(cmd):
        sslCertsFile.write(ebt._SSL_APP_CERT_INFO)
        print('  Creating application certificate'.ljust(_PRINT_SP, ' '), appCert)
        appCertFile = open(appCert, 'r')
        for l in appCertFile.readlines():
            sslCertsFile.write('      ' + l)
        appCertFile.close()
    else:
        msg = 'failed to create the app key'
        print(msg)
        sys.exit(1)

    sslCertsFile.close()

    return 0 

def create_options_file(passFile, bstalk_options_file):

    print('  Creating pass phrase file'.ljust(_PRINT_SP, ' '), passFile) 
    with open(passFile, 'r') as passFile:
        passPhrase = passFile.read().rstrip()
    passFile.close()

    print('  Creating Beanstalk options file'.ljust(_PRINT_SP, ' '), bstalk_options_file)
    optionsFile = open(bstalk_options_file, 'w')
    optionsFile.write(ebt._OPTIONS_FILE_TEMPLATE.format(passPhrase))
    optionsFile.close()

def create_sec_group_file(bstalk_sec_group_file):

    print('  Creating Beanstalk sec group file'.ljust(_PRINT_SP, ' '), bstalk_sec_group_file)
    secGroupFile = open(bstalk_sec_group_file, 'w')
    secGroupFile.write(ebt._SEC_GROUP_TEMPLATE)
    secGroupFile.close

def create_https_conf_file(nginx_https_file):

    print('  Creating Nginx https config file'.ljust(_PRINT_SP, ' '), nginx_https_file)
    httpsConfFile = open(nginx_https_file, 'w')
    httpsConfFile.write(ebt._HTTPS_CONF_FILE_TEMPLATE)
    httpsConfFile.close

def create_nginx_conf_file(nginx_conf_file):

    print('  Creating Nginx server config file'.ljust(_PRINT_SP, ' '), nginx_conf_file)
    nginxConfFile = open(nginx_conf_file, 'w')
    nginxConfFile.write(ebt._NGINX_CONF_TEMPLATE)
    nginxConfFile.close

def create_env_file(passFile, certDir, appKey, appCert):

    print('  Creating .env file'.ljust(_PRINT_SP, ' '), '.env')

    with open(passFile, 'r') as pf:
        passPhrase = pf.read().rstrip()
    pf.close()

    envFile = open('.env', 'w')
    envFile.write(
        ebt._ENV_FILE_TEMPLATE.format( 
            passPhrase,
            certDir, 
            Path(appKey).name, 
            Path(appCert).name
            )
    )


def main():

    parser = argparse.ArgumentParser(description='beanstalk setup')
    requiredGroup = parser.add_argument_group('required arguments')
    requiredGroup.add_argument('-d', help='certificates directory', required=True, metavar='<cert_directory>')
    args = parser.parse_args()

    certDir = os.path.join(args.d, '')
    userHome = str(Path.home())

    print('\n  The {} directory should be in both the .gitignore file and .ebignore file.'.format(certDir))
    ans = input('  Should the {} directory still be used for the certificates?[YES/no]: '.format(certDir)).lower()

    if ans == "yes" or ans == "":
        os.makedirs(os.path.dirname(certDir), exist_ok=True)
        print('')
    else:
        print('Exiting...')
        sys.exit(0)

    # Beanstalk file and dirs 
    bstalkExtensionDir     = '.ebextensions/'
    bstalk_SSL_file        = bstalkExtensionDir + 'ssl-file.config'
    bstalk_options_file    = bstalkExtensionDir + 'options.config'
    bstalk_sec_group_file  = bstalkExtensionDir + 'sec-group.config'
    platformDir            = '.platform/nginx/conf.d/'
    nginx_https_file       = platformDir + 'https.conf' 
    nginx_conf_file        = '.platform/nginx/nginx.conf' 

    # SSL files
    passFile  = certDir + 'pass_phrase.txt'
    webKey    = certDir + 'myWebServerKey.pem'
    webCert   = certDir + 'myWebServerCert.pem'
    appKey    = certDir + 'myAppKey.pem'
    appCert   = certDir + 'myAppCert.pem'

    os.makedirs(os.path.dirname(bstalkExtensionDir), exist_ok=True)
    os.makedirs(os.path.dirname(platformDir), exist_ok=True)

    create_ssl_file(passFile, webKey, webCert, appKey, appCert, bstalk_SSL_file)
    create_options_file(passFile, bstalk_options_file)
    create_sec_group_file(bstalk_sec_group_file)
    create_https_conf_file(nginx_https_file)
    create_nginx_conf_file(nginx_conf_file)
    create_env_file(passFile, certDir, appKey, appCert)


    defaultIgnoreDir = userHome + '/repos/gitignore/'
    defaultGitIgnoreFile = defaultIgnoreDir + '.gitignore' 
    defaultEbIgnoreFile = defaultIgnoreDir + '.ebignore' 

    print('\nBoth .gitignore and .ebignore files should be created as well. Please give the locations of each, or "NONE" to skip:')
    gitIgnoreFile = input('  Location of .gitignore, it will be copied to cwd: [{}]: '.format(defaultGitIgnoreFile))
    ebIgnoreFile = input('  Location of .ebignore, it will be copied to cwd: [{}]: '.format(defaultEbIgnoreFile))

    if gitIgnoreFile == 'NONE':
        pass
    elif gitIgnoreFile == '':
        gitIgnoreFile = defaultGitIgnoreFile
        shutil.copy2(gitIgnoreFile, '.gitignore')
    elif os.path.exists(gitIgnoreFile):
        shutil.copy2(gitIgnoreFile, '.gitignore')
    else:
        print('\n*** Error creating .gitignore file, check if it exists ***')
        sys.exit(1)

    if ebIgnoreFile == 'NONE':
        pass
    elif ebIgnoreFile == '':
        ebIgnoreFile = defaultEbIgnoreFile
        shutil.copy2(ebIgnoreFile, '.ebignore')
    elif os.path.exists(ebIgnoreFile):
        shutil.copy2(ebIgnoreFile, '.ebignore')
    else:
        print('\n*** Error creating .ebignore file, check if it exists ***')
        sys.exit(1)

    print(
        "\nSetup finished, now verify the application works.\n"
        ">>>> 1. VERIFY <<<<\n"
        "  First test the app by running 'node app.js', and go to https://localhost:3030 (note https)\n"
        "\n"
        ">>>> 2. DEPLOY <<<<\n"
        "  Once you have verified the application is working, you can deploy to Beanstalk.\n"
        "  Run 'eb init' and 'eb create' commands, for example (mykeyName is your AWS API key name):\n\n" +
        "    $ eb init\n" + 
        "    $ eb create --single --enable-spot --instance-types t3.nano,t3.micro <env_name_is_here>\n"
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print('\nReceived Keyboard interrupt. Exiting...')
    except ValueError as e:
        print(e)
    sys.exit(0)
