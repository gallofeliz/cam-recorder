# cam-recorder

See docker-compose.yml


TODO :
- Listen Shutdown signal and, using python-gallocloud-utils, clear the schedulers
- Change User to nobody (and volume perm), ability tu change user with docker, and why not use env vars like linuxserver.io
  - https://github.com/linuxserver/docker-baseimage-alpine/blob/master/root/etc/cont-init.d/10-adduser
  - https://github.com/ncopa/su-exec
