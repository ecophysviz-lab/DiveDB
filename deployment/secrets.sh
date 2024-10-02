source .env

kubectl delete secret divedb-postgres-credentials

kubectl create secret generic divedb-postgres-credentials \
  --from-literal=POSTGRES_DB=$POSTGRES_DB \
  --from-literal=POSTGRES_USER=$POSTGRES_USER \
  --from-literal=POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
  --from-literal=POSTGRES_PORT=$POSTGRES_PORT \
  --from-literal=POSTGRES_HOST=$POSTGRES_HOST \
  --from-literal=DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY \
  --from-literal=OPENSTACK_AUTH_URL=$OPENSTACK_AUTH_URL \
  --from-literal=OPENSTACK_APPLICATION_CREDENTIAL_ID=$OPENSTACK_APPLICATION_CREDENTIAL_ID \
  --from-literal=OPENSTACK_APPLICATION_CREDENTIAL_SECRET=$OPENSTACK_APPLICATION_CREDENTIAL_SECRET