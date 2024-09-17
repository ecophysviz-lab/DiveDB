POD_NAME=$(kubectl get pods -l app=divedb-django -o jsonpath='{.items[0].metadata.name}')

# Might have to run 
kubectl exec -it $POD_NAME -- python3 manage.py makemigrations
kubectl exec -it $POD_NAME -- python3 manage.py migrate