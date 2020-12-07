# scisoseq-portal

## Installation

These are the steps I took to get the server up and running on Ubuntu 20.04.

### Install system dependencies

```
sudo apt-get install nginx
curl -sL https://deb.nodesource.com/setup_15.x | sudo -E bash -
sudo apt-get install nodejs
```

### Retrieve data

```
rclone copy Fetal_scIsoSeq:processed_data/01a_PseudoBulk_11M/All_filtered_118k_multiexon_A0.75_minRead3_2datasetsupport_talon.gtf .
rclone copy Fetal_scIsoSeq:shiny_prototype/Expression/Isoform_Average_percent_expression.txt.gz .
wget ftp://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_35/GRCh37_mapping/gencode.v35lift37.annotation.gtf.gz
gunzip gencode.v35lift37.annotation.gtf.gz Isoform_Average_percent_expression.txt.gz
```

### Clone this git project

```
git clone --recurse-submodules git@github.com:cjops/scisoseq-portal.git
cd scisoseq-portal
```

### Create a virtual environment with Flask and gunicorn

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Install the project

```
npm install
npx rollup -c

python install.py ../data All_filtered_118k_multiexon_A0.75_minRead3_2datasetsupport_talon
```

### System configuration

Modify or create the configuration files listed below, then run:

```
ln -s /etc/nginx/sites-available/gandallab.connor.jp /etc/nginx/sites-enabled/
ln -s /etc/nginx/sites-available/gandallab-default /etc/nginx/sites-enabled/

systemctl enable --now gunicorn.socket
systemctl restart nginx
```

Run [certbot](https://certbot.eff.org/docs/using.html#nginx).

### Outdated mongodb instructions

```
wget -qO - https://www.mongodb.org/static/pgp/server-4.4.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/4.4 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-4.4.list
sudo apt-get update
sudo apt-get install mongodb-org
sudo systemctl start mongod
sudo systemctl enable mongod

mongodump --db=gandallab --archive=gandallab-mongo.gz --gzip
gcloud compute scp gandallab-mongo.gz jops@scisoseq-portal:.

mongorestore --archive=gandallab-mongo.gz --gzip
```

## References

https://flask.palletsprojects.com/en/1.1.x/deploying/wsgi-standalone/#gunicorn
https://docs.gunicorn.org/en/stable/deploy.html
https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-20-04
https://docs.mongodb.com/manual/tutorial/install-mongodb-on-ubuntu/
https://github.com/nodesource/distributions/blob/master/README.md

## Configuration files

### /etc/systemd/system/gunicorn.service
```
[Unit]
Description=gunicorn daemon
Requires=gunicorn.socket
After=network.target

[Service]
Type=notify
# the specific user that our service will run as
User=jops
Group=www-data
# another option for an even more restricted service is
# DynamicUser=yes
# see http://0pointer.net/blog/dynamic-users-with-systemd.html
RuntimeDirectory=gunicorn
WorkingDirectory=/home/jops/scisoseq-portal
Environment="PATH=/home/jops/scisoseq-portal/.venv/bin"
ExecStart=/home/jops/scisoseq-portal/.venv/bin/gunicorn main:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### /etc/systemd/system/gunicorn.socket
```
Description=gunicorn socket

[Socket]
ListenStream=/run/gunicorn.sock
# Our service won't need permissions for the socket, since it
# inherits the file descriptor by socket activation
# only the nginx daemon will need access to the socket
User=www-data
# Optionally restrict the socket permissions even more.
# Mode=600

[Install]
WantedBy=sockets.target
```

### /etc/nginx/sites-available/gandallab-default
```
server {
  # if no Host match, close the connection to prevent host spoofing
  listen 80 default_server;
  listen [::]:80 default_server;

  return 444;
}
```

### /etc/nginx/sites-available/gandallab.connor.jp
```
upstream app_server {
  # fail_timeout=0 means we always retry an upstream even if it failed
  # to return a good HTTP response

  # for UNIX domain socket setups
  server unix:/run/gunicorn.sock fail_timeout=0;

  # for a TCP configuration
  # server 192.168.0.7:8000 fail_timeout=0;
}

server {
  # use 'listen 80 deferred;' for Linux
  # use 'listen 80 accept_filter=httpready;' for FreeBSD
  listen 80 deferred;
  client_max_body_size 4G;

  # set the correct host(s) for your site
  server_name gandallab.connor.jp;

  keepalive_timeout 5;

  # path for static files
  root /home/jops/scisoseq-portal/static;

  location / {
    # checks for static file, if not found proxy to app
    try_files $uri @proxy_to_app;
  }

  location @proxy_to_app {
    proxy_set_header Host $http_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    # we don't want nginx trying to do something clever with
    # redirects, we set the Host: header above already.
    proxy_redirect off;
    proxy_pass http://app_server;
  }

  error_page 500 502 503 504 /500.html;
  location = /500.html {
    root /home/jops/scisoseq-portal/static;
  }
}
```

### /etc/nginx/nginx.conf
```
user www-data;
worker_processes auto;
pid /run/nginx.pid;
include /etc/nginx/modules-enabled/*.conf;

events {
        worker_connections 768;
        # multi_accept on;
}

http {

        ##
        # Basic Settings
        ##

        sendfile on;
        tcp_nopush on;
        tcp_nodelay on;
        keepalive_timeout 65;
        types_hash_max_size 2048;
        # server_tokens off;

        # server_names_hash_bucket_size 64;
        # server_name_in_redirect off;

        include /etc/nginx/mime.types;
        default_type application/octet-stream;

        ##
        # SSL Settings
        ##

        ssl_protocols TLSv1 TLSv1.1 TLSv1.2 TLSv1.3; # Dropping SSLv3, ref: POODLE
        ssl_prefer_server_ciphers on;

        ##
        # Logging Settings
        ##

        access_log /var/log/nginx/access.log;
        error_log /var/log/nginx/error.log;

        ##
        # Gzip Settings
        ##

        gzip on;

        # gzip_vary on;
        # gzip_proxied any;
        # gzip_comp_level 6;
        # gzip_buffers 16 8k;
        # gzip_http_version 1.1;
        # gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

        ##
        # Virtual Host Configs
        ##

        include /etc/nginx/conf.d/*.conf;
        include /etc/nginx/sites-enabled/*;
}
```