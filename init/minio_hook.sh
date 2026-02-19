mc alias set local http://localhost:9000 atc atch1114
mc admin config set local notify_webhook:primary endpoint="http://host.docker.internal:5000/api/osshook" queue_limit="0"
mc admin service restart local
mc admin config get local notify_webhook