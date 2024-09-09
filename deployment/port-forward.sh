kubectl port-forward svc/divedb-pg-service 5432:5432 &
kubectl port-forward svc/divedb-django-service 8000:8000

# Code for migrations goes here