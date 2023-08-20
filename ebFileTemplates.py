#
# Copyright 2020 Mark Duffield
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file
# except in compliance with the License. A copy of the License is located at
#
#    http://www.apache.org/licenses/LICENSE-2.0 
#
# or in the "license" file accompanying this file. This file is distributed on an "AS IS"
# BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under the License.
#

_SSL_FILE_HEADER = """
# location: .ebextensions/ssl-files.config

files:
"""

_SSL_WEB_SRV_KEY_INFO = """
  /etc/pki/tls/certs/server.key:
    mode: "000400"
    owner: root
    group: root
    content: |
"""

_SSL_WEB_SRV_CRT_INFO = """
  /etc/pki/tls/certs/server.crt:
    mode: "000400"
    owner: root
    group: root
    content: |
"""

_SSL_APP_KEY_INFO = """
  /home/webapp/appCert/app1.key:
    mode: "000400"
    owner: webapp
    group: webapp
    content: |
"""

_SSL_APP_CERT_INFO = """
  /home/webapp/appCert/app1.crt:
    mode: "000400"
    owner: webapp
    group: webapp
    content: |
"""

_OPTIONS_FILE_TEMPLATE = """
option_settings:
  aws:elasticbeanstalk:environment:proxy:staticfiles:
    /public: /public
  aws:elasticbeanstalk:managedactions:
    ManagedActionsEnabled: true
    PreferredStartTime: "Mon:10:00"
  aws:elasticbeanstalk:managedactions:platformupdate:
    UpdateLevel: patch
    InstanceRefreshEnabled: true
  aws:elasticbeanstalk:application:environment:
    PORT: 5000
    PKEY_PASSPHRASE: '{0}'
    NODE_ENV: 'production'
"""

_SEC_GROUP_TEMPLATE = """
Resources:
  sslSecurityGroupIngress: 
    Type: AWS::EC2::SecurityGroupIngress
    Properties:
      GroupId: {"Fn::GetAtt" : ["AWSEBSecurityGroup", "GroupId"]}
      IpProtocol: tcp
      ToPort: 443
      FromPort: 443
      CidrIp: 0.0.0.0/0
"""


_HTTPS_CONF_FILE_TEMPLATE = """
# HTTPS server
# location: .platform/nginx/conf.d/https.conf

server {
  listen       443 ssl;
  server_name  localhost;

  ssl_certificate      /etc/pki/tls/certs/server.crt;
  ssl_certificate_key  /etc/pki/tls/certs/server.key;

  ssl_session_timeout  5m;

  ssl_protocols  TLSv1 TLSv1.1 TLSv1.2;
  ssl_prefer_server_ciphers   on;

  location / {
          ## proxy_pass has to point to https and the port number used for PORT in the options.conf file
          proxy_pass  https://localhost:5000;
          proxy_set_header   Connection "";
          proxy_http_version 1.1;
          proxy_set_header        Host            $host;
          proxy_set_header        X-Real-IP       $remote_addr;
          proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header        X-Forwarded-Proto https;
  }
}
"""

_NGINX_CONF_TEMPLATE = """
# Elastic Beanstalk Nginx Configuration File
# Added redirect

user                    nginx;
error_log               /var/log/nginx/error.log warn;
pid                     /var/run/nginx.pid;
worker_processes        auto;
worker_rlimit_nofile    31486;

events {
    worker_connections  1024;
}

http {
    server_tokens off;

    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                      '$status $body_bytes_sent "$http_referer" '
                      '"$http_user_agent" "$http_x_forwarded_for"';

    include       conf.d/*.conf;

    map $http_upgrade $connection_upgrade {
        default     "upgrade";
    }

    server {
        listen        80 default_server;
        access_log    /var/log/nginx/access.log main;

        client_header_timeout 60;
        client_body_timeout   60;
        keepalive_timeout     60;
        gzip                  off;
        gzip_comp_level       4;
        gzip_types text/plain text/css application/json application/javascript application/x-javascript text/xml application/xml application/xml+rss text/javascript;

        # Include the Elastic Beanstalk generated locations
        include conf.d/elasticbeanstalk/*.conf;

        # Permanently redirecting to https
        return 301 https://$host$request_uri;
    }
}
"""

_ENV_FILE_TEMPLATE = """
PKEY_PASSPHRASE = '{0}'
LOCAL_KEY_DIR = '{1}'
APP_KEY_FILE = '{2}'
APP_CERT_FILE = '{3}'
"""
