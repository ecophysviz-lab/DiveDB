POD_NAME=$(kubectl get pods -l app=divedb-django -o jsonpath='{.items[0].metadata.name}')

kubectl exec -it $POD_NAME -- bash